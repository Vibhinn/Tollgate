import click

@click.group()
def cli():
    pass

@cli.command()
def init():
    click.echo("Hi. Thanks for using Tollgate.")