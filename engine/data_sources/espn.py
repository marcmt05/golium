from __future__ import annotations

from typing import Any
import json
from pathlib import Path


def load_from_json(path: str | Path) -> dict[str, Any]:
    """Load existing scraper output to keep backward compatibility."""
    return json.loads(Path(path).read_text(encoding="utf-8"))
