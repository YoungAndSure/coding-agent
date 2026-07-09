#!/usr/bin/env python3
"""
step 1 的"行模式"对照版 —— 没有 tty.setraw，按 Enter 才把整行送给程序。

跑：python tui_step1_line.py
退：输入 quit 回车，或者 Ctrl-C
"""
import sys

# 注意：没 tty.setraw，没 termios，没 read(1) —— 全是"普通 Python"
try:
    while True:
        line = input("❯ ")                  # ← 整行读，Enter 提交
        if line.strip() in ("quit", "exit"):
            break
        print(f"got: {line!r}  length={len(line)}")
except EOFError:
    pass                                    # Ctrl-D / 管道结束
