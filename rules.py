from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BlockRule:
    trigger: str
    after: int = 100


@dataclass(frozen=True)
class Rules:
    include: list[str]
    blocks: list[BlockRule]
    regex: bool = False