
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from .api import router
from .database import Base, SessionLocal, engine, get_db
from .security import _user_from_token
from .ws import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables when the application starts.
    Base.metadata.create_all(engine)
    yield


# Create the FastAPI application.
app = FastAPI(
    title="SmartWaste AI",
    version="1.0.0",
    lifespan=lifespan,
)


# CORS configuration: allow the local frontend to access the backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the existing API routes.
app.include_router(router)


# Health-check endpoint.
@app.get("/health", tags=["meta"])
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


# WebSocket endpoint for Digital Twin updates.
@app.websocket("/ws/twin")
async def ws_twin(ws: WebSocket, token: str = ""):
    with SessionLocal() as db:
        if not _user_from_token(token, db):
            await ws.close(code=4401)
            return

    await manager.connect(ws)

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)

