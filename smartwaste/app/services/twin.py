"""Digital twin: assembles live virtual state of the whole campus."""
from datetime import timedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..database import utcnow
from ..models import Bin, WasteClassification, Zone
from .prediction import predict


def status_of(level: float) -> str:
    return "green" if level < 50 else "yellow" if level < 80 else "red"


def composition(db: Session, bin_ids: list[int] | None = None, hours: int = 24) -> dict[int, dict[str, float]]:
    since = utcnow() - timedelta(hours=hours)
    q = (select(WasteClassification.bin_id, WasteClassification.label, func.count())
         .where(WasteClassification.created_at >= since, WasteClassification.bin_id.is_not(None))
         .group_by(WasteClassification.bin_id, WasteClassification.label))
    if bin_ids is not None:
        q = q.where(WasteClassification.bin_id.in_(bin_ids))
    counts: dict[int, dict[str, int]] = {}
    for bid, label, n in db.execute(q):
        counts.setdefault(bid, {})[label] = n
    return {bid: {k: round(100 * v / sum(c.values()), 1) for k, v in c.items()} for bid, c in counts.items()}


def bin_state(b: Bin, comp: dict, pred: dict) -> dict:
    return {"id": b.id, "code": b.code, "name": b.name, "zone": b.zone.name, "lat": b.lat, "lng": b.lng,
            "fill_level": round(b.fill_level, 1), "status": status_of(b.fill_level),
            "composition": comp.get(b.id, {}), "prediction": pred,
            "last_collected_at": b.last_collected_at.isoformat() if b.last_collected_at else None,
            "updated_at": b.updated_at.isoformat()}


def snapshot(db: Session) -> dict:
    bins = db.scalars(select(Bin).join(Zone).order_by(Zone.name, Bin.code)).all()
    comp = composition(db)
    states = [bin_state(b, comp, predict(db, b)) for b in bins]
    zones: dict[str, list] = {}
    for s in states:
        zones.setdefault(s["zone"], []).append(s)
    return {
        "generated_at": utcnow().isoformat(),
        "kpis": {"total_bins": len(states),
                 "critical_bins": sum(s["status"] == "red" for s in states),
                 "avg_fill": round(sum(s["fill_level"] for s in states) / len(states), 1) if states else 0},
        "zones": [{"name": z, "bins": v} for z, v in zones.items()],
    }
