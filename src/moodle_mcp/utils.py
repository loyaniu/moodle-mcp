import json
import os

from dotenv import load_dotenv

from .logger import logger

ENV_LOADED = False

DEBUG_DIR_ENV = "MOODLE_MCP_DEBUG_DIR"


def to_json_file(data, filename, folder=None):
    """Dump raw API data to a JSON file for debugging.

    Opt-in only: nothing is written unless ``folder`` is given or the
    ``MOODLE_MCP_DEBUG_DIR`` environment variable is set. A failed write is
    logged as a warning and never raises, so it cannot break a tool call.
    """
    folder = folder or getenv(DEBUG_DIR_ENV)
    if not folder:
        return

    path = os.path.join(folder, filename)
    try:
        os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except OSError as e:
        logger.warning(f"Could not write debug file {path}: {e}")


def getenv(key: str, default: str = None) -> str:
    global ENV_LOADED

    if not ENV_LOADED:
        load_dotenv()
        ENV_LOADED = True

    return os.getenv(key, default)
