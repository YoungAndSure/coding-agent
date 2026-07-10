#!/usr/bin/env python3
"""
tui_demo.py - 一个最简 TUI：底部输入框 + 上方历史区 + 分隔线

【重要】这个文件就是 Ink / Textual / blessed 等库在底层干的事，
        只是没人替你写好。读懂这个，再看任何 TUI 库都秒懂。

运行：python tui_demo.py
退出：Ctrl-C
"""
import os, sys, tty, termios, select

# ============================================================================
# 1. ANSI 转义码：终端的"汇编指令"，库帮你封好的就是这些
# ============================================================================
CLEAR      = "\x1b[2J\x1b[H"          # 清整屏 + 光标回 (0,0)
HIDE_CUR   = "\x1b[?25l"              # 隐藏光标
SHOW_CUR   = "\x1b[?25h"              # 显示光标
CLEAR_LINE = "\x1b[2K"                # 清掉当前行
MOVE       = lambda y, x: f"\x1b[{y};{x}H"   # 光标跳到第 y 行第 x 列
BOLD, DIM, RST = "\x1b[1m", "\x1b[2m", "\x1b[0m"
CYAN, MAG, GRN = "\x1b[36m", "\x1b[35m", "\x1b[32m"


# ============================================================================
# 2. 状态：就是两个变量，UI 完全是这两个变量的"投影"
# ============================================================================
# messages: 历史     [(who, text), ...]
# draft:    正在编辑的一行
# 库不会让状态消失；无论 Ink / Textual / React，最终都是把这个 state 画到屏幕。


# ============================================================================
# 3. 渲染：把 state 完整画一遍（每次按键都全量重画）
#    ---- 这就是 "re-render"，React 的精髓 ----
# ============================================================================
def render(messages, draft):
    h, w = map(int, os.popen("stty size", "r").read().split())
    out = [CLEAR]

    # ------ 顶部：历史消息流 ------
    y = 1
    for who, text in messages[-10:]:
        if y >= h - 3:                # 别画到分隔线下面
            break
        tag = f"{MAG}你 ❯{RST}" if who == "user" else f"{CYAN}AI ❯{RST}"
        # 移动光标 → 清行 → 写一行
        out.append(f"{MOVE(y,1)}{CLEAR_LINE}{tag} {text}")
        y += 1

    # ------ 中部：分隔线 ------
    out.append(f"{MOVE(h - 3, 1)}{DIM}{'─' * w}{RST}")

    # ------ 底部：输入框 ------
    # {GRN}❯{RST} 是绿色 ❯，{BOLD}{draft}{RST} 是加粗的 draft，结尾 _ 是"光标"
    out.append(f"{MOVE(h - 1, 1)}{CLEAR_LINE}{GRN}❯{RST} {BOLD}{draft}{RST}_")
    sys.stdout.write("".join(out)); sys.stdout.flush()


# ============================================================================
# 4. 非阻塞读键：不阻塞就拿不到按键；阻塞太死，动画就废了
#    ---- 库里的 useInput / getch 都是这个 ----
# ============================================================================
def read_key(fd, t=0.03):
    r, _, _ = select.select([fd], [], [], t)
    return os.read(fd, 1).decode("utf-8", "replace") if r else None


# ============================================================================
# 5. 主循环：核心就 4 行 —— 读键、改 state、重画、循环
# ============================================================================
def main():
    fd = sys.stdin.fileno()

    # --- 5a. 把终端从"行模式"切到"raw 模式" ---
    # 不切的话，按一个键要等回车才送给程序；TUI 必须每个按键立刻送达。
    old = termios.tcgetattr(fd)
    tty.setraw(fd)
    sys.stdout.write(HIDE_CUR); sys.stdout.flush()

    messages, draft = [], ""

    try:
        while True:
            render(messages, draft)        # ← 每次循环都全量重画
            ch = read_key(fd)              # ← 阻塞 30ms 拿 1 字符
            if ch is None:
                continue

            # 把按键翻译成"对 state 的修改"
            if ch == "\x03":                                    # Ctrl-C
                break
            elif ch in ("\r", "\n"):                            # Enter
                if draft.strip():
                    messages.append(("user", draft))
                    messages.append(("assistant", "[echo] " + draft))  # 假装 AI 回
                    draft = ""
            elif ch in ("\x7f", "\b"):                          # Backspace
                draft = draft[:-1]
            elif ch == "\x1b":                                  # ESC 序列（方向键等）
                read_key(fd); read_key(fd)                      # 吞掉后两字节，简化
            elif ch.isprintable():
                draft += ch
    finally:
        # 5b. 把终端还回去，不然你 shell 会很奇怪
        sys.stdout.write(f"{SHOW_CUR}{RST}\n")
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.flush()


if __name__ == "__main__":
    main()
