
from model.model_predict import predict_image
from model.abc_functions import analyze_abc

def analyze_full(image_path, threshold=0.2644):

    try:
        model_result = predict_image(image_path, threshold)

        pred = model_result["prediction"]
        prob = model_result["probability"]

        # CASE: Suspicious
        if pred == 1:

            abc_result = analyze_abc(image_path)
            explanation = []

            if abc_result.get("valid"):

                abc = abc_result["abc"]

                # Asymmetry
                a_score = abc["A"]["score"]
                if a_score > 0.6:
                    explanation.append("High asymmetry detected")
                elif a_score > 0.3:
                    explanation.append("Moderate asymmetry detected")

                # Border 
                b_score = abc["B"]["score"]
                if b_score > 0.6:
                    explanation.append("Highly irregular borders")
                elif b_score > 0.3:
                    explanation.append("Some border irregularity")

                # Color
                c_score = abc["C"]["score"]
                if c_score > 0.6:
                    explanation.append("Significant color variation")
                elif c_score > 0.3:
                    explanation.append("Mild color variation")

                # fallback
                if not explanation:
                    explanation.append("Only minor visual irregularities detected")

            else:
                explanation.append("Unable to fully analyze lesion structure")

            return {
                "prediction": pred,
                "probability": prob,
                "label": "Suspicious",
                "message": "The lesion appears suspicious based on the model's assessment.",
                "explanation": explanation
            }

        # CASE: Not Suspicious 
        else:
            return {
                "prediction": pred,
                "probability": prob,
                "label": "Not Suspicious",
                "message": "The lesion does not appear suspicious based on the model's assessment. Monitoring is recommended."
            }

    except Exception as e:
        return {"error": str(e)}


