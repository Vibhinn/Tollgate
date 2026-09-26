import sys
from pathlib import Path

import yaml
from rich.prompt import Prompt, Confirm

from ..ui import console, step_header, success, warn, error, info
from .admin_setup import verify_password
from src.utils.crypto import decrypt_value

_CONFIG_PATH = Path("config.yaml")


def _config_is_initialized() -> bool:
    if not _CONFIG_PATH.exists():
        return False
    with open(_CONFIG_PATH) as f:
        data = yaml.safe_load(f)
    return bool(data and data.get("admin", {}).get("password_hash"))


def _load_admin_credentials() -> tuple[str, str]:
    with open(_CONFIG_PATH) as f:
        data = yaml.safe_load(f)
    admin = data["admin"]
    return decrypt_value(admin["username"]), admin["password_hash"]


def run(config: dict) -> dict:
    if not _config_is_initialized():
        config["force_key_reset"] = False
        return config

    step_header(0, "Existing Configuration Detected", total=7)

    warn("A Tollgate configuration already exists on this machine.")
    console.print()
    console.print(
        "  [dim]To change a specific setting without wiping everything, run:[/dim]\n"
        "  [bold cyan]tollgate config --change[/bold cyan]\n"
    )

    user_confirmation: str = Prompt.ask("  [bold white]Are you sure you want to continue?[/bold white] [dim](Y/N)[/dim]")
    if user_confirmation.lower() != "y":
        info("No changes made. Run [bold cyan]tollgate config --change[/bold cyan] to update a specific setting.")
        sys.exit(0)

    info("To continue, verify your admin identity.")
    console.print()

    stored_username, password_hash = _load_admin_credentials()

    for attempt in range(3):
        entered_username = Prompt.ask("  [bold cyan]Admin username[/bold cyan]")
        entered_password = Prompt.ask("  [bold cyan]Admin password[/bold cyan]", password=True)

        if entered_username == stored_username and verify_password(entered_password, password_hash):
            success("Identity verified")
            break

        remaining = 2 - attempt
        if remaining > 0:
            error(f"Invalid credentials — {remaining} attempt{'s' if remaining > 1 else ''} remaining")
        else:
            error("Too many failed attempts. This issue will be reported. Exiting.")
            sys.exit(1)

    console.print()
    warn("[bold yellow]This will WIPE and completely replace all existing configuration.[/bold yellow]")
    warn("Your current API keys, admin credentials, and rate limits will be lost.")
    console.print()

    first_confirm = Confirm.ask(
        "  [bold red]Are you sure you want to start from scratch?[/bold red]",
        default=False,
    )
    if not first_confirm:
        info("Wise choice. Run [bold cyan]tollgate config --change[/bold cyan] to update a specific setting.")
        sys.exit(0)

    console.print()
    final = Prompt.ask(
        "  [bold red]Type [bold white]RESET[/bold white] to confirm full reconfiguration[/bold red]"
    )
    if final.strip() != "RESET":
        info("Reset cancelled. No changes were made.")
        sys.exit(0)

    config["force_key_reset"] = True
    success("Proceeding with full reset\n")
    return config