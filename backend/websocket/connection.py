from typing import List
from fastapi import WebSocket
from backend.utils.timezone_helper import ist_now

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WS] Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"[WS] Client disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_json(self, data: dict, websocket: WebSocket):
        try:
            await websocket.send_json(data)
        except Exception:
            # Handle disconnected sockets gracefully during write
            self.disconnect(websocket)

    async def broadcast_json(self, data: dict):
        # Create a copy of connections list to avoid modifying during iteration
        for connection in list(self.active_connections):
            try:
                await connection.send_json(data)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()
