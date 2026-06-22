import os
import torch
import timm
from PIL import Image
from torchvision import transforms
import psutil


MODEL_PATH = os.path.join(os.path.dirname(__file__), "best_model_v8.pth")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Image preprocessing
inference_transform = transforms.Compose([
    transforms.Resize((300, 300)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    ),
])

def load_skin_model():
    model = timm.create_model(
        "efficientnet_b3",
        pretrained=False,
        num_classes=2
    )

    state_dict = torch.load(MODEL_PATH, map_location=device)
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    return model

# Load once
model = load_skin_model()


def predict_image(image_path, threshold=0.2644):
    image = Image.open(image_path).convert("RGB")
    image_tensor = inference_transform(image).unsqueeze(0).to(device)

    with torch.no_grad():
        outputs = model(image_tensor)
        probs = torch.softmax(outputs, dim=1)

        prob_suspicious = probs[0, 1].item()

    # Apply threshold
    pred = 1 if prob_suspicious >= threshold else 0

    return {
        "prediction": pred,
        "probability": prob_suspicious
    }

