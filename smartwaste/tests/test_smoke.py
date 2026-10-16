import io, os, tempfile
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/t.db"
from fastapi.testclient import TestClient
from PIL import Image
from app.main import app
from app.database import SessionLocal
from seed import seed


def test_flow():
    with TestClient(app) as c:
        with SessionLocal() as db:
            keys = seed(db)
        assert c.get("/twin").status_code == 401
        tok = c.post("/auth/login", data={"username": "admin", "password": "admin123"}).json()["access_token"]
        H = {"Authorization": f"Bearer {tok}"}
        assert c.post("/auth/login", data={"username": "admin", "password": "x"}).status_code == 401

        t = c.get("/twin", headers=H).json()
        assert t["kpis"]["total_bins"] == 4

        # IoT ingestion + wrong key
        D = {"X-Device-Key": keys["BIN02"]}
        assert c.post("/devices/readings", json={"fill_level": 95}, headers=D).json()["status"] == "red"
        assert c.post("/devices/readings", json={"fill_level": 5}, headers={"X-Device-Key": "bad"}).status_code == 401
        assert c.post("/devices/readings", json={"fill_level": 150}, headers=D).status_code == 422

        # CV
        buf = io.BytesIO(); Image.new("RGB", (64, 64), (30, 60, 200)).save(buf, "PNG")
        r = c.post("/classify", files={"image": ("a.png", buf.getvalue(), "image/png")},
                   data={"bin_code": "BIN02"}, headers=H)
        assert r.status_code == 200 and r.json()["label"] in ["plastic", "paper", "organic", "metal", "hazardous"]
        assert c.post("/classify", files={"image": ("a.txt", b"hi", "text/plain")}, headers=H).status_code == 415
        assert c.post("/classify", files={"image": ("a.png", b"notimage", "image/png")}, headers=H).status_code == 400

        # twin / prediction / route / AI
        assert c.get("/bins/1/prediction", headers=H).json()["rate_per_hour"] is not None
        route = c.get("/routes/collection?threshold=50", headers=H).json()
        assert route["stops"][0]["fill_level"] >= 50
        assert "recommendation" in c.post("/ai/recommendations/2", headers=H).json()
        assert "REPORT" in c.post("/ai/report", headers=H).json()["report"]

        # collection resets level; admin-only creation
        assert c.post("/collections", json={"bin_id": 2, "weight_kg": 12}, headers=H).status_code == 201
        assert c.get("/bins/2", headers=H).json()["fill_level"] == 0
        with c.websocket_connect(f"/ws/twin?token={tok}") as ws:
            c.post("/devices/readings", json={"fill_level": 10}, headers=D)
