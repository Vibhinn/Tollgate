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
    step_header(7, "Writing Configuration", total=7)

    data = {
        "models": {
            **{
                meta["config_key"].lower(): {
                    "api_key": config["api_keys"].get(meta["config_key"], "NOT_CONFIGURED")
                }
                for meta in PROVIDERS.values()
            },
            "self_hosted": config.get("self_hosted_models", {}),
        },
        "embedding": {
            "model_name": config["embedding_model"],
        },
        "rate_limiter": config["rate_limiter"],
        "gateway": {
            "default_model": config["default_model"],
            "default_temperature": config["default_temperature"],
        },
        "admin": {
            "username": config["admin"]["username"],
            "password_hash": config["admin"]["password_hash"],
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
