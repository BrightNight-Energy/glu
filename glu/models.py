from dataclasses import dataclass
from typing import Literal

from github.NamedUser import NamedUser
from pydantic import BaseModel

ChatProvider = Literal["OpenAI", "Glean"]

CHAT_PROVIDERS: list[ChatProvider] = ["OpenAI", "Glean"]


@dataclass
class MatchedUser:
    user: NamedUser
    score: float


class TicketGeneration(BaseModel):
    description: str
    summary: str
