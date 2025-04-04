import json
import os

from dotenv import load_dotenv

ENV_LOADED = False


def to_json_file(data, filename, folder="output"):
    if not os.path.exists(folder):
        os.makedirs(folder)

    with open(f"{folder}/{filename}", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def getenv(key: str, default: str = None) -> str:
    global ENV_LOADED

    if not ENV_LOADED:
        load_dotenv()
        ENV_LOADED = True

    return os.getenv(key, default)
