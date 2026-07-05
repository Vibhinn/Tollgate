import click
from .helpers import run_setup


@click.group()
def cli():
    pass


@cli.command()
def init():
    run_setup()
