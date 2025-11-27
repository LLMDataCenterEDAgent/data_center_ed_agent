# utils/logging.py
import logging, os
from datetime import datetime

def get_logger(name):
    if not os.path.exists("logs"):
        os.makedirs("logs")

    log_file = f"logs/{datetime.now().strftime('%Y%m%d')}.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    ch = logging.StreamHandler()
    fh = logging.FileHandler(log_file, encoding="utf-8")

    fmt = logging.Formatter("[%(asctime)s] %(name)s: %(message)s")
    ch.setFormatter(fmt)
    fh.setFormatter(fmt)

    logger.addHandler(ch)
    logger.addHandler(fh)

    return logger