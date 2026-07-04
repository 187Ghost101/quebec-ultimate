"""OSIN CHAIN QUEBEC ULTIMATE — Config - Ghost1o1"""
import os
from pathlib import Path
from dataclasses import dataclass, field

BASE_DIR = Path(__file__).parent.resolve()


@dataclass
class Config:
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "neo4j")
    USE_NEO4J: str = os.getenv("USE_NEO4J", "auto")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    USE_CELERY: str = os.getenv("USE_CELERY", "auto")
    APP_NAME: str = "OSIN CHAIN QUEBEC ULTIMATE"
    APP_VERSION: str = "1.0.0-ghost"
    AUTHOR: str = "Ghost1o1"
    SECRET_KEY: str = "osin-chain-quebec-ultimate-ghost1o1"
    BASE_DIR: Path = BASE_DIR
    EXPORTS_DIR: Path = field(default_factory=lambda: BASE_DIR / "exports")
    LOGS_DIR: Path = field(default_factory=lambda: BASE_DIR / "logs")
    DATA_DIR: Path = field(default_factory=lambda: BASE_DIR / "data")
    MAX_UPLOAD_MB: int = 16
    MODULE_TIMEOUT_SEC: int = 30
    RATE_LIMIT_PER_IP: int = 30
    RATE_LIMIT_WINDOW: int = 60

    def __post_init__(self):
        for d in [self.EXPORTS_DIR, self.LOGS_DIR, self.DATA_DIR]:
            d.mkdir(parents=True, exist_ok=True)

    def available_apis(self):
        """List which optional APIs have keys configured."""
        keys = {
            "HIBP": bool(os.getenv("HIBP_API_KEY")),
            "NUMVERIFY": bool(os.getenv("NUMVERIFY_API_KEY")),
            "SHODAN": bool(os.getenv("SHODAN_API_KEY")),
            "VIRUSTOTAL": bool(os.getenv("VIRUSTOTAL_API_KEY")),
            "TINEYE": bool(os.getenv("TINEYE_API_KEY")),
            "YANDEX_VISION": bool(os.getenv("YANDEX_VISION_KEY")),
            "INTELX": bool(os.getenv("INTELX_API_KEY")),
        }
        active = [k for k, v in keys.items() if v]
        return {"configured": active, "missing": [k for k, v in keys.items() if not v]}


config = Config()


def has_neo4j() -> bool:
    if config.USE_NEO4J == "false":
        return False
    try:
        from neo4j import GraphDatabase
        d = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD), connection_timeout=2)
        d.verify_connectivity()
        d.close()
        return True
    except Exception:
        return False


def has_redis() -> bool:
    try:
        import redis
        return redis.from_url(config.REDIS_URL, socket_connect_timeout=2).ping()
    except Exception:
        return False
