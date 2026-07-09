#!/usr/bin/env python3
"""
agent.py - MiniMax 上的工具调用 agent 循环

复用 chat.py 的配置加载与客户端构造。在它之上加：
  1. 一组内置工具（bash / read_file / calc / current_time）
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
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable, Iterable

import chat  # 复用 resolve_settings / make_client


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


def tool_calc(input_: dict) -> str:
    """受限 eval：算术 / 列表 / 字典等表达式；不允许 import 或访问危险属性。"""
    expr = input_.get("expr", "")
    if not expr:
        return "[calc] empty expr"
    try:
        # 清掉内置；通过 __class__/__mro__ 的 gadget chain 仍可能漏，
        # 仅适合本机 demo，**不要用于不可信输入**。
        # noqa: S307 - 故意在受控环境里 eval
        return str(eval(expr, {"__builtins__": {}}))
    except Exception as e:  # noqa: BLE001 - 把所有异常当字符串还回去
        return f"[calc error] {type(e).__name__}: {e}"


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
        "name": "calc",
        "description": "Evaluate a Python expression (arithmetic, list, dict, etc.) and return its repr.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expr": {"type": "string", "description": "Python expression"},
            },
            "required": ["expr"],
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
    "calc": tool_calc,
    "current_time": tool_current_time,
}

SYSTEM_PROMPT = (
    "You are a helpful assistant with a small toolbox. "
    "Use tools when they help. When you have a complete answer, just write it in plain text. "
    "Keep answers concise."
)


# ---------- 记忆系统 ----------
MEMORY_DIR = Path.cwd() / ".codeagent"
MEMORY_FILE = MEMORY_DIR / "memory.json"
MEMORY_SQL = MEMORY_DIR / "memory.sql"  # SQLite 数据库 (单文件,后缀 .sql 仅约定)

_SQL_LOCK = threading.Lock()
_SQL_CONN: sqlite3.Connection | None = None

_MEMORY_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS conversations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    iter         INTEGER NOT NULL,
    kind         TEXT    NOT NULL CHECK(kind IN ('request','response')),
    timestamp    TEXT    NOT NULL,
    system       TEXT,
    payload      TEXT    NOT NULL,
    created_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_conv_iter ON conversations(iter);
CREATE INDEX IF NOT EXISTS idx_conv_kind ON conversations(kind);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    iter            INTEGER NOT NULL,
    kind            TEXT    NOT NULL,
    role            TEXT,
    seq             INTEGER NOT NULL,
    text            TEXT,
    blocks_json     TEXT
);

CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_msg_iter ON messages(iter);
"""


def _ensure_memory() -> None:
    """确保 .codeagent/memory.json 与 .codeagent/memory.sql 都存在。"""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    if not MEMORY_FILE.exists():
        MEMORY_FILE.write_text("[]", encoding="utf-8")
    _get_sql_conn()  # 触发建表


def _get_sql_conn() -> sqlite3.Connection:
    """获取(或懒初始化)SQLite 连接。进程内单例,线程安全。"""
    global _SQL_CONN
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    with _SQL_LOCK:
        if _SQL_CONN is None:
            _SQL_CONN = sqlite3.connect(str(MEMORY_SQL), check_same_thread=False)
            _SQL_CONN.executescript(_MEMORY_SCHEMA)
            _SQL_CONN.commit()
        return _SQL_CONN


