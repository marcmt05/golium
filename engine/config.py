from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json

from engine.markets import MARKETS


@dataclass
class ModelConfig:
    max_goals: int = 8
    dc_rho: float = 0.08
    use_dixon_coles: bool = True
    home_advantage: float = 1.06
    form_decay: float = 0.72
    form_cap: float = 0.12
    momentum_cap: float = 0.08
    shrinkage_weight: float = 0.2


@dataclass
class BettingConfig:
    kelly_fraction: float = 0.25
    kelly_cap: float = 0.03
    min_model_prob: float = 0.55
    min_model_gap: float = 0.04
    min_value_edge: float = 0.02
    min_odds: float = 1.5
    max_odds: float = 5.5
    allowed_markets: tuple[str, ...] = MARKETS


@dataclass
class PipelineConfig:
    input_file: Path = Path("data.json")
    output_dir: Path = Path("public-data")
    history_dir: Path = Path("history/snapshots")
    model_version: str = "golium-engine-v2"
    model: ModelConfig = field(default_factory=ModelConfig)
    betting: BettingConfig = field(default_factory=BettingConfig)


def load_config(path: str | Path | None = None) -> PipelineConfig:
    if path is None:
        return PipelineConfig()

    cfg = PipelineConfig()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))

    for key in ("input_file", "output_dir", "history_dir", "model_version"):
        if key in payload:
            setattr(cfg, key, Path(payload[key]) if key.endswith("file") or key.endswith("dir") else payload[key])

    if "model" in payload:
        for k, v in payload["model"].items():
            if hasattr(cfg.model, k):
                setattr(cfg.model, k, v)

    if "betting" in payload:
        for k, v in payload["betting"].items():
            if hasattr(cfg.betting, k):
                setattr(cfg.betting, k, tuple(v) if k == "allowed_markets" else v)

    return cfg


def config_as_dict(cfg: PipelineConfig) -> dict[str, Any]:
    return {
        "input_file": str(cfg.input_file),
        "output_dir": str(cfg.output_dir),
        "history_dir": str(cfg.history_dir),
        "model_version": cfg.model_version,
        "model": cfg.model.__dict__,
        "betting": {**cfg.betting.__dict__, "allowed_markets": list(cfg.betting.allowed_markets)},
    }
