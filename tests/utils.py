import json
import re
from enum import Enum
from pathlib import Path

import rich

from tests import TESTS_DATA_DIR


class Key(Enum):
    ENTER = "\r"
    UP = "\x1b[A"
    DOWN = "\x1b[B"


def get_terminal_text(output: str | bytes) -> str:
    ansi_re = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
    text = output.decode("utf-8") if isinstance(output, bytes) else output
    output = ansi_re.sub("", text)
    rich.print(output)
    return output


def load_json(path: str | Path) -> dict:
    with open(TESTS_DATA_DIR / path, "r") as f:
        return json.load(f)
