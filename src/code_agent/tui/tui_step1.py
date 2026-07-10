#!/usr/bin/env python3
"""
step 1: 最最最基础 — 按啥键就打印它的字符编号。

跑：python tui_step1.py
退：Ctrl-C
"""
import sys, tty, termios

fd = sys.stdin.fileno()
old = termios.tcgetattr(fd)        # 记住终端旧设置，等会儿还原
#tty.setraw(fd)                     # 切到 raw 模式：按键立刻到达，不等回车

try:
    while True:
        b = sys.stdin.read(1)      # 阻塞读 1 个字符（按键）
        print(f"got: {b!r}  codepoint=U+{ord(b):04X}", end="\r\n", flush=True)
        if b == "\x03":            # Ctrl-C
            break
finally:
    termios.tcsetattr(fd, termios.TCSADRAIN, old)   # 把终端还回去
