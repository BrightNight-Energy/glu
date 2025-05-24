from dataclasses import dataclass

from github.NamedUser import NamedUser


@dataclass
class MatchedUser:
    user: NamedUser
    score: float
