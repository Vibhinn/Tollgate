import socket
import subprocess
import time

from ..ui import step_header, success, warn, error, info


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except (ConnectionRefusedError, OSError):
        return False


def _try_start_redis() -> bool:
    try:
        subprocess.Popen(
            ["redis-server", "--daemonize", "yes"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)
        return _port_open("localhost", 6379)
    except FileNotFoundError:
        return False


def _try_start_qdrant() -> bool:
    try:
        subprocess.Popen(
            ["docker", "run", "-d", "-p", "6333:6333", "-p", "6334:6334", "qdrant/qdrant"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(3)
        return _port_open("localhost", 6333)
    except FileNotFoundError:
        return False


def run(config: dict) -> dict:
    step_header(2, "Infrastructure Services", total=6)

    # Redis
    if _port_open("localhost", 6379):
        success("Redis  [dim]localhost:6379[/dim]  — running")
    else:
        warn("Redis not detected on :6379 — attempting to start...")
        if _try_start_redis():
            success("Redis started")
        else:
            error(
                "Redis could not start automatically.\n"
                "  [dim]Run:[/dim]  [bold]redis-server[/bold]  in a separate terminal, then re-run init."
            )

    # Qdrant
    if _port_open("localhost", 6333):
        success("Qdrant [dim]localhost:6333[/dim]  — running")
    else:
        warn("Qdrant not detected on :6333 — attempting to start via Docker...")
        if _try_start_qdrant():
            success("Qdrant started via Docker")
        else:
            error(
                "Qdrant could not start automatically.\n"
                "  [dim]Run:[/dim]  [bold]docker run -d -p 6333:6333 qdrant/qdrant[/bold]"
            )

    return config
