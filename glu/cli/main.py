import typer
from glu.cli import ticket, pr

app = typer.Typer()
app.add_typer(pr.app, name="pr")
app.add_typer(ticket.app, name="ticket")

if __name__ == "__main__":
    app()
