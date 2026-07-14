"""从本地缓存的 parquet 文件加载 HumanEval / MBPP 样本。"""
from __future__ import annotations
import pathlib, random
from typing import Iterator, Dict, Any

CACHE_DIR = pathlib.Path("/tmp/hf_cache")

DATASETS = {
    "humaneval": {
        "path": "datasets--openai_humaneval/snapshots",
        "file": "openai_humaneval/test-00000-of-00001.parquet",
        "id_field": "task_id",
    },
    "mbpp": {
        "path": "datasets--mbpp/snapshots",
        "file": "sanitized/test-00000-of-00001.parquet",
        "id_field": "task_id",
    },
}


def _find_parquet(rel_path: str, file: str) -> pathlib.Path:
    base = CACHE_DIR / rel_path
    snaps = sorted(base.glob("*/" + file))
    if not snaps:
        raise FileNotFoundError(f"parquet not found under {base}/{file}")
    return snaps[-1]


def load_all(source: str):
    info = DATASETS[source]
    import pandas as pd
    p = _find_parquet(info["path"], info["file"])
    df = pd.read_parquet(p)
    return df.to_dict("records")


def sample(source: str, n: int, seed: int = 42) -> list:
    rng = random.Random(seed)
    rows = load_all(source)
    rng.shuffle(rows)
    return rows[:n]
