from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Site:
    id: str
    name: str
    allowed_origins: list[str]
    is_active: bool

