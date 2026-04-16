#!/usr/bin/env python3
from __future__ import annotations

import argparse

from engine.config import load_config
from engine.pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Golium local engine pipeline")
    parser.add_argument("--config", default=None, help="Optional config JSON path")
    args = parser.parse_args()

    cfg = load_config(args.config)
    result = run_pipeline(cfg)
    print(f"Pipeline OK: snapshot={result['snapshot_id']} leagues={len(result['data'].get('leagues', {}))} picks={len(result['picks'])}")


if __name__ == "__main__":
    main()
