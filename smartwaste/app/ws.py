from fastapi import WebSocket


class Manager:
    def __init__(self):
        self.clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket):
        self.clients.discard(ws)

    async def broadcast(self, payload: dict):
        for ws in list(self.clients):
            try:
                await ws.send_json(payload)
            except Exception:
                self.disconnect(ws)


manager = Manager()
