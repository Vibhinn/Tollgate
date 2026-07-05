import os
from configparser import ConfigParser
from pathlib import Path

from ..ui import step_header, success, info
from ..inputs.accepted_inputs import PROVIDERS

_KEY_FILE = Path(".tollgate.key")
_CONFIG_PATH = Path("config.ini")
_KEY_TMP = Path(".tollgate.key.tmp")
_CONFIG_TMP = Path("config.ini.tmp")


def _cleanup_tmp():
    _KEY_TMP.unlink(missing_ok=True)
    _CONFIG_TMP.unlink(missing_ok=True)


def run(config: dict) -> dict:
    step_header(6, "Writing Configuration", total=6)

    parser = ConfigParser()

    for provider_name, meta in PROVIDERS.items():
        section = meta["config_key"]
        parser[section] = {
            "API_KEY": config["api_keys"].get(section, "NOT_CONFIGURED"),
        }

    parser["EMBEDDING"] = {"MODEL_NAME": config["embedding_model"]}
    parser["RATE_LIMITER"] = config["rate_limiter"]
    parser["GATEWAY"] = {
        "DEFAULT_MODEL": config["default_model"],
        "DEFAULT_TEMPERATURE": config["default_temperature"],
    }
    parser["ADMIN"] = {
        "USERNAME": config["admin"]["username"],
        "PASSWORD_HASH": config["admin"]["password_hash"],
    }

    try:
        _KEY_TMP.write_bytes(config["_fernet_key"])
        _KEY_TMP.chmod(0o600)

        with open(_CONFIG_TMP, "w") as f:
            parser.write(f)

        # Atomic rename — interrupted between the two os.replace calls is safe:
        # guardrail checks config.ini[ADMIN], not the key file, so a key-only
        # partial state is treated as fresh install on retry.
        os.replace(_KEY_TMP, _KEY_FILE)
        os.replace(_CONFIG_TMP, _CONFIG_PATH)

    except Exception:
        _cleanup_tmp()
        raise

    info(f"config.ini written to [dim]{_CONFIG_PATH.resolve()}[/dim]")
    success("Setup complete — start the gateway with [bold]tollgate start[/bold]")

    return config
