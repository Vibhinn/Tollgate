import stat

import pytest
from cryptography.fernet import Fernet

from src.utils import crypto


@pytest.fixture
def key_file(tmp_path, monkeypatch):
    path = tmp_path / ".tollgate.key"
    monkeypatch.setattr(crypto, "_KEY_FILE", path)
    return path


def test_load_key_raises_when_file_missing(key_file):
    with pytest.raises(FileNotFoundError):
        crypto.get_fernet()


def test_create_key_writes_a_valid_fernet_key(key_file):
    crypto.create_key()

    assert key_file.exists()
    Fernet(key_file.read_bytes().strip())  # does not raise


def test_create_key_sets_owner_only_permissions(key_file):
    crypto.create_key()

    mode = stat.S_IMODE(key_file.stat().st_mode)
    assert mode == 0o600


def test_create_key_does_not_overwrite_existing_valid_key(key_file):
    crypto.create_key()
    original = key_file.read_bytes()

    crypto.create_key()

    assert key_file.read_bytes() == original


def test_create_key_force_overwrites_existing_key(key_file):
    crypto.create_key()
    original = key_file.read_bytes()

    crypto.create_key(force=True)

    assert key_file.read_bytes() != original


def test_create_key_replaces_corrupted_key_file(key_file):
    key_file.write_bytes(b"not-a-valid-fernet-key")

    crypto.create_key()

    Fernet(key_file.read_bytes().strip())  # does not raise


def test_encrypt_decrypt_roundtrip(key_file):
    crypto.create_key()

    ciphertext = crypto.encrypt_value("super-secret-api-key")

    assert ciphertext != "super-secret-api-key"
    assert crypto.decrypt_value(ciphertext) == "super-secret-api-key"


def test_encrypt_with_key_uses_explicit_key_not_the_key_file(key_file):
    explicit_key = Fernet.generate_key()

    ciphertext = crypto.encrypt_with_key("value", explicit_key)

    assert Fernet(explicit_key).decrypt(ciphertext.encode()).decode() == "value"


def test_decrypt_fails_with_wrong_key(key_file):
    crypto.create_key()
    ciphertext = crypto.encrypt_value("secret")

    # Rotate to a different key file contents.
    key_file.write_bytes(Fernet.generate_key())

    with pytest.raises(Exception):
        crypto.decrypt_value(ciphertext)
