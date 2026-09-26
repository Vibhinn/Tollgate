from rich.prompt import Prompt, Confirm
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


def _collect_self_hosted_models(config: dict) -> dict:
    self_hosted_models: dict[str, dict] = {}

    console.print()
    if not Confirm.ask(
        "  [bold cyan]Add a self-hosted model?[/bold cyan] [dim](Ollama, llama.cpp, Apple FM, ...)[/dim]",
        default=False,
    ):
        return self_hosted_models

    while True:
        alias = Prompt.ask(
            "\n  [bold cyan]Name for this model[/bold cyan] [dim](your own name for it, used to request it - e.g. ollama-llama3)[/dim]"
        )
        while not alias or alias in self_hosted_models:
            error(f"'{alias}' is empty or already added — pick a different name")
            alias = Prompt.ask("  [bold cyan]Name for this model[/bold cyan]")

        endpoint = Prompt.ask("  [bold cyan]Endpoint URL[/bold cyan] [dim](e.g. http://localhost:11434/v1)[/dim]")
        model_name = Prompt.ask(
            "  [bold cyan]Real model name[/bold cyan] [dim](exactly what the server expects, e.g. llama3)[/dim]"
        )
        api_key_input = Prompt.ask(
            "  [bold cyan]API key[/bold cyan] [dim](press Enter if the server doesn't require one)[/dim]",
            password=True,
            default="",
        )
        api_key = encrypt_with_key(api_key_input, config["_fernet_key"]) if api_key_input else "NOT_CONFIGURED"

        self_hosted_models[alias] = {
            "endpoint": endpoint,
            "model_name": model_name,
            "api_key": api_key,
        }
        success(f"Added self-hosted model: [bold]{alias}[/bold]")

        if not Confirm.ask("\n  [bold cyan]Add another self-hosted model?[/bold cyan]", default=False):
            break

    return self_hosted_models


def run(config: dict) -> dict:
    step_header(5, "LLM Providers & API Keys", total=7)

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
    config["self_hosted_models"] = _collect_self_hosted_models(config)

    return config
