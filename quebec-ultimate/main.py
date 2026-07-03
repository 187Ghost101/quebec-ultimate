"""OSIN CHAIN QUEBEC ULTIMATE — Main Entry - Ghost1o1
FastAPI + WebSocket + NetworkX + Footprint + GeoManager.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

from config import config
from core.logger import logger
from core.rate_limiter import RateLimiter
from core.graph_manager import GraphManager
from core.dispatcher import InputDispatcher
from core.correlation_v2 import CorrelationEngine
from core.footprint import FootprintTracker
from core.geo import GeoManager
from api import setup_routes, setup_websocket, ws_manager


def create_app():
    app = FastAPI(
        title=config.APP_NAME,
        version=config.APP_VERSION,
        description="OSIN CHAIN QUEBEC ULTIMATE - Recon modulaire + Footprint + Movement",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    graph_manager = GraphManager()
    dispatcher = InputDispatcher()
    correlation_engine = CorrelationEngine(graph_manager)
    rate_limiter = RateLimiter(max_requests=config.RATE_LIMIT_PER_IP,
                                window=config.RATE_LIMIT_WINDOW)
    footprint_tracker = FootprintTracker()
    geo_manager = GeoManager()

    setup_routes(app, dispatcher, graph_manager, correlation_engine,
                 rate_limiter, ws_manager, footprint_tracker, geo_manager)
    setup_websocket(app, graph_manager, correlation_engine)

    frontend_dir = Path(__file__).parent / "frontend"
    if frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=str(frontend_dir / "static")), name="static")

        @app.get("/")
        async def root():
            idx = frontend_dir / "index.html"
            if idx.exists():
                return FileResponse(str(idx))
            return {"message": "frontend not built"}

        @app.get("/footprint")
        async def footprint_page():
            idx = frontend_dir / "footprint.html"
            if idx.exists():
                return FileResponse(str(idx))
            return {"message": "footprint view not built"}

    logger.info(f"{config.APP_NAME} v{config.APP_VERSION} ready")
    logger.info("Components: dispatcher, graph, correlation_v2, footprint, geo, ws")
    logger.info("ContentMiner module 13 (avatar pHash + bio link mining + GitHub API)")
    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("main:app", host=config.HOST, port=config.PORT,
                reload=config.DEBUG, log_level="info")