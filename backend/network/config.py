"""Settings for the Network module, read from the environment (and an optional git-ignored .env at the repo root)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
try:  # python-dotenv is optional; without it only real environment variables are used
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:  # noqa: BLE001
    pass


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


RETENTION_DAYS = _int("NETWORK_RETENTION_DAYS", 180)
SESSION_DAYS = 7
# Prototype switch: seeds clearly-labelled demonstration camps and demo staff accounts. Turn off for anything real.
DEMO_MODE = os.getenv("NETWORK_DEMO_MODE", "1") != "0"
GEMINI_MODEL = os.getenv("NETWORK_GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_DAILY_CAP = _int("NETWORK_GEMINI_DAILY_CAP", 200)  # protects the free quota; never switches to a paid service


def gemini_key() -> str:
    """Free-tier AI Studio key. Backend only; never sent to the browser."""
    return os.getenv("GEMINI_API_KEY", "").strip()


def data_dir() -> Path:
    return Path(os.getenv("RS_DATA_DIR") or ROOT / "data" / "app")
