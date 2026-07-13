"""run_eval.py — coding-agent 评测 runner

用法:
    python3 eval/run_eval.py                  # 跑全部
    python3 eval/run_eval.py --ids a,b       # 跑指定题
    python3 eval/run_eval.py --agent /abs/path/to/agent.py

每题一个隔离 workdir,跑完清掉。结果写 eval/results/<run_id>.json。
"""
import argparse, json, os, pathlib, shutil, subprocess, sys, tempfile, time
from datetime import datetime

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from eval.tasks.registry import TASKS

DEFAULT_AGENT = REPO_ROOT / "src/code_agent/exec_loop/agent.py"


def _run_setup(setup_code: str, workdir: pathlib.Path):
    """在 workdir 里跑 setup 代码(EVAL_WORKDIR 会传进去)"""
    env = os.environ.copy()
    env["EVAL_WORKDIR"] = str(workdir)
    # 同时让 ground_truth 文件可被 grader 读到:把内容塞进 GROUND_TRUTH 环境变量
    gt_file = workdir / ".ground_truth"
    if gt_file.exists():
        env["GROUND_TRUTH"] = gt_file.read_text().strip()
    r = subprocess.run(
        [sys.executable, "-c", setup_code],
        env=env, capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0:
        raise RuntimeError(f"setup failed: {r.stderr}")
    # 重读一遍 .ground_truth(setup 可能写了)
    if gt_file.exists():
        env["GROUND_TRUTH"] = gt_file.read_text().strip()
    return env


def _run_agent(agent_cmd: list[str], task: str, env: dict, workdir: pathlib.Path, timeout: int):
    """调 agent CLI,拿最终 stdout"""
    env2 = env.copy()
    # agent 用 cwd 找上下文
    r = subprocess.run(
        agent_cmd + [task],
        cwd=str(workdir), env=env2,
        capture_output=True, text=True, timeout=timeout,
    )
    return r.stdout, r.stderr, r.returncode


def _run_grader(grader_code: str, agent_output: str, env: dict):
    """grader 从 stdin 读回答内容"""
    env2 = env.copy()
    r = subprocess.run(
        [sys.executable, "-c", grader_code],
        input=agent_output, env=env2,
        capture_output=True, text=True, timeout=15,
    )
    pass_ = r.returncode == 0
    msg = (r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr) else ""
    return pass_, msg


def run_one(task_id: str, agent_cmd: list[str], timeout: int, base_tmp: pathlib.Path):
    entry = TASKS[task_id]
    workdir = base_tmp / task_id
    workdir.mkdir(parents=True, exist_ok=True)
    env = {}
    try:
        if "setup" in entry:
            env = _run_setup(entry["setup"], workdir)
        else:
            env = os.environ.copy()
            env["EVAL_WORKDIR"] = str(workdir)

        t0 = time.time()
        stdout, stderr, rc = _run_agent(agent_cmd, entry["task"], env, workdir, timeout)
        elapsed = time.time() - t0

        # agent 失败也算 FAIL(没回答/出错)
        if rc != 0 and not stdout.strip():
            return {
                "id": task_id, "pass": False,
                "reason": f"agent exited {rc}: {stderr.strip()[:200]}",
                "elapsed_sec": round(elapsed, 2),
            }

        ok, msg = _run_grader(entry["grader"], stdout, env)
        return {
            "id": task_id, "pass": ok,
            "reason": msg if not ok else "ok",
            "elapsed_sec": round(elapsed, 2),
            "agent_output_preview": stdout.strip()[:300],
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="", help="comma-separated task ids; default = all")
    ap.add_argument("--agent", default=str(DEFAULT_AGENT),
                    help="path to agent.py (or use python -m ...)")
    ap.add_argument("--timeout", type=int, default=120, help="per-task timeout (sec)")
    ap.add_argument("--out", default="", help="results JSON path")
    args = ap.parse_args()

    if args.ids:
        ids = [x.strip() for x in args.ids.split(",") if x.strip()]
    else:
        ids = list(TASKS.keys())

    unknown = [x for x in ids if x not in TASKS]
    if unknown:
        print(f"[!] unknown task ids: {unknown}; available: {list(TASKS)}", file=sys.stderr)
        sys.exit(2)

    agent_cmd = [sys.executable, args.agent, "--quiet"]
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_tmp = pathlib.Path(tempfile.mkdtemp(prefix=f"eval_{run_id}_"))

    results = []
    for tid in ids:
        print(f"[run] {tid} ...", flush=True)
        r = run_one(tid, agent_cmd, args.timeout, base_tmp)
        results.append(r)
        flag = "PASS" if r["pass"] else "FAIL"
        print(f"  -> {flag} ({r['elapsed_sec']}s) {r.get('reason','')}", flush=True)

    n_pass = sum(1 for r in results if r["pass"])
    summary = {
        "run_id": run_id,
        "agent": args.agent,
        "total": len(results),
        "pass": n_pass,
        "accuracy": round(n_pass / len(results), 4) if results else 0.0,
        "tasks": results,
    }

    out_path = pathlib.Path(args.out) if args.out else (
        REPO_ROOT / "eval" / "results" / f"{run_id}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n[done] {n_pass}/{len(results)} pass  (acc={summary['accuracy']:.0%})")
    print(f"  results: {out_path}")

    shutil.rmtree(base_tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
