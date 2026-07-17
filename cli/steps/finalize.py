import os
from pathlib import Path

import yaml

from ..ui import step_header, success, info
from ..inputs.accepted_inputs import PROVIDERS

_KEY_FILE = Path(".tollgate.key")
_CONFIG_PATH = Path("config.yaml")
_KEY_TMP = Path(".tollgate.key.tmp")
_CONFIG_TMP = Path("config.yaml.tmp")


def _cleanup_tmp():
    _KEY_TMP.unlink(missing_ok=True)
    _CONFIG_TMP.unlink(missing_ok=True)


def run(config: dict) -> dict:
    step_header(6, "Writing Configuration", total=6)

    data = {
        "MODELS": {
            meta["config_key"].upper(): {
                "API_KEY": config["api_keys"].get(meta["config_key"], "NOT_CONFIGURED")
            }
            for meta in PROVIDERS.values()
        },
        "EMBEDDING": {
            "MODEL_NAME": config["embedding_model"],
        },
        "RATE_LIMITER": {k.upper(): v for k, v in config["rate_limiter"].items()},
        "GATEWAY": {
            "DEFAULT_MODEL": config["default_model"],
            "DEFAULT_TEMPERATURE": config["default_temperature"],
        },
        "ADMIN": {
            "USERNAME": config["admin"]["username"],
            "PASSWORD_HASH": config["admin"]["password_hash"],
        },
    }

    try:
        _KEY_TMP.write_bytes(config["_fernet_key"])
        _KEY_TMP.chmod(0o600)

        with open(_CONFIG_TMP, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        os.replace(_KEY_TMP, _KEY_FILE)
        os.replace(_CONFIG_TMP, _CONFIG_PATH)

    except Exception:
        _cleanup_tmp()
        raise

    info(f"config.yaml written to [dim]{_CONFIG_PATH.resolve()}[/dim]")
    success("Setup complete — start the gateway with [bold]tollgate start[/bold]")

    return config
