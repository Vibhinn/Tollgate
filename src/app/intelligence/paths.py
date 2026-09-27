from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("TOLLGATE_DATA_DIR")
    return Path(override) if override else Path(__file__).parent


def model_dir() -> Path:
    return data_dir() / "model"


def server_dir() -> Path:
    return data_dir() / "server"
