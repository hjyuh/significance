"""Shared violation type for schema and semantic checks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Violation:
    rule: str
    message: str
    location: str
    file: str | None = None

    def to_dict(self) -> dict:
        d = {"rule": self.rule, "location": self.location, "message": self.message}
        if self.file:
            d["file"] = self.file
        return d

    def __str__(self) -> str:
        prefix = f"{self.file}: " if self.file else ""
        return f"{prefix}[{self.rule}] {self.location}: {self.message}"
