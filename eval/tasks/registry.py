"""任务注册表:每个 task 必须提供 TASK / GRADER_CODE,可选用 SETUP_CODE / ground_truth()

加载规则:扫描本目录下所有 .py 文件,跳过以 _ 开头的和自身。
seede_*.py 自动注册;手写的也照样加载。
"""
import os, importlib, pathlib, sys

_TASKS_DIR = pathlib.Path(__file__).parent

# 手写注册(避免依赖文件命名约定)
TASKS = {}

def _load(name: str):
    try:
        mod = importlib.import_module(f"eval.tasks.{name}")
    except Exception as e:
        print(f"[registry] skip {name}: {e}", file=sys.stderr)
        return
    if not hasattr(mod, "TASK") or not hasattr(mod, "GRADER_CODE"):
        return
    entry = {
        "id": name,
        "task": mod.TASK,
        "grader": mod.GRADER_CODE,
    }
    if hasattr(mod, "SETUP_CODE"):
        entry["setup"] = mod.SETUP_CODE
    if hasattr(mod, "ground_truth") and callable(mod.ground_truth):
        entry["ground_truth"] = mod.ground_truth()
    elif hasattr(mod, "GROUND_TRUTH"):
        entry["ground_truth"] = mod.GROUND_TRUTH
    TASKS[name] = entry

# 扫描所有 .py,排除自身 + 私有
for _p in sorted(_TASKS_DIR.glob("*.py")):
    _name = _p.stem
    if _name.startswith("_") or _name == "registry":
        continue
    _load(_name)
