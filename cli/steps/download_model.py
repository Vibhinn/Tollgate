from pathlib import Path

import requests
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from ..ui import console, step_header, success, warn, info

MODEL_FILENAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"

_MODEL_URL = (
    f"https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/{MODEL_FILENAME}?download=true"
)


def _model_dir() -> Path:
    return Path(__file__).parent.parent.parent / "src" / "app" / "intelligence" / "model"


def run(config: dict) -> dict:
    step_header(1, "Routing Intelligence Model", total=6)

    model_dir = _model_dir()
    model_path = model_dir / MODEL_FILENAME

    if model_path.exists():
        success(f"Model already present at [dim]{model_path}[/dim]")
        config["model_path"] = str(model_path)
        return config

    model_dir.mkdir(parents=True, exist_ok=True)
    info(f"Downloading [bold]{MODEL_FILENAME}[/bold] (~1 GB) — this runs once")

    response = requests.get(_MODEL_URL, stream=True, timeout=30)
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))

    with Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Downloading...", total=total or None)
        with open(model_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                progress.update(task, advance=len(chunk))

    success(f"Model saved to [dim]{model_path}[/dim]")
    config["model_path"] = str(model_path)
    return config



