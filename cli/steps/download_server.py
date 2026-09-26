import platform
import tarfile
import zipfile
from pathlib import Path

import requests
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from ..ui import console, step_header, success, info

RELEASE_TAG = "llama-server-v1"
_RELEASE_BASE_URL = f"https://github.com/Vibhinn/tollgate-native/releases/download/{RELEASE_TAG}"

BINARY_NAME = "llama-server.exe" if platform.system() == "Windows" else "llama-server"


def _server_dir() -> Path:
    return Path(__file__).parent.parent.parent / "src" / "app" / "intelligence" / "server"


def _asset_name() -> str:
    system = platform.system()
    machine = platform.machine().lower()

    if system == "Darwin" and machine in ("arm64", "aarch64"):
        return "llama-server-macos-arm64.tar.gz"
    if system == "Linux" and machine in ("x86_64", "amd64"):
        return "llama-server-linux-x86_64.tar.gz"
    if system == "Linux" and machine in ("arm64", "aarch64"):
        return "llama-server-linux-arm64.tar.gz"
    if system == "Windows" and machine in ("x86_64", "amd64"):
        return "llama-server-windows-x86_64.zip"

    raise RuntimeError(
        f"No prebuilt llama-server for {system} {machine} yet. "
        "See https://github.com/Vibhinn/tollgate-native to build one for this platform."
    )


def _extract(archive_path: Path, dest_dir: Path) -> None:
    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(dest_dir)
    else:
        with tarfile.open(archive_path) as tf:
            tf.extractall(dest_dir)


def run(config: dict) -> dict:
    step_header(2, "Routing Intelligence Server", total=7)

    server_dir = _server_dir()
    binary_path = server_dir / BINARY_NAME

    if binary_path.exists():
        success(f"llama-server already present at [dim]{binary_path}[/dim]")
        return config

    asset_name = _asset_name()
    server_dir.mkdir(parents=True, exist_ok=True)
    info(f"Downloading [bold]{asset_name}[/bold] — this runs once")

    response = requests.get(f"{_RELEASE_BASE_URL}/{asset_name}", stream=True, timeout=30)
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))

    archive_path = server_dir / asset_name
    with Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Downloading...", total=total or None)
        with open(archive_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                progress.update(task, advance=len(chunk))

    _extract(archive_path, server_dir)
    archive_path.unlink()

    if binary_path.exists():
        binary_path.chmod(binary_path.stat().st_mode | 0o111)

    success(f"llama-server saved to [dim]{server_dir}[/dim]")
    return config
