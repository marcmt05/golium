from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import json


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def snapshot_id_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def export_public_data(output_dir: Path, data: dict, picks: list[dict], metrics: dict, model_info: dict) -> None:
    write_json(output_dir / "data.json", data)
    write_json(output_dir / "picks.json", {"generated_at": model_info.get("generated_at"), "picks": picks})
    write_json(output_dir / "metrics.json", metrics)
    write_json(output_dir / "model-info.json", model_info)


def export_snapshot(history_dir: Path, snapshot_id: str, data: dict, picks: list[dict], metrics: dict, model_info: dict, ledger: list[dict]) -> Path:
    root = history_dir / snapshot_id
    write_json(root / "data.json", data)
    write_json(root / "picks.json", {"generated_at": model_info.get("generated_at"), "picks": picks})
    write_json(root / "metrics.json", metrics)
    write_json(root / "model-info.json", model_info)
    write_json(root / "ledger.json", ledger)
    return root
