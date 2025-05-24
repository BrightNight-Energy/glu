from typer import Context
import rich


def get_kwargs(ctx: Context) -> dict[str, str | bool]:
    """
    Everything not declared as a parameter comes through in ctx.args,
    e.g. ["--foo", "bar", "--baz", "qux"].
    """
    raw = ctx.args
    # turn ["--foo","bar","--baz","qux"] into {"foo":"bar","baz":"qux"}
    it = iter(raw)
    extra_kwargs: dict[str, str | bool] = {}
    for token in it:
        if token.startswith("--"):
            key = token.lstrip("-")
            # peek next item for a value, else treat as boolean flag
            try:
                nxt = next(it)
                if nxt.startswith("--"):
                    # flag without value
                    extra_kwargs[key] = True
                    # put it back for the next loop
                    it = (x for x in [nxt] + list(it))
                else:
                    extra_kwargs[key] = nxt
            except StopIteration:
                extra_kwargs[key] = True

    return extra_kwargs


def print_error(error: str) -> None:
    rich.print(f"[red][bold]Error:[/bold] {error}.[/red]")
