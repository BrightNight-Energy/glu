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


def get_terminal_text(text: str) -> str:
    ansi_re = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
    output = ansi_re.sub("", text)
    rich.print(output)
    return output


def load_json(path: str | Path) -> dict:
    with open(TESTS_DATA_DIR / path, "r") as f:
        return json.load(f)
