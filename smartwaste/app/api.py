import secrets
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db, utcnow
from .models import AIOutput, Bin, BinReading, Collection, User, WasteClassification, Zone
from .schemas import BinCreate, CollectionIn, ReadingIn, Token, ZoneCreate
from .security import (admin_user, create_token, current_user, device_bin, hash_device_key,
                       user_or_device, verify_password)
from .services import genai, routing, twin, vision
from .services.prediction import predict
from .ws import manager

router = APIRouter()


def _get_bin(db: Session, bin_id: int) -> Bin:
    b = db.get(Bin, bin_id)
    if not b:
        raise HTTPException(404, "Bin not found")
    return b


def _state(db: Session, b: Bin) -> dict:
    return twin.bin_state(b, twin.composition(db, [b.id]), predict(db, b))


# ---------- auth ----------
@router.post("/auth/login", response_model=Token, tags=["auth"])
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.username == form.username))
    if not u or not verify_password(form.password, u.password_hash):
        raise HTTPException(401, "Incorrect username or password")
    return Token(access_token=create_token(u.username, u.role))


# ---------- admin: zones & bins ----------
@router.post("/zones", status_code=201, tags=["admin"])
def create_zone(body: ZoneCreate, db: Session = Depends(get_db), _=Depends(admin_user)):
    z = Zone(name=body.name)
    db.add(z)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Zone already exists")
    return {"id": z.id, "name": z.name}


@router.post("/bins", status_code=201, tags=["admin"])
def create_bin(body: BinCreate, db: Session = Depends(get_db), _=Depends(admin_user)):
    if not db.get(Zone, body.zone_id):
        raise HTTPException(404, "Zone not found")
    device_key = secrets.token_urlsafe(24)  # shown ONCE; only the hash is stored
    b = Bin(**body.model_dump(), device_key_hash=hash_device_key(device_key))
    db.add(b)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bin code already exists")
    return {"id": b.id, "code": b.code, "device_key": device_key}


@router.get("/bins", tags=["twin"])
def list_bins(db: Session = Depends(get_db), _=Depends(current_user)):
    return [_state(db, b) for b in db.scalars(select(Bin).order_by(Bin.code))]


@router.get("/bins/{bin_id}", tags=["twin"])
def get_bin(bin_id: int, db: Session = Depends(get_db), _=Depends(current_user)):
    return _state(db, _get_bin(db, bin_id))


@router.get("/bins/{bin_id}/history", tags=["twin"])
def bin_history(bin_id: int, limit: int = 200, db: Session = Depends(get_db), _=Depends(current_user)):
    _get_bin(db, bin_id)
    rows = db.execute(select(BinReading.recorded_at, BinReading.fill_level)
                      .where(BinReading.bin_id == bin_id)
                      .order_by(BinReading.recorded_at.desc()).limit(min(limit, 1000))).all()
    return [{"t": t.isoformat(), "fill_level": f} for t, f in reversed(rows)]


# ---------- IoT ingestion (ESP32 / simulator) ----------
@router.post("/devices/readings", tags=["iot"])
def ingest_reading(body: ReadingIn, bg: BackgroundTasks, b: Bin = Depends(device_bin), db: Session = Depends(get_db)):
    db.add(BinReading(bin_id=b.id, fill_level=body.fill_level))
    b.fill_level = body.fill_level
    b.updated_at = utcnow()
    db.add(b)
    db.commit()
    state = _state(db, b)
    bg.add_task(manager.broadcast, {"event": "bin_update", "bin": state})
    return {"ok": True, "status": state["status"]}


# ---------- Computer vision ----------
@router.post("/classify", tags=["vision"])
async def classify_waste(bg: BackgroundTasks, image: UploadFile = File(...), bin_code: str | None = Form(None),
                         db: Session = Depends(get_db), principal: str = Depends(user_or_device)):
    if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Only JPEG/PNG/WEBP images are allowed")
    data = await image.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Image larger than {settings.max_upload_mb} MB")
    try:
        result = await run_in_threadpool(vision.classify, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    b = None
    if bin_code:
        b = db.scalar(select(Bin).where(Bin.code == bin_code))
        if not b:
            raise HTTPException(404, "Bin not found")
        if principal.startswith("device:") and principal != f"device:{b.code}":
            raise HTTPException(403, "Device key does not belong to this bin")
    rec = WasteClassification(bin_id=b.id if b else None, label=result["label"],
                              confidence=result["confidence"], scores=result["scores"],
                              image_sha256=vision.sha256(data))
    db.add(rec)
    db.commit()
    if b:
        bg.add_task(manager.broadcast, {"event": "bin_update", "bin": _state(db, b)})
    return {"id": rec.id, **result, "bin_code": bin_code}


# ---------- Digital twin ----------
@router.get("/twin", tags=["twin"])
def twin_snapshot(db: Session = Depends(get_db), _=Depends(current_user)):
    return twin.snapshot(db)


@router.get("/bins/{bin_id}/prediction", tags=["twin"])
def bin_prediction(bin_id: int, db: Session = Depends(get_db), _=Depends(current_user)):
    return predict(db, _get_bin(db, bin_id))


@router.post("/collections", status_code=201, tags=["twin"])
def record_collection(body: CollectionIn, bg: BackgroundTasks, db: Session = Depends(get_db),
                      user: User = Depends(current_user)):
    b = _get_bin(db, body.bin_id)
    db.add(Collection(bin_id=b.id, collected_by=user.username, weight_kg=body.weight_kg, level_before=b.fill_level))
    b.fill_level, b.last_collected_at = 0.0, utcnow()
    db.add(BinReading(bin_id=b.id, fill_level=0.0))
    db.add(b)
    db.commit()
    bg.add_task(manager.broadcast, {"event": "bin_update", "bin": _state(db, b)})
    return {"ok": True, "bin_id": b.id}


@router.get("/routes/collection", tags=["twin"])
def collection_route(threshold: float = 70, db: Session = Depends(get_db), _=Depends(current_user)):
    bins = [{"id": b.id, "code": b.code, "name": b.name, "lat": b.lat, "lng": b.lng, "fill_level": b.fill_level}
            for b in db.scalars(select(Bin))]
    return routing.plan_route(bins, threshold)


# ---------- GenAI ----------
@router.post("/ai/recommendations/{bin_id}", tags=["genai"])
async def ai_recommendation(bin_id: int, db: Session = Depends(get_db), _=Depends(current_user)):
    b = _get_bin(db, bin_id)
    text, source = await run_in_threadpool(genai.recommend_for_bin, _state(db, b))
    db.add(AIOutput(kind="recommendation", bin_id=b.id, content=text, source=source))
    db.commit()
    return {"bin_id": b.id, "recommendation": text, "source": source}


@router.post("/ai/report", tags=["genai"])
async def ai_report(db: Session = Depends(get_db), _=Depends(current_user)):
    text, source = await run_in_threadpool(genai.report, twin.snapshot(db))
    db.add(AIOutput(kind="report", content=text, source=source))
    db.commit()
    return {"report": text, "source": source}


@router.get("/ai/history", tags=["genai"])
def ai_history(limit: int = 20, db: Session = Depends(get_db), _=Depends(current_user)):
    rows = db.scalars(select(AIOutput).order_by(AIOutput.id.desc()).limit(min(limit, 100))).all()
    return [{"id": r.id, "kind": r.kind, "bin_id": r.bin_id, "content": r.content, "source": r.source,
             "created_at": r.created_at.isoformat()} for r in rows]