def _sql_insert_entry(entry: dict, payload_text: str) -> None:
    """把一条记忆条目写进 SQLite。失败不阻塞 JSON 主流程。"""
    try:
        conn = _get_sql_conn()
        kind = entry.get("kind", "")
        cur = conn.execute(
            "INSERT INTO conversations(iter, kind, timestamp, system, payload) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                int(entry.get("iter", 0)),
                kind,
                entry.get("timestamp", ""),
                entry.get("system"),
                payload_text,
            ),
        )
        conv_id = cur.lastrowid

        rows: list[tuple] = []
        if kind == "request":
            for seq, m in enumerate(entry.get("messages") or []):
                if not isinstance(m, dict):
                    continue
                rows.append((
                    conv_id,
                    int(entry.get("iter", 0)),
                    kind,
                    m.get("role"),
                    seq,
                    m.get("text"),
                    json.dumps(m.get("blocks"), ensure_ascii=False) if m.get("blocks") else None,
                ))
        elif kind == "response":
            resp = entry.get("response") or {}
            usage = resp.get("usage") or {}
            # response 没有按 message 拆开,但 blocks 数组本身就是顺序的
            for seq, b in enumerate(resp.get("blocks") or []):
                if not isinstance(b, dict):
                    continue
                rows.append((
                    conv_id,
                    int(entry.get("iter", 0)),
                    kind,
                    "assistant",
                    seq,
                    b.get("text"),
                    json.dumps(b, ensure_ascii=False) if b.get("type") != "text" else None,
                ))
            # 额外把 usage 记到 text 字段,便于 grep
            if usage:
                rows.append((
                    conv_id,
                    int(entry.get("iter", 0)),
                    kind + "_usage",
                    None,
                    len(rows),
                    json.dumps(usage, ensure_ascii=False),
                    None,
                ))

        if rows:
            conn.executemany(
                "INSERT INTO messages(conversation_id, iter, kind, role, seq, text, blocks_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        conn.commit()
    except Exception as e:  # noqa: BLE001 - SQL 是辅助存储,失败不应影响主流程
        sys.stderr.write("[memory.sql] write failed: " + type(e).__name__ + ": " + str(e) + chr(10))


def _append_memory(entry: dict) -> None:
    """把一条记录 append 到 .codeagent/memory.json,同步落库到 memory.sql。"""
    _ensure_memory()
    try:
        raw = MEMORY_FILE.read_text(encoding="utf-8") or "[]"
        data = json.loads(raw)
        if not isinstance(data, list):
            data = []
    except (json.JSONDecodeError, OSError):
        data = []
    data.append(entry)
    payload_text = json.dumps(entry, ensure_ascii=False, indent=2)
    MEMORY_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # 同步写入 SQL
    _sql_insert_entry(entry, payload_text)


def query_memory(sql: str, params: Iterable = ()) -> list[tuple]:
    """只读便捷查询(供调试 / 脚本使用)。"""
    conn = _get_sql_conn()
    cur = conn.execute(sql, tuple(params))
    return cur.fetchall()


def _summarize_messages(messages: list) -> list:
    """把 messages 压成可序列化的小条目,便于写入 memory.json。"""
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
    max_iters: int = 50,
    system: str = SYSTEM_PROMPT,
    verbose: bool = True,
) -> str:
    """
    跑完整 tool-use 循环，返回最后一条纯文本回答。

    协议（Anthropic / MiniMax 兼容）：
      1. 发起请求，附上 tools 列表
      2. assistant 消息原样进历史（保留 text + tool_use blocks）
      3. 若有 tool_use block → 每个都执行 → 把 tool_result 装进一条 user 消息
      4. 跳回 1，直到响应里没有 tool_use / 达到 max_iters / stop_reason=end_turn
    """
    messages: list[dict] = [{"role": "user", "content": user_prompt}]
    last_text = ""

    for i in range(1, max_iters + 1):
        if verbose:
            print(f"\n[iter {i}/{max_iters}] >>> model", file=sys.stderr)

        # 记忆: 记录即将发送给 LLM 的内容
        _append_memory({
            "kind": "request",
            "iter": i,
            "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
            "system": system,
            "messages": _summarize_messages(messages),
        })

        resp = client.messages.create(
            model=model,
            max_tokens=2048,
            system=system,
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


def main():
    ap = argparse.ArgumentParser(
        description="Tool-use agent loop on MiniMax (Anthropic-compatible)."
    )
    ap.add_argument("prompt", help="User prompt")
    ap.add_argument("--max-iters", type=int, default=50)
    ap.add_argument("--quiet", action="store_true", help="suppress per-iter stderr logs")
    args = ap.parse_args()

    env, _ = chat.resolve_settings()
    client, model = chat.make_client(env)
    final = agent_loop(
        client, model, args.prompt,
        max_iters=args.max_iters,
        verbose=not args.quiet,
    )
    print(final)


if __name__ == "__main__":
    main()
