from typer import Context
import rich
from langchain_core.language_models import BaseChatModel
import os


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


def get_chat_model() -> BaseChatModel | None:
    if os.getenv("GLEAN_API_TOKEN"):
        from langchain_glean.chat_models import ChatGlean

        return ChatGlean()

    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model="o4-mini", temperature=0)

    rich.print("[warning]No API key found. Skipping PR description generation.[/]")
    return None
