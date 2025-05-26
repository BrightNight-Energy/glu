from dataclasses import dataclass
from typing import Literal

from github.NamedUser import NamedUser


ChatProvider = Literal["OpenAI", "Glean"]

CHAT_PROVIDERS: list[ChatProvider] = ["OpenAI", "Glean"]


@dataclass
class MatchedUser:
    user: NamedUser
    score: float
