import os

import rich
import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import FuzzyCompleter, WordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.validation import Validator
from typer import Context


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


def multi_select_menu(prompt_text: str, options: list[str]) -> list[str]:
    """
    Let the user pick zero or more items via filterable_menu.
    Repeats until they press Enter on a blank selection.
    """
    remaining = options.copy()
    selected: list[str] = []

    while True:
        toolbar = HTML(f"Selected: {', '.join(selected)}") if selected else None

        choice = filterable_menu(prompt_text, remaining, toolbar, enter_to_escape=True)
        # If they hit Enter on blank (or ESC), filterable_menu will return "" or invalid, so break
        if not choice:
            break

        selected.append(choice)
        remaining.remove(choice)

        # If nothing left, bail out
        if not remaining:
            break

    return selected


def filterable_menu(
    prompt_text: str,
    options: list[str],
    toolbar: HTML | None = None,
    enter_to_escape: bool = False,
) -> str:
    # 1) Build a fuzzy completer over your options.
    completer = FuzzyCompleter(WordCompleter(options, ignore_case=True))

    # 2) Bind up/down to move through the visible suggestions, and open menu if not open.
    kb = KeyBindings()

    @kb.add("up")
    def _(event):
        buf = event.current_buffer
        buf.start_completion(select_first=False)
        buf.complete_previous()

    @kb.add("down")
    def _(event):
        buf = event.current_buffer
        buf.start_completion(select_first=False)
        buf.complete_next()

    validator = Validator.from_callable(
        lambda text: (text == "" if enter_to_escape else False) or text in options,
        error_message="Invalid selection; choose one of the list or press Enter to skip",
        move_cursor_to_end=True,
    )

    session: PromptSession = PromptSession()
    return session.prompt(
        HTML(
            f"{prompt_text} <ansibrightblack>[use ↑/↓ arrows or type to select, press "
            f"enter to end]</ansibrightblack> "
        ),
        completer=completer,
        complete_while_typing=True,
        complete_style=CompleteStyle.COLUMN,
        key_bindings=kb,
        validator=validator,
        validate_while_typing=False,
        bottom_toolbar=toolbar,
    )


def prompt_or_edit(prompt: str, allow_skip: bool = False) -> str:
    output = typer.prompt(
        f"{prompt} [(e) to launch editor{', enter to skip' if allow_skip else ''}]",
        default="" if allow_skip else None,
        show_default=False,
    )

    if output.lower() == "e":
        body = typer.edit("") or ""
        if body is None:
            print_error(f"No {prompt.lower()} provided")
            raise typer.Exit(1)
        return body

    return output


def remove_json_backticks(text: str) -> str:
    return text.replace("```json", "").replace("```", "")


def suppress_traceback(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as err:
            if os.getenv("GLU_TEST"):
                raise err

            rich.print(f"[bold red]{type(err).__name__}: {err}[/]")
            raise typer.Exit(1) from err

    return wrapper


def add_generated_with_glu_tag(text: str, supports_markdown: bool = True) -> str:
    if not supports_markdown:
        return f"{text}\n\nGenerated with [glu|https://github.com/BrightNight-Energy/glu]"

    return f"{text}\n\nGenerated with [glu](https://github.com/BrightNight-Energy/glu)"
