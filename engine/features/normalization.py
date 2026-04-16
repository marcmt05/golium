from __future__ import annotations

import re


def norm_team(name: str | None) -> str:
    txt = (name or "").lower()
    txt = re.sub(r"\b(fc|cf|ac|sc|cd|rc|ud|as|ss|afc|fk|sk|1\.)\b", "", txt)
    return re.sub(r"[^a-z0-9]", "", txt).strip()


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
