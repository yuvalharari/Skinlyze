import torch
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

# Load CLIP model once
device = "cuda" if torch.cuda.is_available() else "cpu"

model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
model.to(device)
model.eval()


def validate_with_clip(image_path):

    try:
        image = Image.open(image_path).convert("RGB")

        # Simple binary classification - skin or not skin
        labels = [
            "a close-up photo of human skin with a lesion or mole",
            "a photo that does not show human skin or a skin lesion"
        ]

        inputs = processor(
            text=labels,
            images=image,
            return_tensors="pt",
            padding=True
        ).to(device)

        with torch.no_grad():
            outputs = model(**inputs)
            probs = outputs.logits_per_image.softmax(dim=1)[0]

        skin_prob = probs[0].item()
        not_skin_prob = probs[1].item()

        # If skin probability is higher - allow analysis
        if skin_prob > not_skin_prob:
            return {"valid": True}

        # Otherwise - reject with a clear message
        return {
            "valid": False,
            "message": "Unable to detect a skin lesion in the uploaded image. Please upload a clear, close-up photo of the lesion on a skin background."
        }

    except Exception as e:
        # If CLIP fails for any reason - allow the analysis to continue
        return {"valid": True}