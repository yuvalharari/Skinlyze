import cv2
import numpy as np
from sklearn.cluster import KMeans
from skimage import color


def load_image_rgb(path):
    img = cv2.imread(path)

    if img is None:
        raise ValueError(f"Image not found or cannot be loaded: {path}")

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return img


def detect_vignette(img_rgb, edge_width_ratio=0.08, threshold=25):
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape

    edge_w = int(w * edge_width_ratio)
    edge_h = int(h * edge_width_ratio)

    # Extract edges
    top = gray[:edge_h, :]
    bottom = gray[h-edge_h:, :]
    left = gray[:, :edge_w]
    right = gray[:, w-edge_w:]

    edges = np.concatenate([top.flatten(), bottom.flatten(),
                            left.flatten(), right.flatten()])

    # Extract center
    cx1, cx2 = int(w*0.3), int(w*0.7)
    cy1, cy2 = int(h*0.3), int(h*0.7)
    center = gray[cy1:cy2, cx1:cx2].flatten()

    edges_mean = edges.mean()
    center_mean = center.mean()

    return (center_mean - edges_mean) > threshold


def auto_remove_vignette(img_rgb):
    if img_rgb is None:
        return None

    if detect_vignette(img_rgb):

        h, w = img_rgb.shape[:2]
        center = (w//2, h//2)
        radius = int(min(h, w) * 0.45)

        Y, X = np.ogrid[:h, :w]
        dist = (X - center[0])**2 + (Y - center[1])**2
        circle_mask = dist <= radius**2

        cleaned = img_rgb.copy()
        cleaned[~circle_mask] = 255
        return cleaned

    else:
        return img_rgb

def segment_otsu(img_rgb):
    if img_rgb is None:
        return None

    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    gray_blur = cv2.GaussianBlur(gray, (5, 5), 0)

    _, mask = cv2.threshold(
        gray_blur, 0, 255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    return (mask > 0).astype("uint8")

def segment_lab(img_rgb):
    if img_rgb is None:
        return None

    lab = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2LAB)
    L, A, B = cv2.split(lab)

    # Lesions are darker in L
    _, mask_L = cv2.threshold(
        L, 0, 255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    _, mask_A = cv2.threshold(
        A, 0, 255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    # Combine both
    mask = cv2.bitwise_and(mask_L, mask_A)

    return (mask > 0).astype("uint8")


def segment_kmeans(img_rgb, k=3):
    if img_rgb is None:
        return None

    # Flatten image 
    pixels = img_rgb.reshape(-1, 3)

    # KMeans
    try:
        kmeans = KMeans(n_clusters=k, n_init=10)
        labels = kmeans.fit_predict(pixels)
        centers = kmeans.cluster_centers_
    except:
        return None  # fallback if clustering fails

    # Compute brightness of each cluster (lower = darker)
    brightness = centers.mean(axis=1)

    # Lesion = darkest cluster
    lesion_cluster = np.argmin(brightness)

    # Build mask
    mask = (labels == lesion_cluster).astype("uint8")
    mask = mask.reshape(img_rgb.shape[:2])

    return mask

def clean_mask(mask):

    # If mask is None - return None safely
    if mask is None:
        return None

    mask = np.array(mask, dtype="uint8")

    # If mask is empty or wrong shape
    if mask.ndim != 2 or mask.sum() < 5:
        return np.zeros_like(mask, dtype="uint8")

    # Convert to uint8 0/255
    mask = (mask * 255).astype("uint8")

    # Morphology: close holes
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    # Morphology: remove small noise
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # Connected components
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)

    if num_labels <= 1:
        return (mask > 0).astype("uint8")

    # Keep largest connected component
    sizes = stats[1:, cv2.CC_STAT_AREA]
    largest = 1 + np.argmax(sizes)

    final_mask = (labels == largest).astype("uint8")

    return final_mask


def detect_bad_boundary_mask(mask, border_thickness_ratio=0.08, edge_ratio_threshold=0.20):

    if mask is None:
        return True  # treat as bad mask

    h, w = mask.shape

    # thickness of the border
    t_h = int(h * border_thickness_ratio)
    t_w = int(w * border_thickness_ratio)

    border = np.zeros_like(mask, dtype="uint8")

    border[0:t_h, :] = 1              # top
    border[h - t_h:h, :] = 1          # bottom
    border[:, 0:t_w] = 1              # left
    border[:, w - t_w:w] = 1          # right

    # count overlap
    border_overlap = (mask * border).sum()
    lesion_pixels = mask.sum() + 1e-6

    ratio = border_overlap / lesion_pixels

    return ratio > edge_ratio_threshold

def is_segmentation_unreliable(masks):

    if masks is None or len(masks) == 0:
        return True

    bad = 0

    for m in masks:
        if detect_bad_boundary_mask(m):
            bad += 1

    return bad == len(masks)

def hole_score(mask):

    if mask is None:
        return 0

    mask = np.array(mask, dtype="uint8")

    # invert mask: holes become white
    inv = (1 - mask).astype("uint8")

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(inv, connectivity=8)

    hole_area = 0
    lesion_area = mask.sum()

    if lesion_area < 5:
        return 0

    for lbl in range(1, num_labels):

        area = stats[lbl, cv2.CC_STAT_AREA]

        component = (labels == lbl)

        # keep only holes inside lesion
        if np.any(component & (mask == 0)):
            continue

        hole_area += area

    hole_ratio = hole_area / lesion_area

    # less holes = better score
    hole_score_value = max(0, 1 - min(1, hole_ratio * 5))

    return float(hole_score_value)

def score_mask(mask, img_rgb):

    if mask is None:
        return 0

    mask = np.array(mask, dtype="uint8")

    h, w = mask.shape
    area = mask.sum()
    area_ratio = area / (h * w + 1e-6)

    # AREA SCORE
    if 0.005 <= area_ratio <= 0.35:
        area_score = 1.0
    elif area_ratio < 0.005:
        area_score = 0.5
    else:
        area_score = 0.0

    # COMPACTNESS
    filled = cv2.morphologyEx(mask * 255,
                              cv2.MORPH_CLOSE,
                              np.ones((7, 7), np.uint8))
    holes = filled.sum() - mask.sum()
    compactness = 1 - min(1, holes / max(1, area))

    # CONTRAST
    if area > 10:
        lesion_mean = img_rgb[mask == 1].mean()
        bg_mean = img_rgb[mask == 0].mean()
        contrast = 1 if lesion_mean < bg_mean else 0
    else:
        contrast = 0

    # EDGE PENALTY (relative)
    t = int(min(h, w) * 0.03)
    border = np.zeros_like(mask)
    border[:t, :] = 1
    border[-t:, :] = 1
    border[:, :t] = 1
    border[:, -t:] = 1

    border_overlap = (mask * border).sum()
    border_ratio = border_overlap / max(1, area)
    edge_penalty = max(0, 1 - border_ratio)

    hole_s = hole_score(mask)

    total = (
        0.30 * compactness +
        0.20 * area_score +
        0.20 * contrast +
        0.15 * edge_penalty +
        0.15 * hole_s
    )

    return float(total)

def combined_segmentation(img_rgb):

    if img_rgb is None:
        return None, [], []

    img_clean = auto_remove_vignette(img_rgb)

    m1_raw = segment_otsu(img_clean)
    m2_raw = segment_lab(img_clean)
    m3_raw = segment_kmeans(img_clean)

    m1 = clean_mask(m1_raw)
    m2 = clean_mask(m2_raw)
    m3 = clean_mask(m3_raw)

    masks = [m1, m2, m3]

    if is_segmentation_unreliable(masks):
        return None, masks, [0, 0, 0]

    scores = [
        score_mask(m1, img_clean),
        score_mask(m2, img_clean),
        score_mask(m3, img_clean)
    ]

    best_index = int(np.argmax(scores))

    return masks[best_index], masks, scores

def compute_asymmetry(mask):

    if mask is None:
        return {"score": 0, "explanation": "Invalid mask"}

    mask = np.array(mask, dtype="uint8")

    mask_u8 = (mask * 255).astype("uint8")

    # Contours
    contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return {"score": 0, "explanation": "Invalid mask"}

    cnt = contours[0]

    # Convex hull
    hull = cv2.convexHull(cnt)
    h, w = mask.shape
    hull_mask = np.zeros((h, w), dtype="uint8")
    cv2.drawContours(hull_mask, [hull], -1, 1, -1)

    hull_mask_f = hull_mask.astype("float32")

    mid_y = h // 2
    mid_x = w // 2

    # Areas
    area_top    = float(hull_mask_f[:mid_y, :].sum())
    area_bottom = float(hull_mask_f[mid_y:, :].sum())
    area_left   = float(hull_mask_f[:, :mid_x].sum())
    area_right  = float(hull_mask_f[:, mid_x:].sum())

    total_area = float(hull_mask_f.sum()) + 1e-6

    # Asymmetry scores
    asym_tb = abs(area_top - area_bottom) / total_area
    asym_lr = abs(area_left - area_right) / total_area

    asym = float((asym_tb + asym_lr) / 2.0)
    asym = float(np.clip(asym, 0, 1))

    explanation = (
    "High asymmetry"     if asym >= 0.6 else
    "Moderate asymmetry" if asym >= 0.4 else
    "Slight asymmetry"   if asym >= 0.2 else
    "Minimal asymmetry"
)

    return {"score": asym, "explanation": explanation}


def compute_border(mask):

    if mask is None:
        return {"score": 1.0, "explanation": "Invalid mask"}

    mask = np.array(mask, dtype="uint8")

    mask_u8 = (mask * 255).astype("uint8")

    # Contours
    contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return {"score": 1.0, "explanation": "Invalid mask"}

    cnt = contours[0]

    perimeter = cv2.arcLength(cnt, True)
    area = cv2.contourArea(cnt) + 1e-6

    perimeter_ratio = perimeter / np.sqrt(area)

    # Normalize
    score = np.clip((perimeter_ratio - 3) / 7, 0, 1)

    explanation = (
    "Highly irregular border" if score >= 0.6 else
    "Moderate irregularity"   if score >= 0.4 else
    "Slight irregularity"     if score >= 0.2 else
    "Smooth border"
)

    return {"score": float(score), "explanation": explanation}

def compute_color(img_rgb, mask):

    if img_rgb is None or mask is None:
        return {"score": 0, "explanation": "Invalid input"}

    mask = np.array(mask, dtype="uint8")

    lesion_pixels = img_rgb[mask == 1]

    if len(lesion_pixels) < 20:
        return {"score": 0, "explanation": "Too small to evaluate"}

    # Convert to LAB
    lab = color.rgb2lab(lesion_pixels.reshape(-1, 1, 3)).reshape(-1, 3)

    # Cluster colors
    k = min(4, len(lab))

    try:
        km = KMeans(n_clusters=k, random_state=0, n_init=10).fit(lab)
        centers = km.cluster_centers_
    except:
        return {"score": 0, "explanation": "Clustering failed"}

    # Color variance
    dists = np.linalg.norm(centers - centers.mean(axis=0), axis=1)

    score = np.clip(dists.mean() / 25, 0, 1)

    explanation = (
    "High color variation"    if score >= 0.6 else
    "Moderate color variation" if score >= 0.4 else
    "Slight color variation"  if score >= 0.2 else
    "Uniform color"
)

    return {"score": float(score), "explanation": explanation}


def compute_abc_scores(img_rgb, mask):

    if img_rgb is None or mask is None or mask.sum() < 30:
        return {"error": "Mask invalid or lesion not found."}

    A = compute_asymmetry(mask)
    B = compute_border(mask)
    C = compute_color(img_rgb, mask)

    total = (
        0.15 * A["score"] +
        0.45 * B["score"] +
        0.40 * C["score"]
    )

    risk = (
        "High suspicion (Derm consult needed)" if total > 0.65 else
        "Medium risk - monitor closely" if total > 0.45 else
        "Low suspicion"
    )

    return {
        "A": A,
        "B": B,
        "C": C,
        "total_score": float(total),
        "risk_level": risk
    }

def analyze_abc(image_path):

    try:
        img = load_image_rgb(image_path)

        best_mask, masks, scores = combined_segmentation(img)

        if best_mask is None:
            return {
                "valid": False,
                "error": "Segmentation unreliable"
            }

        abc = compute_abc_scores(img, best_mask)

        return {
            "valid": True,
            "abc": abc
        }

    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }