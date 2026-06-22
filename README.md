# Skinlyze

Skinlyze is a web-based deep learning system for preliminary skin lesion assessment.

The application allows users to upload an image and classify it into one of two categories:

* Suspicious
* Not Suspicious

The system also performs lesion segmentation and provides an ABCDE-based analysis to support awareness and early detection.

## Technologies

* Python
* Flask
* PyTorch
* OpenCV
* Scikit-image
* HTML
* CSS
* JavaScript

## Project Structure

* `app.py` – Flask application
* `model/` – validation, prediction, segmentation and ABCDE analysis
* `templates/` – HTML pages
* `static/` – CSS, JavaScript and images
* `train/` – model training notebooks
* `data/` – metadata files

## Running Locally

```bash
pip install -r requirements.txt
python app.py
```

The application will run on:

```
http://localhost:7860
```

## Disclaimer

Skinlyze is intended for educational purposes only and does not provide medical diagnosis.
