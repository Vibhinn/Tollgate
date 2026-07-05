import base64
import hashlib
import os

from rich.prompt import Prompt

from ..ui import step_header, success, error, info
from src.utils.crypto import encrypt_with_key


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return base64.b64encode(salt + key).decode()


def verify_password(password: str, stored_hash: str) -> bool:
    decoded = base64.b64decode(stored_hash.encode())
    salt, stored_key = decoded[:16], decoded[16:]
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return key == stored_key


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
        "password_hash": _hash_password(password),
    }

    success("Admin credentials encrypted and ready to write")
    return config
