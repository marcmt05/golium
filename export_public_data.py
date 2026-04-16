#!/usr/bin/env python3
from __future__ import annotations

from engine.config import PipelineConfig
from engine.pipeline import run_pipeline

if __name__ == "__main__":
    result = run_pipeline(PipelineConfig())
    print(f"Export complete -> public-data/ and {result['snapshot_path']}")
