"""Fill-level forecasting: least-squares slope over recent readings."""
from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import utcnow
from ..models import Bin, BinReading

WINDOW_HOURS = 6


def predict(db: Session, b: Bin) -> dict:
    since = utcnow() - timedelta(hours=WINDOW_HOURS)
    if b.last_collected_at and b.last_collected_at > since:
        since = b.last_collected_at  # ignore pre-collection data (level reset)
    rows = db.execute(
        select(BinReading.recorded_at, BinReading.fill_level)
        .where(BinReading.bin_id == b.id, BinReading.recorded_at >= since)
        .order_by(BinReading.recorded_at)
    ).all()
    result = {"current_level": round(b.fill_level, 1), "rate_per_hour": None,
              "hours_to_full": None, "collection_recommended": b.fill_level >= 80}
    if len(rows) < 3:
        return result
    t0 = rows[0][0]
    xs = [(t - t0).total_seconds() / 3600 for t, _ in rows]
    ys = [y for _, y in rows]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    var = sum((x - mx) ** 2 for x in xs)
    if var == 0:
        return result
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var
    result["rate_per_hour"] = round(slope, 2)
    if slope > 0.05:
        hrs = max(0.0, (100 - b.fill_level) / slope)
        result["hours_to_full"] = round(hrs, 1)
        result["collection_recommended"] = b.fill_level >= 80 or hrs <= 4
    return result
