#!/usr/bin/env python3
"""
chat.py - 调用 MiniMax 的 Anthropic 兼容 API 进行对话

用法:
    # 单轮对话：直接把问题作为参数传入
    python chat.py "你好，请介绍一下你自己"

    # 多轮对话：不带参数进入 REPL，连续多轮交互
    python chat.py

    # 从 stdin 读入（适合管道）
    echo "什么是 Python?" | python chat.py

依赖:
    pip install anthropic

配置来源:
    按以下顺序查找 ~/.claude/settings.json:
      1. ./<cwd>/.claude/settings.json        (项目级)
      2. ~/.claude/settings.json              (用户级)
    从其中读取 env 字段:
      ANTHROPIC_BASE_URL  - 形如 https://api.minimaxi.com/anthropic
      ANTHROPIC_AUTH_TOKEN - API Key
      ANTHROPIC_MODEL     - 形如 MiniMax-M3
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable

import anthropic


SETTINGS_CANDIDATES = (
    Path.cwd() / ".claude" / "settings.json",
    Path.home() / ".claude" / "settings.json",
)


def load_settings(path: Path) -> dict:
    """读取 settings.json，失败时给出清晰报错。"""
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"[错误] 未找到配置文件: {path}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"[错误] {path} 不是合法 JSON: {e}")
    env = data.get("env") or {}
    missing = [k for k in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN") if not env.get(k)]
    if missing:
        raise SystemExit(f"[错误] {path} 缺少 env 字段: {', '.join(missing)}")
    if not env.get("ANTHROPIC_MODEL"):
        env["ANTHROPIC_MODEL"] = "MiniMax-M3"
    return env


def resolve_settings() -> tuple[dict, Path]:
    """按顺序查找第一个存在的 settings.json。"""
    for p in SETTINGS_CANDIDATES:
        if p.is_file():
            return load_settings(p), p
    raise SystemExit(
        "[错误] 在以下位置都未找到 settings.json:\n  - "
        + "\n  - ".join(str(p) for p in SETTINGS_CANDIDATES)
    )


def make_client(env: dict) -> tuple[anthropic.Anthropic, str]:
    """根据 env 配置构造 Anthropic SDK 客户端。"""
    base_url = env["ANTHROPIC_BASE_URL"].rstrip("/")
    api_key = env["ANTHROPIC_AUTH_TOKEN"]
    model = env["ANTHROPIC_MODEL"]
    client = anthropic.Anthropic(base_url=base_url, api_key=api_key)
    return client, model


def build_messages(history: list[dict], user_text: str) -> list[dict]:
    """组装本轮 messages，把刚刚的用户输入追加到历史末尾。"""
    messages = [m for m in history if m["role"] in ("user", "assistant")]
    messages.append({"role": "user", "content": user_text})
    return messages


def chat_once(
    client: anthropic.Anthropic,
    model: str,
    user_text: str,
    history: list[dict] | None = None,
    system: str | None = None,
    max_tokens: int = 1024,
    stream: bool = False,
) -> tuple[str, list[dict]]:
    """单次对话调用，返回 (assistant 回复, 更新后的历史)。"""
    history = list(history or [])
    messages = build_messages(history, user_text)

    kwargs = dict(model=model, max_tokens=max_tokens, messages=messages)
    if system:
        kwargs["system"] = system

    if stream:
        # 流式：实时打印，不返回 token 用量
        with client.messages.stream(**kwargs) as s:
            text_parts: list[str] = []
            for chunk in s.text_stream:
                sys.stdout.write(chunk)
                sys.stdout.flush()
                text_parts.append(chunk)
            print()
            assistant_text = "".join(text_parts).strip()
    else:
        resp = client.messages.create(**kwargs)
        assistant_text = extract_text(resp)

    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": assistant_text})
    return assistant_text, history


def extract_text(message) -> str:
    """从 Message.content 里抽出文本（可能含多 block）。"""
    parts = []
    for block in getattr(message, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return ("\n".join(parts)).strip()


def read_initial_prompt(args: argparse.Namespace) -> str | None:
    """从 CLI 参数 / stdin 收集初始 prompt；都没有就 None 表示进入 REPL。"""
    if args.prompt:
        return args.prompt
    if not sys.stdin.isatty():
        data = sys.stdin.read().strip()
        return data or None
    return None


def run_repl(client: anthropic.Anthropic, model: str, system: str | None) -> None:
    """简单多轮 REPL：空行退出，/clear 清空历史。"""
    history: list[dict] = []
    print(f"[已连接] model={model}  （输入空行或 Ctrl-D 退出，/clear 清空上下文）")
    while True:
        try:
            user_text = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[bye]")
            return
        if not user_text:
            return
        if user_text == "/clear":
            history.clear()
            print("[已清空上下文]")
            continue
        print("AI> ", end="", flush=True)
        _, history = chat_once(client, model, user_text, history, system=system, stream=True)
        # 收紧 history，防止上游有总长度限制
        history = history[-20:]


def main() -> None:
    parser = argparse.ArgumentParser(description="通过 ~/.claude/settings.json 调用 MiniMax Anthropic 兼容 API")
    parser.add_argument("prompt", nargs="?", help="单轮用户输入；省略则从 stdin 读取或进入 REPL")
    parser.add_argument("--system", "-s", default=None, help="system 提示词")
    parser.add_argument("--max-tokens", type=int, default=1024, help="最大输出 token（默认 1024）")
    parser.add_argument("--no-stream", action="store_true", help="关闭流式输出")
    parser.add_argument("--show-config", action="store_true", help="仅打印加载到的配置后退出")
    args = parser.parse_args()

    env, path = resolve_settings()
    if args.show_config:
        # 打印时把 token 隐掉，避免泄漏到日志
        safe = {k: ("***" if "TOKEN" in k or "KEY" in k else v) for k, v in env.items()}
        print(f"[settings] {path}\n{json.dumps(safe, indent=2, ensure_ascii=False)}")
        return

    client, model = make_client(env)
    stream = not args.no_stream

    initial = read_initial_prompt(args)
    if initial is None:
        run_repl(client, model, system=args.system)
        return

    # 单轮模式：history 不持久
    if stream:
        # 仍然走 chat_once 流式分支，但给出明确的"单轮"语义
        print("AI> ", end="", flush=True)
        chat_once(
            client, model, initial,
            history=None, system=args.system,
            max_tokens=args.max_tokens, stream=True,
        )
    else:
        text, _ = chat_once(
            client, model, initial,
            history=None, system=args.system,
            max_tokens=args.max_tokens, stream=False,
        )
        print(text)


if __name__ == "__main__":
    main()
