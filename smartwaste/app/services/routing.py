"""Collection route: priority bins only, greedy nearest-neighbour from depot."""
import math
from ..config import settings


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    R = 6371.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dphi, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def plan_route(bins: list[dict], threshold: float = 70.0) -> dict:
    todo = [b for b in bins if b["fill_level"] >= threshold]
    pos = (settings.depot_lat, settings.depot_lng)
    stops, total = [], 0.0
    while todo:
        # urgency-weighted distance: fuller bins look "closer"
        nxt = min(todo, key=lambda b: haversine_km(pos, (b["lat"], b["lng"])) * (1.5 - b["fill_level"] / 200))
        d = haversine_km(pos, (nxt["lat"], nxt["lng"]))
        total += d
        stops.append({"order": len(stops) + 1, "bin_id": nxt["id"], "code": nxt["code"], "name": nxt["name"],
                      "fill_level": nxt["fill_level"], "lat": nxt["lat"], "lng": nxt["lng"],
                      "leg_km": round(d, 2)})
        pos = (nxt["lat"], nxt["lng"])
        todo.remove(nxt)
    total += haversine_km(pos, (settings.depot_lat, settings.depot_lng)) if stops else 0
    return {"threshold": threshold, "stops": stops, "total_km": round(total, 2),
            "skipped_bins": len(bins) - len(stops)}
