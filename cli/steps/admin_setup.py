from rich.prompt import Prompt

from ..ui import step_header, success, error, info
from src.utils.crypto import encrypt_with_key, hash_password, verify_password

__all__ = ["run", "verify_password"]


def run(config: dict) -> dict:
    step_header(3, "Admin Credentials", total=6)

    info("These credentials protect gateway administration. Store them safely.")

    username = Prompt.ask("\n  [bold cyan]Admin username[/bold cyan]")

    while True:
        password = Prompt.ask("  [bold cyan]Password[/bold cyan]", password=True)
        confirm = Prompt.ask("  [bold cyan]Confirm password[/bold cyan]", password=True)
        if password == confirm:
            break
        error("Passwords do not match — try again")

    config["admin"] = {
        "username": encrypt_with_key(username, config["_fernet_key"]),
        "password_hash": hash_password(password),
    }

    success("Admin credentials encrypted and ready to write")
    return config
