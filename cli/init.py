import click
from .helpers import generate_config_ini_file

@click.group()
def cli():
    pass

@cli.command()
def init():
    click.echo("Hi. Thanks for using Tollgate.")
    generate_config_ini_file()
