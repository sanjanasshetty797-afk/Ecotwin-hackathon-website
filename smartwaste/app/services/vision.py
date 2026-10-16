"""YOLO-based computer vision for waste classification."""

import hashlib
import io
from functools import lru_cache
from pathlib import Path

from PIL import Image
from ultralytics import YOLO


CATEGORIES = [
    "biodegradable",
    "cardboard",
    "glass",
    "metal",
    "paper",
    "plastic",
]

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "best.pt"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_image(data: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()

        return Image.open(io.BytesIO(data)).convert("RGB")

    except Exception as e:
        raise ValueError("Not a valid image") from e


@lru_cache(maxsize=1)
def _load_model():
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"YOLO model not found at: {MODEL_PATH}"
        )

    return YOLO(str(MODEL_PATH))


def classify(data: bytes) -> dict:
    img = validate_image(data)
    model = _load_model()

    results = model.predict(
        source=img,
        conf=0.25,
        imgsz=640,
        verbose=False,
    )

    scores = {category: 0.0 for category in CATEGORIES}
    detections = []

    for result in results:
        if result.boxes is None:
            continue

        for box in result.boxes:
            class_id = int(box.cls.item())
            confidence = float(box.conf.item())

            raw_label = result.names[class_id]
            label = str(raw_label).strip().lower()

            if label not in CATEGORIES:
                continue

            scores[label] = max(scores[label], confidence)

            coordinates = box.xyxy[0].tolist()

            detections.append({
                "label": label,
                "confidence": round(confidence, 4),
                "bounding_box": {
                    "x1": round(coordinates[0], 2),
                    "y1": round(coordinates[1], 2),
                    "x2": round(coordinates[2], 2),
                    "y2": round(coordinates[3], 2),
                },
            })

    if not detections:
        return {
            "label": "unknown",
            "confidence": 0.0,
            "scores": scores,
            "detections": [],
        }

    best_detection = max(
        detections,
        key=lambda detection: detection["confidence"],
    )

    total = sum(scores.values())

    if total > 0:
        scores = {
            category: round(score / total, 4)
            for category, score in scores.items()
        }

    return {
        "label": best_detection["label"],
        "confidence": best_detection["confidence"],
        "scores": scores,
        "detections": detections,
    }