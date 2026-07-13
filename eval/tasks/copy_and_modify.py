"""Task 03: copy_and_modify
类型: multi_step(读 → 改 → 写 → 验证)
评分: agent 需要 cp 源文件 → 把所有 'foo' 替换成 'bar' → 写入新文件
"""
TASK = (
    "Do the following in the current working directory:\n"
    "1. There is a file called `source.txt`. Read it.\n"
    "2. Create a new file called `output.txt` that is a copy of `source.txt` "
    "   but with every occurrence of the word 'foo' replaced with 'bar'.\n"
    "3. Report when done with just the word 'done' on the last line."
)

GRADER_CODE = r'''
import os, sys, pathlib
ws = pathlib.Path(os.environ["EVAL_WORKDIR"])
out = ws / "output.txt"
src = ws / "source.txt"
if not out.exists():
    print("FAIL: output.txt not created")
    sys.exit(1)
content = out.read_text()
if "foo" in content:
    print(f"FAIL: 'foo' still in output.txt: {content!r}")
    sys.exit(1)
# 检查 source.txt 仍存在且未改
if not src.exists() or "foo" not in src.read_text():
    print("FAIL: source.txt was modified or deleted")
    sys.exit(1)
# 检查内容符合预期
expected = src.read_text().replace("foo", "bar")
if content != expected:
    print(f"FAIL: content mismatch.\nwant={expected!r}\ngot ={content!r}")
    sys.exit(1)
print("PASS")
'''

SETUP_CODE = r'''
import os, pathlib
ws = pathlib.Path(os.environ["EVAL_WORKDIR"])
for p in ws.glob("*"):
    if p.is_file() and p.name != ".ground_truth":
        p.unlink()
(ws / "source.txt").write_text("the foo is here\nand another foo here\nfoo foo foo\n")
'''
