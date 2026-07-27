#!/usr/bin/env python3
"""
agent.py - MiniMax 上的工具调用 agent 循环

复用 chat.py 的配置加载与客户端构造。在它之上加：
  1. 一组内置工具（bash / read_file / current_time）
  2. Anthropic tool-use 循环：
       - 若响应含 tool_use 块 → 执行 → 把 tool_result 回灌 → 再请求
       - 直到 end_turn 或 max_iters
  3. 每轮摘要打到 stderr，最终回答打到 stdout

用法:
    python agent.py "用 bash 看一下当前目录下有什么文件"
    python agent.py --quiet "算一下 1234 * 5678"
    python agent.py --max-iters 20 "读 ./chat.py 然后告诉我它干了啥"

依赖: anthropic SDK（与 chat.py 共用）
注意: --quiet 关闭逐轮日志；日志默认打印在 stderr。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable

# 让 `from code_agent.X import Y` 在任何 cwd 下都能工作 —— 把 src/ 加进 sys.path。
# 路径布局: this_file → src/code_agent/exec_loop/agent.py → 上溯 3 层到 src。
_SRC = Path(__file__).resolve().parent.parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from code_agent.llm import chat  # 复用 resolve_settings / make_client
from code_agent.contexts.base import ContextBuilder
from code_agent.contexts.memory import RecentConversationsContext


# ---------- 工具实现 ----------
# 每个工具返回一个字符串结果（出错则用 is_error=True 的 tool_result 回灌）

def _truncate(s: str, limit: int = 8000) -> str:
    if len(s) <= limit:
        return s
    return s[:limit] + f"\n...[truncated, {len(s) - limit} bytes more]"


def tool_bash(input_: dict) -> str:
    """跑 shell 命令，返回 stdout+stderr+exit code。"""
    cmd = input_.get("cmd", "")
    if not cmd.strip():
        return "[bash] empty cmd"
    timeout = min(int(input_.get("timeout", 30) or 30), 120)
    try:
        cp = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
        out = (cp.stdout or "") + (cp.stderr or "")
        return _truncate(f"[exit {cp.returncode}]\n{out}")
    except subprocess.TimeoutExpired:
        return f"[bash] timeout after {timeout}s"


def tool_read_file(input_: dict) -> str:
    """读文本文件（绝对或相对 cwd）。"""
    p = Path(input_["path"])
    if not p.is_absolute():
        p = Path.cwd() / p
    max_bytes = int(input_.get("max_bytes", 20000) or 20000)
    try:
        return _truncate(p.read_text(encoding="utf-8", errors="replace"), max_bytes)
    except FileNotFoundError:
        return f"[read_file] not found: {p}"
    except IsADirectoryError:
        return f"[read_file] is a directory: {p}"


def tool_current_time(_input: dict) -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


# ---------- 工具定义（给模型看）----------
TOOLS_SPEC: list[dict] = [
    {
        "name": "bash",
        "description": (
            "Run a shell command (non-interactive) and return stdout+stderr+exit code. "
            "Use this to inspect files, run git/ls/cat, etc. NOT for interactive programs. "
            "Output is truncated at 8000 chars."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cmd": {"type": "string", "description": "Shell command to run"},
                "timeout": {"type": "integer", "description": "Timeout seconds (1-120)", "default": 30},
            },
            "required": ["cmd"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a UTF-8 text file. Path can be absolute or relative to cwd.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
                "max_bytes": {"type": "integer", "description": "Max bytes to read", "default": 20000},
            },
            "required": ["path"],
        },
    },
    {
        "name": "current_time",
        "description": "Return current local time as an ISO 8601 string.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]

# name -> runner
TOOL_RUNNERS: dict[str, Callable[[dict], str]] = {
    "bash": tool_bash,
    "read_file": tool_read_file,
    "current_time": tool_current_time,
}

SYSTEM_PROMPT = (
    "You are a helpful assistant with a small toolbox. "
    "Use tools when they help. When you have a complete answer, just write it in plain text. "
    "Keep answers concise."
)


# ---------- Context 拼接 ----------
# 默认 contexts 列表:逐个调用 .build() 拿到一段文本,append 到一起,
# 拼到 system prompt 前面喂给 LLM。
DEFAULT_CONTEXTS: list[ContextBuilder] = [
    RecentConversationsContext(limit=10),
]

def build_contexts(contexts: list[ContextBuilder] | None = None) -> str:
    """遍历 contexts,逐个调用 render(),把纯文本用空行拼起来。

    任一 context 抛异常时,降级为空串,不影响主流程。
    """
    items = contexts if contexts is not None else DEFAULT_CONTEXTS
    chunks: list[str] = []
    for c in items:
        try:
            rendered = c.render()
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(
                f"[contexts] {type(c).__name__} build failed: "
                f"{type(e).__name__}: {e}\n"
            )
            continue
        if rendered:
            chunks.append(rendered)
    return "\n\n".join(chunks)



# ---------- Session 系统 ----------
# 设计: 每次启动 = 一个新 session 文件,放 ~/.codeagent/projects/<sanitize-cwd>/<timestamp>.json。
#      - 项目目录: abs_cwd 把 / 替成 - (保留前导 -,因为绝对路径以 / 开头)
#      - session 文件: <sanitize-cwd>/<timestamp>.json (扁平,不再嵌一层子目录)
#      - 每次默认开新 session,不接续(不实现 --continue / --resume)
#
# 这两个变量在 main() 里被覆盖;这里只是占位,让模块能 import。
PROJECT_DIR: Path = Path.home() / ".codeagent" / "projects"
SESSION_FILE: Path = PROJECT_DIR / "placeholder.json"  # main() 里重设


def _project_key(abs_cwd: str) -> str:
    """把绝对 cwd 编码成目录名。

    简单: 把 / 替成 -,其他非 [a-zA-Z0-9_-.] 也替成 -。
    保留前导 -,因为绝对路径以 / 开头。
    """
    return "".join(
        c if (c.isalnum() or c in "-_.") else "-"
        for c in abs_cwd
    )


def _projects_root() -> Path:
    return Path.home() / ".codeagent" / "projects"


def _project_dir() -> Path:
    """当前 cwd 对应的 projects/<sanitize-cwd> 目录。"""
    abs_cwd = str(Path.cwd().resolve())
    return _projects_root() / _project_key(abs_cwd)


def _new_session_id() -> str:
    """微秒级时间戳,字典序就是时间序。

    格式: YYYY-MM-DD-HHMMSS-microseconds
    例:   2026-07-23-114512-345678
    """
    return _dt.datetime.now().strftime("%Y-%m-%d-%H%M%S-%f")


def _resolve_session(args) -> Path:
    """根据 CLI 参数决定 session 文件路径。

    --session <name>: 用确切名字,撞名报错
    默认: 新 timestamp session 文件

    返回: <project_dir>/<session_id>.json
    """
    proj = _project_dir()

    if args.session:
        sess_id = args.session
    else:
        sess_id = _new_session_id()

    sess_file = proj / f"{sess_id}.jsonl"
    if sess_file.exists():
        sys.exit(f"[error] session '{sess_id}' already exists in this project")

    # 立即创建 project dir,文件在第一次写时才创建
    proj.mkdir(parents=True, exist_ok=True)
    return sess_file


def _ensure_memory() -> None:
    """确保当前 session 文件所在的目录存在。文件在第一次 append 时才创建。"""
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)


def _append_memory(entry: dict) -> None:
    """把一条记录作为一行 JSON append 到 session 文件。失败不阻塞主流程。

    O(1) per append —— 不读不解析整个文件,直接追加一行。
    fail-soft:序列化失败或写失败 → stderr 警告,主流程继续。
    """
    _ensure_memory()
    try:
        line = json.dumps(entry, ensure_ascii=False)
    except (TypeError, ValueError) as e:  # noqa: BLE001
        sys.stderr.write(f"[session.jsonl] serialize error: {type(e).__name__}: {e}\n")
        return
    try:
        with open(SESSION_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:  # noqa: BLE001 - 写失败不阻塞主流程
        sys.stderr.write(f"[session.jsonl] write failed: {type(e).__name__}: {e}\n")




def _summarize_messages(messages: list) -> list:
    """把 messages 压成可序列化的小条目,便于写入 session.json。"""
    out = []
    for m in messages:
        content = m.get("content")
        if isinstance(content, str):
            text = content
            blocks = None
        else:
            blocks = content if isinstance(content, list) else None
            text = "\n".join(
                b.get("text", "") for b in (blocks or []) if isinstance(b, dict) and b.get("type") == "text"
            )
        item = {"role": m.get("role"), "text": text}
        if blocks:
            item["blocks"] = blocks
        out.append(item)
    return out


def _summarize_response(resp) -> dict:
    """把一次 messages.create 的响应压成可序列化的 dict。"""
    try:
        blocks = extract_blocks(resp)
    except Exception:  # noqa: BLE001
        blocks = []
    usage = getattr(resp, "usage", None)
    return {
        "stop_reason": getattr(resp, "stop_reason", None),
        "model": getattr(resp, "model", None),
        "usage": (
            {
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
            }
            if usage is not None
            else None
        ),
        "blocks": blocks,
    }


# ---------- 工具执行 ----------
def run_tool(call: dict) -> tuple[str, str | None]:
    """
    执行一个 tool_use block。
    返回 (result_str, error_kind or None)
      error_kind: 'unknown_tool' | 'bad_input' | 'exception' | None
    """
    name = call.get("name", "")
    raw_input = call.get("input", {})
    if not isinstance(raw_input, dict):
        return f"[{name}] bad input: expected dict, got {type(raw_input).__name__}", "bad_input"
    runner = TOOL_RUNNERS.get(name)
    if runner is None:
        return f"[{name}] unknown tool", "unknown_tool"
    try:
        result = runner(raw_input)
        return (result if result else "(empty result)"), None
    except Exception as e:  # noqa: BLE001
        return f"[{name}] {type(e).__name__}: {e}", "exception"


# ---------- 序列化辅助 ----------
def extract_blocks(message) -> list[dict]:
    """把 SDK message.content 展开成 list of dict（用于追加到 messages 历史）。"""
    blocks = []
    for blk in message.content or []:
        btype = getattr(blk, "type", None)
        if btype == "text":
            blocks.append({"type": "text", "text": blk.text})
        elif btype == "tool_use":
            blocks.append({
                "type": "tool_use",
                "id": blk.id,
                "name": blk.name,
                "input": blk.input,
            })
        # 其它类型（tool_result 等不会出现在 assistant 消息里）忽略
    return blocks


# ---------- Agent 循环 ----------
def agent_loop(
    client,
    model: str,
    user_prompt: str,
    *,
    messages: list[dict] | None = None,
    max_iters: int = 50,
    system: str = SYSTEM_PROMPT,
    verbose: bool = True,
    contexts: list[ContextBuilder] | None = None,
) -> str:
    """
    跑完整 tool-use 循环，返回最后一条纯文本回答。

    messages: 历史消息列表。如果为 None,创建新对话;否则 append 本轮 user_prompt。
    持续 append assistant + user(tool_results) 到 messages 末尾。
    REPL 模式下,外部持续复用同一个 messages,实现多轮上下文。

    协议（Anthropic / MiniMax 兼容）：
      1. 发起请求，附上 tools 列表
      2. assistant 消息原样进历史（保留 text + tool_use blocks）
      3. 若有 tool_use block → 每个都执行 → 把 tool_result 装进一条 user 消息
      4. 跳回 1，直到响应里没有 tool_use / 达到 max_iters / stop_reason=end_turn
    """
    if messages is None:
        messages = []
    messages.append({"role": "user", "content": user_prompt})
    last_text = ""

    for i in range(1, max_iters + 1):
        if verbose:
            print(f"\n[iter {i}/{max_iters}] >>> model", file=sys.stderr)

        # 1) 拼接 contexts:逐个调用每个 context builder,把结果 append 到一起
        ctx_text = build_contexts(contexts)
        if ctx_text:
            full_system = (system + "\n\n" + ctx_text).strip()
        else:
            full_system = system
        if verbose and ctx_text:
            print(
                f"[contexts] injected {len(ctx_text)} chars from "
                f"{len(DEFAULT_CONTEXTS)} builder(s)",
                file=sys.stderr,
            )

        # 记忆: 记录即将发送给 LLM 的内容(含 contexts 拼接结果)
        _append_memory({
            "kind": "request",
            "iter": i,
            "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
            "system": full_system,
            "messages": _summarize_messages(messages),
        })

        resp = client.messages.create(
            model=model,
            max_tokens=2048,
            system=full_system,
            tools=TOOLS_SPEC,
            messages=messages,
        )

        # 记忆: 记录 LLM 返回的内容
        _append_memory({
            "kind": "response",
            "iter": i,
            "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
            "response": _summarize_response(resp),
        })

        blocks = extract_blocks(resp)
        tool_calls = [b for b in blocks if b["type"] == "tool_use"]
        text_chunks = [b["text"] for b in blocks if b["type"] == "text"]

        if verbose:
            for t in text_chunks:
                if t.strip():
                    print(f"[model text] {t}", file=sys.stderr)
            print(
                f"[stop_reason] {resp.stop_reason} "
                f"(tool_use={len(tool_calls)}, text={len(text_chunks)})",
                file=sys.stderr,
            )

        # 不管 stop_reason 是什么，只要这一轮有 tool_use 就必须执行
        # —— 不然下一轮的 tool_result 会因为找不到 id 而拒绝
        messages.append({"role": "assistant", "content": blocks})

        if not tool_calls:
            last_text = "\n".join(text_chunks).strip()
            if resp.stop_reason != "tool_use":
                # end_turn / max_tokens / refusal —— 当作终态
                return last_text or "(no text)"
            # 理论上不会到这里；保留作为兜底
            return last_text

        # 执行每个工具，组装 tool_result blocks
        result_blocks: list[dict] = []
        for call in tool_calls:
            name = call["name"]
            if verbose:
                print(
                    f"[tool: {name}] input={json.dumps(call['input'], ensure_ascii=False)}",
                    file=sys.stderr,
                )
            content, err = run_tool(call)
            if verbose:
                snippet = content if len(content) < 240 else content[:240] + "..."
                tag = "ERR" if err else "OK"
                print(f"[tool: {name} {tag}] {snippet}", file=sys.stderr)
            result_blocks.append({
                "type": "tool_result",
                "tool_use_id": call["id"],
                "content": content,
                "is_error": bool(err),
            })
        messages.append({"role": "user", "content": result_blocks})

    # max_iters 用完，把最后一轮累积的文本兜底返回
    return last_text or f"[agent] hit max_iters={max_iters}, no final text"


# ---------- REPL ----------
# 协议（与 TUI / 其他前端 的 IPC）：
#   stdin : 每行一个 prompt
#   stdout: 最终回复（多行），以一行 "=== END ===" 结尾
#   stderr: verbose 日志（[iter] / [tool] / [contexts] 等），TUI 可显示给用户
#
# 错误处理：
#   - 任何异常都进 stdout 作为回复内容
#   - 不会因异常退出 REPL（除了 stdin EOF / 显式 exit）
#   - 进程死亡时 TUI 通过 stdout EOF 检测

_END_SENTINEL = "=== END ==="


def _repl_loop(
    client,
    model: str,
    *,
    max_iters: int = 50,
    system: str = SYSTEM_PROMPT,
    verbose: bool = True,
    contexts: list[ContextBuilder] | None = None,
) -> None:
    """
    REPL 模式：从 stdin 读 prompt，跑 agent_loop，把结果写到 stdout。
    直到 stdin EOF / 用户输入 exit/quit 才退出。
    """
    # 告诉前端"我准备好了"
    print("READY", flush=True)

    messages: list[dict] = []  # 跨 turn 累积

    for line in sys.stdin:
        prompt = line.rstrip("\n")
        if prompt in ("exit", "quit"):
            break
        if not prompt.strip():
            # 空行忽略
            continue

        # 这一轮加 user prompt 到 messages,跑完后 messages 自动包含所有 iters
        try:
            final_text = agent_loop(
                client, model, prompt,
                messages=messages,
                max_iters=max_iters,
                system=system,
                verbose=verbose,
                contexts=contexts,
            )
        except Exception as e:
            # 任何异常都进 stdout 作为回复 —— TUI 必须能看到
            final_text = f"[agent error] {type(e).__name__}: {e}"

        # 写回复 + 结束标志
        print(final_text, flush=True)
        print(_END_SENTINEL, flush=True)


def main():
    ap = argparse.ArgumentParser(
        description="Tool-use agent loop on MiniMax (Anthropic-compatible). "
                    "Default: REPL mode (reads prompts from stdin). "
                    "-q/--headless: one-shot mode (one prompt from arg, then exit)."
    )
    ap.add_argument("prompt", nargs="?", default=None,
                    help="User prompt (only used in -q headless mode)")
    ap.add_argument("-q", "--headless", action="store_true",
                    help="headless one-shot mode: process prompt and exit")
    ap.add_argument("--max-iters", type=int, default=50)
    ap.add_argument("--quiet", action="store_true", help="suppress per-iter stderr logs")
    ap.add_argument("--no-contexts", action="store_true",
                    help="disable context builders (skip memory recall etc.)")
    ap.add_argument("--session", metavar="NAME",
                    help="use a named session (eval, batch); error if it exists")

    args = ap.parse_args()

    # 解析 session 文件,设置模块全局
    global SESSION_FILE
    SESSION_FILE = _resolve_session(args)

    sys.stderr.write(f"[session] {SESSION_FILE.stem}\n")
    sys.stderr.write(f"[session] path: {SESSION_FILE}\n")

    env, _ = chat.resolve_settings()
    client, model = chat.make_client(env)
    ctxs: list[ContextBuilder] | None = [] if args.no_contexts else None
    verbose = not args.quiet

    # 模式分发
    if args.headless or args.prompt is not None:
        # one-shot: 必须有 prompt
        if args.prompt is None:
            sys.exit("[error] -q requires a positional prompt")
        final = agent_loop(
            client, model, args.prompt,
            messages=None,
            max_iters=args.max_iters,
            verbose=verbose,
            contexts=ctxs,
        )
        print(final, flush=True)
    else:
        # REPL: 多次 prompt,跨 turn 累积 messages
        _repl_loop(
            client, model,
            max_iters=args.max_iters,
            verbose=verbose,
            contexts=ctxs,
        )


if __name__ == "__main__":
    main()
