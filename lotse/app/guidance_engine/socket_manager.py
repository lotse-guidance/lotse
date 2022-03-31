from typing import List

from pydantic import BaseModel
from starlette.websockets import WebSocket


class ConnectionManager:
    def __init__(self):
        self.connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)

    async def broadcast(self, message: BaseModel):
        print("Serializing message to JSON: ", message.json(exclude={'action'}))
        for connection in self.connections:
            # if connection is not websocket:
            await connection.send_text(message.json(exclude={'action'}))

    async def disconnect(self, websocket: WebSocket):
        try:
            self.connections.remove(websocket)
            await websocket.close()
        except RuntimeError:
            print("\n\nERROR ON DISCONNECT\n\n")
            pass


manager = ConnectionManager()


def get_connection_manager():
    return manager
