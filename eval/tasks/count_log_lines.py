"""Task 02: count_log_lines
类型: bash_task(需要 bash 工具)
评分: 在工作区生成 3 个 .log 文件 + 2 个 .txt,然后 agent 统计 .log 总行数
"""
TASK = (
    "Look in the current working directory. There are several .log files mixed "
    "with other files. Count the TOTAL number of lines across ALL .log files "
    "(sum them up). Reply with just one number, nothing else. Example: 42"
)

GRADER_CODE = r'''
import re, sys
text = sys.stdin.read().strip()
# 提取最后一个整数
nums = re.findall(r"-?\d+", text)
if not nums:
    print("FAIL: no number in response")
    sys.exit(1)
got = int(nums[-1])
# 真实值由 setup() 写进 GROUND_TRUTH 环境变量
import os
want = int(os.environ["GROUND_TRUTH"])
if got == want:
    print("PASS")
else:
    print(f"FAIL: want={want} got={got}")
    sys.exit(1)
'''

# 这个题的 setup 字段会被 runner 识别,在跑 agent 之前执行
SETUP_CODE = r'''
import os, pathlib
ws = pathlib.Path(os.environ["EVAL_WORKDIR"])
# 清理旧文件
for p in ws.glob("*"):
    if p.is_file():
        p.unlink()
# 3 个 .log,2 个 .txt
(ws / "a.log").write_text("line1\nline2\nline3\n")  # 3
(ws / "b.log").write_text("x\ny\n")  # 2
(ws / "c.log").write_text("1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n")  # 10
(ws / "readme.txt").write_text("ignore me")
(ws / "notes.md").write_text("# also ignore")
# 总计 15
with open(ws / ".ground_truth", "w") as f:
    f.write("15")
'''

# 检查 .ground_truth 文件的另一种方式
def ground_truth():
    return 15
