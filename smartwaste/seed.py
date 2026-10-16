"""Create demo data: admin user, campus zones/bins, 12h of readings, classifications.
Usage: python seed.py   (prints device keys for each bin)"""
import random
from datetime import timedelta
from sqlalchemy import select
from app.config import settings
from app.database import Base, SessionLocal, engine, utcnow
from app.models import Bin, BinReading, User, WasteClassification, Zone
from app.security import hash_device_key, hash_password

CAMPUS = {  # zone: (name, lat, lng, fill-rate %/h, waste mix)
    "Block A": ("Block A Bin 01", 12.9721, 77.5950, 3.0, {"paper": 5, "plastic": 3, "organic": 1, "metal": 1}),
    "Canteen": ("Canteen Bin 02", 12.9729, 77.5961, 6.0, {"organic": 6, "plastic": 4, "paper": 1, "metal": 1}),
    "Hostel": ("Hostel Bin 03", 12.9705, 77.5938, 1.5, {"plastic": 3, "organic": 3, "paper": 2, "hazardous": 1}),
    "Library": ("Library Bin 04", 12.9712, 77.5957, 2.5, {"paper": 8, "plastic": 2, "metal": 1}),
}


def seed(db, history_hours: int = 12) -> dict[str, str]:
    keys: dict[str, str] = {}
    if not db.scalar(select(User).where(User.username == "admin")):
        db.add(User(username="admin", password_hash=hash_password(settings.admin_password), role="admin"))
    now = utcnow()
    for i, (zone, (name, lat, lng, rate, mix)) in enumerate(CAMPUS.items(), 1):
        z = db.scalar(select(Zone).where(Zone.name == zone)) or Zone(name=zone)
        db.add(z); db.flush()
        code = f"BIN{i:02d}"
        if db.scalar(select(Bin).where(Bin.code == code)):
            continue
        key = f"demo-key-{code}"
        keys[code] = key
        b = Bin(code=code, name=name, zone_id=z.id, lat=lat, lng=lng, device_key_hash=hash_device_key(key),
                last_collected_at=now - timedelta(hours=history_hours))
        db.add(b); db.flush()
        level = random.uniform(2, 8)
        for h in range(history_hours * 4):  # every 15 min
            level = min(100.0, level + rate / 4 + random.uniform(-0.4, 0.4))
            db.add(BinReading(bin_id=b.id, fill_level=round(level, 1),
                              recorded_at=now - timedelta(minutes=15 * (history_hours * 4 - h))))
        b.fill_level = round(level, 1)
        labels = [l for l, w in mix.items() for _ in range(w)]
        for _ in range(40):
            l = random.choice(labels)
            db.add(WasteClassification(bin_id=b.id, label=l, confidence=round(random.uniform(.7, .98), 2),
                                       scores={l: 0.9}, image_sha256="seed",
                                       created_at=now - timedelta(minutes=random.randint(0, 600))))
    db.commit()
    return keys


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        k = seed(db)
    print("Seeded. Admin login: admin /", settings.admin_password)
    for code, key in k.items():
        print(f"  {code}: X-Device-Key={key}")
