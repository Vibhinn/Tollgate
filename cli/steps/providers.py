from rich.prompt import Prompt
from rich.table import Table

from ..ui import console, step_header, success, error, info
from ..inputs.accepted_inputs import PROVIDERS, DEFAULT_EMBEDDING_MODEL
from src.utils.crypto import encrypt_with_key


def _pick_providers() -> list[str]:
    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("#", style="bold white", width=4)
    table.add_column("Provider", style="bold white")
    table.add_column("Models available", style="dim")

    names = list(PROVIDERS.keys())
    for i, name in enumerate(names, 1):
        models = ", ".join(PROVIDERS[name]["models"])
        table.add_row(str(i), name, models)

    console.print(table)

    while True:
        raw = Prompt.ask(
            "\n  [bold cyan]Select providers[/bold cyan] [dim](e.g. 1,2 or 1,2,3)[/dim]"
        )
        indices = []
        valid = True
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit() and 1 <= int(part) <= len(names):
                indices.append(int(part) - 1)
            else:
                valid = False
                break
        if valid and indices:
            return [names[i] for i in indices]
        error(f"Enter numbers between 1 and {len(names)}, comma-separated")


def _pick_default_model(selected: list[str]) -> str:
    all_models = []
    for name in selected:
        all_models.extend(PROVIDERS[name]["models"])

    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("#", style="bold white", width=4)
    table.add_column("Model", style="bold white")
    table.add_column("Provider", style="dim")

    for i, model in enumerate(all_models, 1):
        provider = next(n for n in selected if model in PROVIDERS[n]["models"])
        table.add_row(str(i), model, provider)

    console.print("\n  [bold white]Available models:[/bold white]")
    console.print(table)

    while True:
        raw = Prompt.ask("\n  [bold cyan]Default model[/bold cyan] [dim](number)[/dim]")
        if raw.isdigit() and 1 <= int(raw) <= len(all_models):
            return all_models[int(raw) - 1]
        error(f"Enter a number between 1 and {len(all_models)}")


def run(config: dict) -> dict:
    step_header(4, "LLM Providers & API Keys", total=6)

    selected = _pick_providers()
    info(f"Selected: [bold]{', '.join(selected)}[/bold]")

    api_keys: dict[str, str] = {}
    for name in selected:
        key = Prompt.ask(f"\n  [bold cyan]{name} API key[/bold cyan]", password=True)
        api_keys[PROVIDERS[name]["config_key"]] = encrypt_with_key(key, config["_fernet_key"])
        success(f"{name} key encrypted")

    console.print()
    default_model = _pick_default_model(selected)
    success(f"Default model: [bold]{default_model}[/bold]")

    while True:
        raw = Prompt.ask(
            "\n  [bold cyan]Default temperature[/bold cyan] [dim](0.0 – 2.0, default 0.7)[/dim]",
            default="0.7",
        )
        try:
            temp = float(raw)
            if 0.0 <= temp <= 2.0:
                break
        except ValueError:
            pass
        error("Enter a number between 0.0 and 2.0")

    config["api_keys"] = api_keys
    config["selected_providers"] = selected
    config["default_model"] = default_model
    config["default_temperature"] = str(temp)
    config["embedding_model"] = DEFAULT_EMBEDDING_MODEL

    return config
