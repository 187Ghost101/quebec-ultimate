"""OSIN CHAIN QUEBEC ULTIMATE — WebSocket Manager
Ghost1o1 — Real-time events: entity, chain_step, footprint_event, geo_update.
"""
import json
import asyncio
from typing import Dict, Any
from fastapi import WebSocket, WebSocketDisconnect
from core.logger import logger


class WebSocketManager:
    def __init__(self):
        self._connections: Dict[str, Dict] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self._connections[session_id] = {"ws": websocket, "connected_at": asyncio.get_event_loop().time()}
        logger.info(f"[WS] Connected: {session_id}")
        await self.send(session_id, {"event": "connected", "session_id": session_id})

    async def disconnect(self, session_id: str):
        self._connections.pop(session_id, None)
        logger.info(f"[WS] Disconnected: {session_id}")

    async def send(self, session_id: str, data: Dict):
        if session_id in self._connections:
            try:
                await self._connections[session_id]["ws"].send_text(json.dumps(data, default=str))
            except Exception as e:
                logger.warning(f"[WS] send fail: {e}")


    async def broadcast_all(self, data):
        """Broadcast payload to all connected sessions (face_detected events)."""
        dead = []
        for sid, conn in self._connections.items():
            try:
                await conn["ws"].send_text(json.dumps(data, default=str))
            except Exception:
                dead.append(sid)
        for sid in dead:
            self._connections.pop(sid, None)

    async def broadcast_footprint_event(self, session_id: str, event_type: str,
                                         entity: Dict = None, geo: Dict = None,
                                         snapshot_id: str = None,
                                         extra: Dict = None):
        """Broadcast a footprint event (entity, geo, snapshot)."""
        payload = {"event": event_type, "session_id": session_id}
        if entity:
            payload["entity"] = entity
        if geo:
            payload["geo"] = geo
        if snapshot_id:
            payload["snapshot_id"] = snapshot_id
        if extra:
            payload.update(extra)
        await self.send(session_id, payload)


ws_manager = WebSocketManager()


def setup_websocket(app, graph_manager=None, correlation_engine=None):
    @app.websocket("/ws/{session_id}")
    async def websocket_endpoint(websocket: WebSocket, session_id: str):
        await ws_manager.connect(websocket, session_id)
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    msg = json.loads(data)
                    if msg.get("action") == "ping":
                        await ws_manager.send(session_id, {"event": "pong"})
                    elif msg.get("action") == "get_graph":
                        if graph_manager and msg.get("entity_id"):
                            nb = graph_manager.get_neighborhood(msg["entity_id"], msg.get("depth", 3))
                            await ws_manager.send(session_id, {
                                "event": "graph_data",
                                "entity_id": msg["entity_id"],
                                "nodes": nb.get("nodes", []),
                                "edges": nb.get("edges", []),
                            })
                except Exception:
                    pass
        except WebSocketDisconnect:
            await ws_manager.disconnect(session_id)