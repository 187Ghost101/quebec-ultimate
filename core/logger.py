"""OSIN CHAIN QUEBEC ULTIMATE - Logger - Ghost1o1"""
import logging
import sys
from pathlib import Path
from datetime import datetime

COLORS = {
    'DEBUG': '\033[36m', 'INFO': '\033[32m', 'WARNING': '\033[33m',
    'ERROR': '\033[31m', 'CRITICAL': '\033[35m',
}

class ColoredFormatter(logging.Formatter):
    def format(self, record):
        color = COLORS.get(record.levelname, '')
        reset = '\033[0m'
        time_str = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        msg = (
            f"\033[90m{time_str}\033[0m "
            f"{color}[{record.levelname}]\033[0m "
            f"\033[37m{record.name}\033[0m: "
            f"{record.getMessage()}"
        )
        if record.exc_info:
            msg += '\n' + self.formatException(record.exc_info)
        return msg


def setup_logger(name: str = "osin_chain", level: int = logging.INFO,
                 log_file: Path = None) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(ColoredFormatter())
    console.setLevel(level)
    logger.addHandler(console)
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'))
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
    return logger


from config import config
logger = setup_logger("osin_chain", log_file=config.LOGS_DIR / "osin.log")