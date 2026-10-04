import os
import sys
from pathlib import Path

import click

from rich.table import Table

from .helpers import run_initialization_setup, print_configuration, change_configuration, require_config, verify_admin
from .helpers.tokens import TokenStore, parse_ttl, validate_identifier, redis_from_config
from .ui import console, error, info, success, warn
from src.utils.config import Config

_APP_DIR = os.environ.get("TOLLGATE_APP_DIR", ".")


@click.group()
def cli():
    pass #need to keep tis empty

@cli.command()
def init():
    run_initialization_setup()

@cli.command()
@click.option("--change", "change_mode", is_flag=True, help="Interactively change a specific setting.")
def config(change_mode: bool):
    if change_mode:
        change_configuration()
    else:
        print_configuration()

@cli.command()
def start():
    if not Path("config.yaml").exists():
        error("No config.yaml found. Run: tollgate init")
        sys.exit(1)

    try:
        Config()
    except Exception as e:
        error(f"config.yaml could not be loaded: {e}")
        sys.exit(1)

    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=13000, app_dir=_APP_DIR)




@cli.group()
def token():
    """Create, list and revoke access tokens."""


def _token_store() -> TokenStore:
    if not Path("config.yaml").exists():
        error("No config.yaml found. Run: tollgate init")
        sys.exit(1)
    return TokenStore(redis_from_config(Config()))


@token.command("create")
@click.option("--team", required=True, help="Team that owns the token, e.g. payments.")
@click.option("--name", required=True, help="Person or app using the token, e.g. alice or invoice-bot.")
@click.option("--ttl", default="90d", show_default=True, help="Lifetime: e.g. 30d, 12h, or never.")
def token_create(team: str, name: str, ttl: str):
    """Tokens with the same team and name share one rate limit and cache."""
    try:
        ttl_seconds = parse_ttl(ttl)
        validate_identifier("team", team)
        validate_identifier("name", name)
    except ValueError as e:
        error(str(e))
        sys.exit(1)

    verify_admin(require_config())
    new_token, record = _token_store().create(team, name, ttl_seconds)

    success(f"Token created for [bold]{record.team}:{record.name}[/bold] (ID {record.id}, expires {record.expires_at or 'never'})")
    console.print(f"\n  [bold]{new_token}[/bold]\n")
    warn("Copy it now. It is shown only once and cannot be recovered.")


@token.command("list")
@click.option("--team", default=None, help="Only show this team's tokens.")
def token_list(team: str | None):
    records = _token_store().list(team)
    if not records:
        info("No active tokens.")
        return

    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    for column in ("ID", "Team", "Name", "Created", "Expires"):
        table.add_column(column)
    for record in records:
        table.add_row(record.id, record.team, record.name, _short_date(record.created_at), _short_date(record.expires_at))
    console.print(table)


def _short_date(timestamp: str | None) -> str:
    return timestamp[:16].replace("T", " ") if timestamp else "never"


@token.command("revoke")
@click.argument("token_or_id", required=False)
@click.option("--team", default=None, help="With --name: revoke every token of that team and name.")
@click.option("--name", default=None)
def token_revoke(token_or_id: str | None, team: str | None, name: str | None):
    """Revoke one token (full token or the ID from `tollgate token list`), or all tokens of a team and name."""
    if bool(token_or_id) == bool(team and name):
        error("Give either a token/ID, or both --team and --name.")
        sys.exit(1)

    verify_admin(require_config())
    store = _token_store()

    if token_or_id:
        try:
            revoked = store.revoke(token_or_id)
        except ValueError as e:
            error(str(e))
            sys.exit(1)
        if not revoked:
            error("No active token matches that token or ID.")
            sys.exit(1)
        success("Token revoked. It stops working immediately.")
    else:
        count = store.revoke_identity(team, name)
        if count == 0:
            error(f"No active tokens for {team}:{name}.")
            sys.exit(1)
        success(f"Revoked {count} token{'s' if count != 1 else ''} for {team}:{name}.")
