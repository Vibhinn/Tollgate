import os
import sys
from pathlib import Path

import yaml
from rich.prompt import Prompt, Confirm
from rich.table import Table

from ..ui import console, success, warn, error, info
from ..steps.admin_setup import verify_password
from ..inputs.accepted_inputs import PROVIDERS
from src.utils.crypto import decrypt_value, encrypt_value

_CONFIG_PATH = Path("config.yaml")
_CONFIG_TMP = Path("config.yaml.tmp")
_NOT_CONFIGURED = "NOT_CONFIGURED"

_RESTART_NOTICE = (
    "[bold red]Restart the gateway for this change to take effect "
    "(config.yaml is only read once, at startup).[/bold red]"
)


def _require_config() -> dict:
    if not _CONFIG_PATH.exists():
        error("No config.yaml found. Run [bold]tollgate init[/bold] first.")
        sys.exit(1)
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _write_config(data: dict) -> None:
    try:
        with open(_CONFIG_TMP, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        os.replace(_CONFIG_TMP, _CONFIG_PATH)
    except Exception:
        _CONFIG_TMP.unlink(missing_ok=True)
        raise


def _verify_admin(data: dict) -> None:
    admin = data.get("admin", {})
    if not admin.get("password_hash"):
        error("No admin credentials found in config.yaml. Run [bold]tollgate init[/bold] first.")
        sys.exit(1)

    stored_username = decrypt_value(admin["username"])
    stored_hash = admin["password_hash"]

    for attempt in range(3):
        entered_username = Prompt.ask("  [bold cyan]Admin username[/bold cyan]")
        entered_password = Prompt.ask("  [bold cyan]Admin password[/bold cyan]", password=True)

        if entered_username == stored_username and verify_password(entered_password, stored_hash):
            success("Identity verified\n")
            return

        remaining = 2 - attempt
        if remaining > 0:
            error(f"Invalid credentials — {remaining} attempt{'s' if remaining > 1 else ''} remaining")
        else:
            error("Too many failed attempts. Exiting.")
            sys.exit(1)


def print_configuration() -> None:
    data = _require_config()

    console.print("\n[bold white]Configured models[/bold white]")
    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("Provider")
    table.add_column("Status")
    for provider, meta in data.get("models", {}).items():
        if provider == "self_hosted":
            continue
        configured = meta.get("api_key") != _NOT_CONFIGURED
        status = "[bold green]configured[/bold green]" if configured else "[dim]not configured[/dim]"
        table.add_row(provider, status)
    console.print(table)

    self_hosted = data.get("models", {}).get("self_hosted", {})
    if self_hosted:
        console.print("\n[bold white]Self-hosted models[/bold white]")
        sh_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
        sh_table.add_column("Name")
        sh_table.add_column("Endpoint")
        sh_table.add_column("Model")
        for alias, entry in self_hosted.items():
            sh_table.add_row(alias, entry.get("endpoint", "-"), entry.get("model_name", "-"))
        console.print(sh_table)

    console.print("\n[bold white]Rate limiter[/bold white]")
    rl_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    rl_table.add_column("Setting")
    rl_table.add_column("Value")
    for key, value in data.get("rate_limiter", {}).items():
        rl_table.add_row(key, str(value))
    console.print(rl_table)

    gateway = data.get("gateway", {})
    embedding = data.get("embedding", {})
    console.print("\n[bold white]Gateway[/bold white]")
    console.print(f"  Default model: [bold]{gateway.get('default_model', '-')}[/bold]")
    console.print(f"  Default temperature: [bold]{gateway.get('default_temperature', '-')}[/bold]")
    console.print(f"  Embedding model: [bold]{embedding.get('model_name', '-')}[/bold]")
    console.print()


def _configured_providers(data: dict) -> list[str]:
    return [
        name for name, meta in PROVIDERS.items()
        if data.get("models", {}).get(meta["config_key"].lower(), {}).get("api_key") != _NOT_CONFIGURED
    ]


def _change_rate_limiter(data: dict) -> dict:
    current = data.get("rate_limiter", {})
    info(f"Current: max_tokens={current.get('max_tokens')}, refill_rate={current.get('refill_rate')}, "
         f"time_interval={current.get('time_interval')}")

    while True:
        raw = Prompt.ask("\n  [bold cyan]Sustained requests per second[/bold cyan] [dim](per user)[/dim]")
        if raw.isdigit() and int(raw) > 0:
            rps = int(raw)
            break
        error("Enter a positive integer")

    while True:
        raw = Prompt.ask(
            "  [bold cyan]Burst multiplier[/bold cyan] [dim](seconds of burst capacity, default 5)[/dim]",
            default="5",
        )
        if raw.isdigit() and int(raw) >= 1:
            burst = int(raw)
            break
        error("Enter a positive integer")

    data["rate_limiter"] = {
        "max_tokens": str(rps * burst),
        "refill_rate": str(rps),
        "time_interval": "1.0",
    }
    success("Rate limiter updated")
    warn(_RESTART_NOTICE)
    return data


def _change_embedding_model(data: dict) -> dict:
    current = data.get("embedding", {}).get("model_name", "")
    info(f"Current embedding model: [bold]{current}[/bold]")

    new_name = Prompt.ask(
        "\n  [bold cyan]New embedding model[/bold cyan] [dim](a model2vec model name, e.g. minishlab/potion-base-8M)[/dim]",
        default=current,
    )
    data.setdefault("embedding", {})["model_name"] = new_name
    success(f"Embedding model set to [bold]{new_name}[/bold]")
    warn(_RESTART_NOTICE)
    return data


def _change_default_model(data: dict) -> dict:
    configured = _configured_providers(data)
    if not configured:
        error("No provider has a configured API key yet — add one first (option 4).")
        return data

    all_models = []
    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("#", style="bold white", width=4)
    table.add_column("Model", style="bold white")
    table.add_column("Provider", style="dim")
    for name in configured:
        for model in PROVIDERS[name]["models"]:
            all_models.append(model)
            table.add_row(str(len(all_models)), model, name)

    console.print()
    console.print(table)

    while True:
        raw = Prompt.ask("\n  [bold cyan]New default model[/bold cyan] [dim](number)[/dim]")
        if raw.isdigit() and 1 <= int(raw) <= len(all_models):
            chosen = all_models[int(raw) - 1]
            break
        error(f"Enter a number between 1 and {len(all_models)}")

    data.setdefault("gateway", {})["default_model"] = chosen
    success(f"Default model set to [bold]{chosen}[/bold]")
    warn(_RESTART_NOTICE)
    return data


def _add_new_model(data: dict) -> dict:
    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("#", style="bold white", width=4)
    table.add_column("Provider", style="bold white")
    table.add_column("Status", style="dim")

    names = list(PROVIDERS.keys())
    for i, name in enumerate(names, 1):
        key = data.get("models", {}).get(PROVIDERS[name]["config_key"].lower(), {}).get("api_key", _NOT_CONFIGURED)
        status = "[bold green]configured[/bold green]" if key != _NOT_CONFIGURED else "[dim]not configured[/dim]"
        table.add_row(str(i), name, status)

    console.print()
    console.print(table)

    while True:
        raw = Prompt.ask("\n  [bold cyan]Provider[/bold cyan] [dim](number)[/dim]")
        if raw.isdigit() and 1 <= int(raw) <= len(names):
            provider_name = names[int(raw) - 1]
            break
        error(f"Enter a number between 1 and {len(names)}")

    config_key = PROVIDERS[provider_name]["config_key"].lower()
    api_key = Prompt.ask(f"\n  [bold cyan]{provider_name} API key[/bold cyan]", password=True)

    data.setdefault("models", {})[config_key] = {"api_key": encrypt_value(api_key)}
    success(f"{provider_name} API key saved and encrypted")
    warn(_RESTART_NOTICE)
    return data


def _add_self_hosted_model(data: dict) -> dict:
    self_hosted = data.setdefault("models", {}).setdefault("self_hosted", {})

    if self_hosted:
        table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
        table.add_column("Name", style="bold white")
        table.add_column("Endpoint", style="dim")
        table.add_column("Model", style="dim")
        for alias, entry in self_hosted.items():
            table.add_row(alias, entry.get("endpoint", "-"), entry.get("model_name", "-"))
        console.print()
        console.print(table)

    alias = Prompt.ask(
        "\n  [bold cyan]Name for this model[/bold cyan] "
        "[dim](e.g. ollama-llama3 - used to request it; reuse an existing name to update it)[/dim]"
    )
    endpoint = Prompt.ask("  [bold cyan]Endpoint URL[/bold cyan] [dim](e.g. http://localhost:11434/v1)[/dim]")
    model_name = Prompt.ask(
        "  [bold cyan]Real model name[/bold cyan] [dim](exactly what the server expects, e.g. llama3)[/dim]"
    )
    api_key_input = Prompt.ask(
        "  [bold cyan]API key[/bold cyan] [dim](press Enter if the server doesn't require one)[/dim]",
        password=True,
        default="",
    )
    api_key = encrypt_value(api_key_input) if api_key_input else _NOT_CONFIGURED

    self_hosted[alias] = {"endpoint": endpoint, "model_name": model_name, "api_key": api_key}
    success(f"Self-hosted model [bold]{alias}[/bold] saved")
    warn(_RESTART_NOTICE)
    return data


def _remove_self_hosted_model(data: dict) -> dict:
    self_hosted = data.get("models", {}).get("self_hosted", {})
    if not self_hosted:
        error("No self-hosted models configured yet.")
        return data

    aliases = list(self_hosted.keys())
    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("#", style="bold white", width=4)
    table.add_column("Name", style="bold white")
    table.add_column("Endpoint", style="dim")
    for i, alias in enumerate(aliases, 1):
        table.add_row(str(i), alias, self_hosted[alias].get("endpoint", "-"))

    console.print()
    console.print(table)

    while True:
        raw = Prompt.ask("\n  [bold cyan]Remove which one[/bold cyan] [dim](number)[/dim]")
        if raw.isdigit() and 1 <= int(raw) <= len(aliases):
            chosen = aliases[int(raw) - 1]
            break
        error(f"Enter a number between 1 and {len(aliases)}")

    del data["models"]["self_hosted"][chosen]
    success(f"Removed self-hosted model: [bold]{chosen}[/bold]")
    warn(_RESTART_NOTICE)
    return data


_CHANGE_OPTIONS = {
    "1": ("Rate limiter setting", _change_rate_limiter),
    "2": ("Embedding model", _change_embedding_model),
    "3": ("Default model", _change_default_model),
    "4": ("Add / update a provider API key", _add_new_model),
    "5": ("Add / update a self-hosted model", _add_self_hosted_model),
    "6": ("Remove a self-hosted model", _remove_self_hosted_model),
}


def change_configuration() -> None:
    data = _require_config()
    _verify_admin(data)

    while True:
        console.print("[bold white]What would you like to change?[/bold white]\n")
        for key, (label, _) in _CHANGE_OPTIONS.items():
            console.print(f"  [bold cyan]{key}[/bold cyan]  {label}")

        choice = Prompt.ask("\n  [bold cyan]Choice[/bold cyan]", choices=list(_CHANGE_OPTIONS.keys()))
        _, handler = _CHANGE_OPTIONS[choice]

        data = handler(data)
        _write_config(data)
        info(f"config.yaml updated at [dim]{_CONFIG_PATH.resolve()}[/dim]")

        if not Confirm.ask("\n  [bold white]Change anything else?[/bold white]", default=False):
            break
        console.print()

    console.print()
