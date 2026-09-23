import base64
import hashlib
import os
from pathlib import Path
from cryptography.fernet import Fernet
from rich import print

_KEY_FILE = Path(".tollgate.key")


def _load_key() -> bytes:
    if not _KEY_FILE.exists():
        raise FileNotFoundError(
            ".tollgate.key not found. Run 'tollgate init' to set up the gateway."
        )
    return _KEY_FILE.read_bytes().strip()


def get_fernet() -> Fernet:
    return Fernet(_load_key())


def encrypt_value(value: str) -> str:
    return get_fernet().encrypt(value.encode()).decode()


def encrypt_with_key(value: str, key: bytes) -> str:
    return Fernet(key).encrypt(value.encode()).decode()


def decrypt_value(token: str) -> str:
    return get_fernet().decrypt(token.encode()).decode()


def create_key(force: bool = False):
    if not force and _KEY_FILE.exists():
        content: bytes = _KEY_FILE.read_bytes().strip()
        content_valid: bool = _verify_file_contents(content)
        if content_valid:
            return

    key = Fernet.generate_key()
    _KEY_FILE.write_bytes(key)
    _KEY_FILE.chmod(0o600)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return base64.b64encode(salt + key).decode()


def verify_password(password: str, stored_hash: str) -> bool:
    decoded = base64.b64decode(stored_hash.encode())
    salt, stored_key = decoded[:16], decoded[16:]
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return key == stored_key


def _verify_file_contents(content: bytes) -> bool:
    if content:
        try:
            Fernet(content)
            print("[green]A valid encryption key already exists...[/green]")
            return True
        except Exception as e:
            print("[red]Sorry, an encryption file exists but the content is corrupted. Please contact the admin[/red]")
            print(e)
    return False
