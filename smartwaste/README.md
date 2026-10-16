# SmartWaste AI – Backend (Computer Vision + Digital Twin + GenAI)

## Architecture
```
 ESP32 / Simulator ──(X-Device-Key)──► POST /devices/readings ─┐
 Camera / Upload   ──(JWT or key)────► POST /classify (CV) ────┤
                                                               ▼
                       FastAPI ──► SQLAlchemy ──► SQLite (dev) / PostgreSQL (prod)
                         │   services: vision · twin · prediction · routing · genai
                         ├──► WebSocket /ws/twin  (live push to dashboard)
                         └──► Claude API (grounded recommendations & reports; offline fallback)
```
| Layer | Tech | Why |
|---|---|---|
| API | FastAPI | async, auto docs at `/docs`, validation via Pydantic |
| DB | SQLAlchemy 2 | same code on SQLite (zero-setup) and Postgres (docker) |
| CV | pluggable (`mock` / Hugging Face) | demo never breaks; swap in a real model with 2 env vars |
| Twin | `bins` table = live state, `bin_readings` = time series | snapshot built per request, pushed on change |
| Forecast | least-squares slope on last 6 h | explainable, no training needed |
| Routing | greedy nearest-neighbour, urgency-weighted | simple, visible on a map |
| GenAI | Claude with JSON-grounded prompt | data is delimited and treated as data, not instructions |

### Database schema
`users` · `zones` 1─* `bins` 1─* `bin_readings` · `bins` 1─* `classifications` · `bins` 1─* `collections` · `ai_outputs`
Indexes on `(bin_id, recorded_at)` and `(bin_id, created_at)` keep time-window queries fast.

### Security
- Passwords: PBKDF2-SHA256 (200k iters, salt). Dashboard users: JWT. Admin-only bin/zone creation.
- Devices: per-bin secret key, only its SHA-256 is stored; a device can only classify for its own bin.
- Uploads: type allow-list, 5 MB cap, image validated by Pillow. Input ranges validated by Pydantic.
- CORS allow-list, secrets via `.env`, non-root Docker user.

## Run
```bash
cp .env.example .env            # set SECRET_KEY (32+ chars), optionally ANTHROPIC_API_KEY
pip install -r requirements.txt
python seed.py                  # demo campus + admin + device keys
uvicorn app.main:app --reload   # docs: http://localhost:8000/docs
python simulator.py BIN02 demo-key-BIN02   # live sensor updates
pytest                          # smoke test
# or: docker compose up --build   (Postgres)
```

## Key endpoints
| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/login` | form: username/password → JWT |
| GET | `/twin` | full campus digital twin + KPIs |
| GET | `/bins`, `/bins/{id}`, `/bins/{id}/history`, `/bins/{id}/prediction` | bin state / forecast |
| POST | `/devices/readings` | sensor push (`X-Device-Key`) |
| POST | `/classify` | multipart `image` (+`bin_code`) → category + scores |
| POST | `/collections` | mark collected (resets bin) |
| GET | `/routes/collection?threshold=70` | ordered pickup route |
| POST | `/ai/recommendations/{id}`, `/ai/report` | GenAI outputs |
| WS | `/ws/twin?token=JWT` | live `bin_update` events |

## Real CV model
`pip install transformers torch`, then set `VISION_BACKEND=hf` and `VISION_MODEL=<HF image-classification model id>`; raw labels are mapped to plastic/paper/organic/metal/hazardous in `services/vision.py`.

## Before going beyond a hackathon
Alembic migrations, rate limiting, Redis pub/sub for multi-worker WebSockets, change default `ADMIN_PASSWORD`, HTTPS.
