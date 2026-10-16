"""Computer vision: image -> waste category + probability scores.

Backends (VISION_BACKEND):
  mock : dependency-free demo classifier (colour heuristic) so the demo never breaks.
  hf   : any Hugging Face image-classification model (VISION_MODEL); raw labels are
         mapped onto our 5 categories by keyword.
"""
import hashlib, io
from functools import lru_cache
from PIL import Image
from ..config import settings

CATEGORIES = ["plastic", "paper", "organic", "metal", "hazardous"]
KEYWORDS = {
    "plastic": ["plastic", "bottle", "bag", "polyethylene", "packaging"],
    "paper": ["paper", "cardboard", "carton", "newspaper", "book"],
    "organic": ["organic", "food", "fruit", "vegetable", "banana", "biological", "peel", "compost"],
    "metal": ["metal", "can", "tin", "aluminium", "aluminum", "steel"],
    "hazardous": ["battery", "chemical", "hazard", "e-waste", "electronic", "syringe", "bulb"],
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_image(data: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        return Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as e:
        raise ValueError("Not a valid image") from e


def _normalise(scores: dict[str, float]) -> dict[str, float]:
    total = sum(scores.values()) or 1.0
    return {k: round(scores.get(k, 0.0) / total, 4) for k in CATEGORIES}


def _mock(img: Image.Image) -> dict[str, float]:
    r, g, b = img.resize((1, 1)).getpixel((0, 0))
    s = {
        "plastic": 0.2 + b / 255,                 # bluish/clear
        "paper": 0.2 + (min(r, g, b)) / 255,      # bright / neutral
        "organic": 0.2 + g / 255,                 # greenish/brown
        "metal": 0.2 + (1 - abs(r - b) / 255) * (1 - max(r, g, b) / 400),
        "hazardous": 0.05 + r / 600,
    }
    return s


@lru_cache(maxsize=1)
def _hf_pipe():
    from transformers import pipeline  # lazy import: heavy
    return pipeline("image-classification", model=settings.vision_model)


def _hf(img: Image.Image) -> dict[str, float]:
    out = _hf_pipe()(img, top_k=10)
    scores = {c: 0.0 for c in CATEGORIES}
    for item in out:
        label = item["label"].lower()
        for cat, kws in KEYWORDS.items():
            if any(k in label for k in kws):
                scores[cat] += float(item["score"])
                break
    return scores


def classify(data: bytes) -> dict:
    img = validate_image(data)
    raw = _hf(img) if settings.vision_backend == "hf" and settings.vision_model else _mock(img)
    scores = _normalise(raw)
    label = max(scores, key=scores.get)
    return {"label": label, "confidence": scores[label], "scores": scores}
