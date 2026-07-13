"""任务注册表:每个 task 必须提供 TASK / GRADER_CODE,可选用 SETUP_CODE / ground_truth()"""
import os, importlib, pathlib, sys

_TASKS_DIR = pathlib.Path(__file__).parent

# 手写注册(避免依赖文件命名约定)
TASKS = {}

def _load(name: str):
    mod = importlib.import_module(f"eval.tasks.{name}")
    entry = {
        "id": name,
        "task": mod.TASK,
        "grader": mod.GRADER_CODE,
    }
    if hasattr(mod, "SETUP_CODE"):
        entry["setup"] = mod.SETUP_CODE
    if hasattr(mod, "ground_truth") and callable(mod.ground_truth):
        entry["ground_truth"] = mod.ground_truth()
    TASKS[name] = entry

for _n in ("sort_integers", "count_log_lines", "copy_and_modify"):
    _load(_n)
