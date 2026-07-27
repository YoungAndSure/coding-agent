"""contexts.base - 所有 context builder 的基类。

约定:
    - 子类的 __init__ 接收构造所需的输入(路径/数据/配置等)
    - 子类必须实现 build() -> str,返回一段纯文本 context
    - build() 可以是纯计算,也可以读文件 / 调工具,但应尽量**廉价**,
      因为每轮发给模型前都会调用一次。
"""

from __future__ import annotations


class ContextBuilder:
    """一个 context builder = 一段结构化文本,会拼到 system prompt 里。"""

    # 子类可以覆盖:在最终拼接时用作小标题
    title: str = "context"

    def __init__(self, **kwargs):
        # 接受任意关键字参数,子类在自己的 __init__ 里挑自己需要的
        self.kwargs = kwargs

    def build(self) -> str:
        """返回一段 context 文本;为空字符串表示这一轮不贡献内容。"""
        raise NotImplementedError

    def render(self) -> str:
        """返回 build() 的纯文本。LLM 不需要 markdown 装饰;空内容返回空串。"""
        return (self.build() or "").strip()
