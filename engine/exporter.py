from __future__ import annotations

from pathlib import Path
import json


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def export_public_data(output_dir: Path, data: dict, picks: list[dict], metrics: dict, model_info: dict) -> None:
    write_json(output_dir / "data.json", data)
    write_json(
        output_dir / "picks.json",
        {
            "snapshot_id": model_info.get("snapshot_id"),
            "generated_at": model_info.get("generated_at"),
            "picks": picks,
        },
    )
    write_json(output_dir / "metrics.json", metrics)
    write_json(output_dir / "model-info.json", model_info)
