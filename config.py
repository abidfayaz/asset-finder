"""
Config - the single place where every setting lives.

Each setting is read from the ".env" file in this folder, and falls back to the
default written here when a line is missing. To change a setting, edit ".env" -
not this file. ".env.example" lists every setting with a short explanation.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# The folder this file sits in. Everything else is measured from here, so the
# app works no matter which directory you launch it from.
PROJECT_ROOT = Path(__file__).parent.resolve()

# Read .env into the environment (does nothing if the file is absent).
load_dotenv(PROJECT_ROOT / ".env")


def setting(name: str, default: str = "") -> str:
    """Read one setting from .env, or use the default."""
    return os.getenv(name, default)


def _path_setting(name: str, default: str) -> Path:
    """Read a folder/file setting and turn it into a full, absolute path."""
    raw = setting(name, default)
    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def _float_setting(name: str, default: float) -> float:
    """Read a decimal-number setting, with a clear error if it is not a number."""
    raw = setting(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        raise ValueError(
            f"Setting {name} in your .env should be a number, but it is '{raw}'."
        )


def _int_setting(name: str, default: int) -> int:
    """Read a whole-number setting, with a clear error if it is not a number."""
    raw = setting(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(
            f"Setting {name} in your .env should be a whole number, but it is '{raw}'."
        )


# ---------- Folders ----------
# The starting content folder. The real one is chosen inside the app, on the
# Processing log page, and remembered. The app only ever READS your files.
ASSETS_FOLDER = _path_setting("ASSETS_FOLDER", "./content")
# The searchable index (created automatically the first time files are read).
CHROMA_DIR = _path_setting("CHROMA_DIR", "./chroma_store_local")
# Small record of which files were read, and which failed and why.
STATUS_FILE = _path_setting("STATUS_FILE", "./index_status_local.json")

# ---------- The model runner (Unsloth or Ollama) ----------
# One model writes the "why it matched" sentences and reads pictures. It runs
# in a model runner on this computer, reached through its OpenAI-compatible
# address. The defaults suit Unsloth; see .env.example for Ollama.
LLM_BASE_URL = setting("LLM_BASE_URL", "http://127.0.0.1:8888/v1")
LLM_API_KEY = setting("LLM_API_KEY", "")
LLM_MODEL = setting("LLM_MODEL", "Qwen/Qwen3-VL-4B-Instruct-GGUF")
# How long to wait for the model before giving up on one request. Models on an
# ordinary computer can be slow, so this is generous.
LLM_TIMEOUT_SECONDS = _int_setting("LLM_TIMEOUT_SECONDS", 90)

# ---------- Picture reading ----------
# Left blank, pictures are read by the same model and runner as above - right
# for a model that reads text and pictures, such as Qwen3-VL. Fill these in only
# to read pictures with a different model.
VISION_BASE_URL = setting("VISION_BASE_URL", "") or LLM_BASE_URL
VISION_API_KEY = setting("VISION_API_KEY", "") or LLM_API_KEY
VISION_MODEL = setting("VISION_MODEL", "") or LLM_MODEL

# ---------- The search model (runs inside the app) ----------
# Turns text into "meaning fingerprints" for search. It downloads itself once,
# then works offline. An index only works with the model that built it.
EMBEDDING_MODEL = setting("EMBEDDING_MODEL", "mixedbread-ai/mxbai-embed-large-v1")

# Some embedding models find things better when what you TYPE (not the stored
# text) is given a short instruction first. mxbai-embed-large-v1 is one, and
# its authors publish the exact wording. Left blank, the prefix is chosen
# automatically from the model name.
_MXBAI_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
EMBEDDING_QUERY_PREFIX = setting("EMBEDDING_QUERY_PREFIX", "") or (
    _MXBAI_QUERY_PREFIX if "mxbai" in EMBEDDING_MODEL.lower() else ""
)

# ---------- Search tuning ----------
# How good a result must be to count as a match. Tuned for mxbai-embed-large-v1:
# a different search model scores differently and may need a new value.
SIMILARITY_THRESHOLD = _float_setting("SIMILARITY_THRESHOLD", 0.68)
TOP_K = _int_setting("TOP_K", 10)
# How many of the top results get an AI-written "why it matched" sentence.
# Kept small on purpose: each extra one makes the search wait longer.
WHY_TOP_N = _int_setting("WHY_TOP_N", 5)
# When nothing matches and "Show closest" is chosen in Settings, at most how
# many near results to show.
CLOSEST_FEW = _int_setting("CLOSEST_FEW", 3)
# Even the "closest few" must be genuinely near the search. Below this score an
# item is too far off to be worth showing at all, so "Show closest" can show
# fewer than CLOSEST_FEW, or nothing. Left unset, it sits a little below the
# match threshold: 0.60 with 0.68, where unrelated searches were measured to top
# out around 0.59 and genuine near misses to start at 0.62.
CLOSEST_THRESHOLD = _float_setting("CLOSEST_THRESHOLD",
                                   round(SIMILARITY_THRESHOLD - 0.08, 2))

# The only file types this app handles. Anything else is reported as
# "unsupported" in the processing log rather than silently ignored.
SUPPORTED_EXTENSIONS = {".pptx", ".pdf", ".png", ".jpg", ".jpeg"}
