from __future__ import annotations

import socket
import subprocess
import time

from rich.prompt import Prompt, Confirm

from ..ui import console, step_header, success, warn, error, info
from src.utils.crypto import encrypt_with_key

_NOT_CONFIGURED = "NOT_CONFIGURED"


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except (ConnectionRefusedError, OSError):
        return False


def _is_localhost(host: str) -> bool:
    return host in ("localhost", "127.0.0.1", "::1")


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


def _check_reachability(name: str, host: str, port: int, on_localhost_missing) -> None:
    if _port_open(host, port):
        success(f"{name} [dim]{host}:{port}[/dim] — reachable")
        return

    if _is_localhost(host):
        warn(f"{name} not detected on {host}:{port} — attempting to start locally...")
        on_localhost_missing()
    else:
        # A failed probe against a real managed endpoint could just be a
        # firewall/security-group rule blocking this machine, not proof the
        # service is actually down - warn, don't hard-fail the wizard over it.
        warn(
            f"Could not reach {name} at {host}:{port} — this may just be a "
            "firewall or security-group rule, not necessarily a real problem. "
            "Double-check host/port/credentials if the gateway can't connect later."
        )


def _collect_redis(config: dict) -> dict:
    console.print("\n  [bold white]Redis[/bold white] [dim](exact cache, rate limiting, job queue)[/dim]")
    info("Running it yourself (local or containerized) or pointing at a managed service (AWS ElastiCache, Redis Cloud, ...) both work.")

    host = Prompt.ask("\n  [bold cyan]Host[/bold cyan]", default="localhost")
    port = Prompt.ask("  [bold cyan]Port[/bold cyan]", default="6379")
    password_input = Prompt.ask(
        "  [bold cyan]Password[/bold cyan] [dim](press Enter if none - e.g. a local dev instance)[/dim]",
        password=True,
        default="",
    )
    tls = Confirm.ask(
        "  [bold cyan]Use TLS?[/bold cyan] [dim](usually yes for managed services like ElastiCache/Redis Cloud)[/dim]",
        default=False,
    )
    password = encrypt_with_key(password_input, config["_fernet_key"]) if password_input else _NOT_CONFIGURED

    def _start_local_redis():
        if _try_start_redis():
            success("Redis started")
        else:
            error(
                "Redis could not start automatically.\n"
                "  [dim]Run:[/dim]  [bold]redis-server[/bold]  in a separate terminal, then re-run init."
            )

    _check_reachability("Redis", host, int(port), _start_local_redis)

    config["redis"] = {"host": host, "port": port, "password": password, "tls": str(tls).lower()}
    return config


def _collect_qdrant(config: dict) -> dict:
    console.print("\n  [bold white]Qdrant[/bold white] [dim](semantic cache)[/dim]")
    info("Same idea - a local/containerized instance or a managed one (Qdrant Cloud) both work.")

    host = Prompt.ask("\n  [bold cyan]Host[/bold cyan]", default="localhost")
    port = Prompt.ask("  [bold cyan]Port[/bold cyan]", default="6333")
    api_key_input = Prompt.ask(
        "  [bold cyan]API key[/bold cyan] [dim](press Enter if none - e.g. a local dev instance)[/dim]",
        password=True,
        default="",
    )
    https = Confirm.ask(
        "  [bold cyan]Use HTTPS?[/bold cyan] [dim](usually yes for Qdrant Cloud)[/dim]",
        default=False,
    )
    api_key = encrypt_with_key(api_key_input, config["_fernet_key"]) if api_key_input else _NOT_CONFIGURED

    def _start_local_qdrant():
        if _try_start_qdrant():
            success("Qdrant started via Docker")
        else:
            error(
                "Qdrant could not start automatically.\n"
                "  [dim]Run:[/dim]  [bold]docker run -d -p 6333:6333 qdrant/qdrant[/bold]"
            )

    _check_reachability("Qdrant", host, int(port), _start_local_qdrant)

    config["qdrant"] = {"host": host, "port": port, "api_key": api_key, "https": str(https).lower()}
    return config


def run(config: dict) -> dict:
    step_header(3, "Infrastructure Services", total=8)

    config = _collect_redis(config)
    config = _collect_qdrant(config)

    return config
