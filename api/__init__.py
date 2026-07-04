"""OSIN CHAIN QUEBEC ULTIMATE - API - Ghost1o1"""
from .routes import create_router
from .websocket import setup_websocket, ws_manager

setup_routes = create_router

__all__ = ["create_router", "setup_routes", "setup_websocket", "ws_manager"]
