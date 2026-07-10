"""contexts.memory - 从 session.sql 里捞最近 10 条对话,作为 context 喂给 LLM。

约定:
    - 继承 base.ContextBuilder
    - title = "recent conversations"
    - build() 返回一段纯文本,列出最近 10 条 (request, response) 对话
    - 只读 session.sql,失败时返回空串,不影响主流程
"""

from __future__ import annotations

from .base import ContextBuilder


def _get_sql_conn():
    """延迟导入 agent._get_sql_conn,避免 contexts.memory <-> agent 循环依赖。

    只在 build() 真正被调用时才 import,届时 agent.py 早已加载完毕。
    """
    try:
        from agent import _get_sql_conn as _fn  # type: ignore
        return _fn
    except Exception:
        return None


class RecentConversationsContext(ContextBuilder):
    """从 session.sql 里查询最近 10 条对话,按时间倒序展示。"""

    title = "recent conversations"

    def __init__(self, limit: int = 10, **kwargs):
        super().__init__(**kwargs)
        self.limit = int(limit)

    def build(self) -> str:
        get_conn = _get_sql_conn()
        if get_conn is None:
            return ""

        sql = """
            SELECT id, iter, kind, timestamp, payload
            FROM conversations
            ORDER BY id DESC
            LIMIT ?
        """

        try:
            conn = get_conn()
            cur = conn.execute(sql, (self.limit * 4,))  # 多取一些,保证最近 N 轮对话都在窗口里(每轮 ≈2 行)
            rows = cur.fetchall()
        except Exception:
            # 表还没建 / 文件还没创建 —— 当作没历史,安静返回
            return ""

        if not rows:
            return ""

        # rows 按 id DESC 倒序,先反转让它变成正序
        rows = list(reversed(rows))

        by_iter: dict[int, dict[str, tuple]] = {}
        for cid, it, kind, ts, payload in rows:
            bucket = by_iter.setdefault(int(it), {})
            bucket[kind] = (cid, ts, payload)

        # 按 iter 升序,只保留有 request 的轮次,取最后 self.limit 轮
        iters = sorted(by_iter.keys())
        iters = [i for i in iters if "request" in by_iter[i]]
        iters = iters[-self.limit:]

        if not iters:
            return ""

        lines: list[str] = []
        for i in iters:
            req = by_iter[i].get("request")
            resp = by_iter[i].get("response")
            ts = (req or resp or (None, "", ""))[1]
            lines.append(f"[iter {i} @ {ts}]")

            if req is not None:
                _, _, payload = req
                req_text = _extract_request_text(payload)
                if req_text:
                    lines.append("  user:")
                    for ln in req_text.splitlines():
                        lines.append(f"    {ln}")
            if resp is not None:
                _, _, payload = resp
                resp_text = _extract_response_text(payload)
                if resp_text:
                    lines.append("  assistant:")
                    for ln in resp_text.splitlines():
                        lines.append(f"    {ln}")
            lines.append("")

        return "\n".join(lines).rstrip()


def _extract_request_text(payload: str) -> str:
    """从 conversations.payload (JSON) 里抽出 request 的 user 文本。"""
    import json
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return ""

    msgs = data.get("messages") or []
    parts: list[str] = []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        role = m.get("role") or ""
        text = (m.get("text") or "").strip()
        if text:
            parts.append(f"[{role}] {text}")
    return "\n".join(parts)


def _extract_response_text(payload: str) -> str:
    """从 conversations.payload (JSON) 里抽出 response 的文本 / 工具调用。"""
    import json
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return ""

    resp = data.get("response") or {}
    blocks = resp.get("blocks") or []
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
