"""contexts.memory - 从 session.json 里捞最近 10 条对话,作为 context 喂给 LLM。

约定:
    - 继承 base.ContextBuilder
    - title = "recent conversations"
    - build() 返回一段纯文本,列出最近 10 条 (request, response) 对话
    - 只读 session.json,失败时返回空串,不影响主流程
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import ContextBuilder


class RecentConversationsContext(ContextBuilder):
    """从 session.json 读取最近 N 轮对话,按时间正序展示。"""

    title = "recent conversations"

    def __init__(self, limit: int = 10, **kwargs):
        super().__init__(**kwargs)
        self.limit = int(limit)

    def build(self) -> str:
        try:
            from code_agent.exec_loop.agent import MEMORY_FILE
        except Exception:
            return ""

        try:
            raw = Path(MEMORY_FILE).read_text(encoding="utf-8") or "[]"
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            return ""

        if not isinstance(data, list) or not data:
            return ""

        # 按时序正序排列(已 append 的天然就是时序)
        by_iter: dict[int, dict[str, dict]] = {}
        for entry in data:
            if not isinstance(entry, dict):
                continue
            it = entry.get("iter")
            kind = entry.get("kind")
            if not isinstance(it, int) or kind not in ("request", "response"):
                continue
            by_iter.setdefault(it, {})[kind] = entry

        # 只保留有 request 的轮次,取最后 self.limit 轮
        iters = sorted(by_iter.keys())
        iters = [i for i in iters if "request" in by_iter[i]]
        iters = iters[-self.limit:]

        if not iters:
            return ""

        lines: list[str] = []
        for i in iters:
            req = by_iter[i].get("request")
            resp = by_iter[i].get("response")
            ts = (req or resp or {}).get("timestamp", "")
            lines.append(f"[iter {i} @ {ts}]")

            if req is not None:
                req_text = _extract_request_text(req)
                if req_text:
                    lines.append("  user:")
                    for ln in req_text.splitlines():
                        lines.append(f"    {ln}")
            if resp is not None:
                resp_text = _extract_response_text(resp)
                if resp_text:
                    lines.append("  assistant:")
                    for ln in resp_text.splitlines():
                        lines.append(f"    {ln}")
            lines.append("")

        return "\n".join(lines).rstrip()


def _extract_request_text(req: dict) -> str:
    """从一条 request entry 抽出 user 文本。"""
    msgs = req.get("messages") or []
    parts: list[str] = []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        role = m.get("role") or ""
        text = (m.get("text") or "").strip()
        if text:
            parts.append(f"[{role}] {text}")
    return "\n".join(parts)


def _extract_response_text(resp: dict) -> str:
    """从一条 response entry 抽出 text / tool_use 文本。"""
    blocks = (resp.get("response") or {}).get("blocks") or []
    parts: list[str] = []
    for b in blocks:
        if not isinstance(b, dict):
            continue
        btype = b.get("type")
        if btype == "text":
            t = (b.get("text") or "").strip()
            if t:
                parts.append(t)
        elif btype == "tool_use":
            name = b.get("name", "?")
            inp = b.get("input") or {}
            parts.append(f"[tool_use: {name}] {inp}")
    return "\n".join(parts)
