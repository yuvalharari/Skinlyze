import os
import requests
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename

from model.analyze import analyze_full
from model.abc_functions import analyze_abc, combined_segmentation, load_image_rgb
from model.clip_validator import validate_with_clip

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")


# HOME PAGE
@app.route("/")
def home():
    return render_template("index.html")


# ANALYZE PAGE
@app.route("/analyze", methods=["GET"])
def analyze_page():
    return render_template("analyze.html")


# AWARENESS PAGE
@app.route("/awareness")
def awareness():
    return render_template("awareness.html")


# ANALYZE API
@app.route("/analyze", methods=["POST"])
def analyze():

    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files["image"]

    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)

    # Step 1 - CLIP validation
    clip_result = validate_with_clip(file_path)
    if not clip_result["valid"]:
        try:
            os.remove(file_path)
        except Exception:
            pass
        save_rejected_to_db("CLIP", clip_result["message"])
        return jsonify({
            "error": "image_quality",
            "message": clip_result["message"]
        }), 400

    # Step 2 - Segmentation validation
    try:
        img = load_image_rgb(file_path)
        best_mask, masks, scores = combined_segmentation(img)
        if best_mask is None:
            try:
                os.remove(file_path)
            except Exception:
                pass
            msg = "No clear lesion detected. Please ensure the lesion is centered and the background is skin only."
            save_rejected_to_db("Segmentation", msg)
            return jsonify({
                "error": "image_quality",
                "message": msg
            }), 400
    except Exception:
        pass

    # Step 3 - Full analysis
    result = analyze_full(file_path)

    if result.get("prediction") == 1:
        abc_result = analyze_abc(file_path)
        if abc_result and abc_result.get("valid"):
            result["abc_scores"] = abc_result["abc"]
            result["insight"] = generate_insight(abc_result["abc"])

    try:
        os.remove(file_path)
    except Exception:
        pass

    if "error" in result:
        return jsonify(result), 500

    save_to_db(result)

    return jsonify(result)


# STATS API
@app.route("/stats", methods=["GET"])
def stats():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return jsonify({"total": 0, "suspicious": 0, "safe": 0})

    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }

        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/analyses?select=prediction",
            headers=headers,
            timeout=10
        )

        rows = res.json()
        total = len(rows)
        suspicious = sum(1 for r in rows if r.get("prediction") == 1)
        safe = total - suspicious

        return jsonify({
            "total": total,
            "suspicious": suspicious,
            "safe": safe
        })

    except Exception:
        return jsonify({"total": 0, "suspicious": 0, "safe": 0})


def save_to_db(result):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return

    try:
        abc = result.get("abc_scores", {})

        data = {
            "prediction": result.get("prediction", 0),
            "confidence": round(result.get("probability", 0), 4),
            "a_score": round(abc.get("A", {}).get("score", 0), 4) if abc else None,
            "b_score": round(abc.get("B", {}).get("score", 0), 4) if abc else None,
            "c_score": round(abc.get("C", {}).get("score", 0), 4) if abc else None
        }

        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }

        requests.post(
            f"{SUPABASE_URL}/rest/v1/analyses",
            headers=headers,
            json=data,
            timeout=10
        )

    except Exception:
        pass


def save_rejected_to_db(reason, message):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return

    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }

        requests.post(
            f"{SUPABASE_URL}/rest/v1/rejected_images",
            headers=headers,
            json={"reason": reason, "message": message},
            timeout=10
        )

    except Exception:
        pass


def generate_insight(abc):

    a_score = abc.get("A", {}).get("score", 0)
    b_score = abc.get("B", {}).get("score", 0)
    c_score = abc.get("C", {}).get("score", 0)

    parts = []

    if a_score >= 0.6:
        parts.append("The lesion displays a clearly asymmetrical shape, where one half does not match the other - a feature that dermatologists consider when evaluating skin lesions.")
    elif a_score >= 0.4:
        parts.append("A notable degree of asymmetry was detected in the lesion's shape, meaning the two halves are not entirely uniform.")
    elif a_score >= 0.2:
        parts.append("There is mild asymmetry present in the lesion, though it remains relatively minor.")

    if b_score >= 0.6:
        parts.append("The borders of the lesion appear clearly irregular, with uneven or ragged edges that are worth monitoring closely.")
    elif b_score >= 0.4:
        parts.append("The lesion's borders show notable irregularity, with some unevenness along the edges.")
    elif b_score >= 0.2:
        parts.append("Slight border irregularity was observed, though the edges remain mostly defined.")

    if c_score >= 0.6:
        parts.append("Significant color variation is present within the lesion, including multiple shades that can be an important indicator for dermatological review.")
    elif c_score >= 0.4:
        parts.append("The lesion shows notable color variation across its surface, with different shades visible within the affected area.")
    elif c_score >= 0.2:
        parts.append("Mild color variation was detected within the lesion, though it appears mostly uniform.")

    if not parts:
        parts.append("The lesion shows minimal irregularities across asymmetry, border, and color parameters.")

    parts.append("While this analysis is based on AI-assisted image evaluation, it is not a medical diagnosis. We strongly recommend consulting a licensed dermatologist for a professional assessment.")

    return " ".join(parts)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    app.run(host="0.0.0.0", port=port)