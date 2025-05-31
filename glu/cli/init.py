import typer

app = typer.Typer()


@app.command(short_help="Init config file")
def init():
    pass
