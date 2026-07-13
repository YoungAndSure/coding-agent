"""Task 01: sort_integers
类型: write_code(纯算法,只需文字+代码)
评分: 提取回答里的 Python 函数定义,跑测试(支持 markdown code fence)
"""
TASK = (
    "Write a Python function `sort_integers(nums: list[int]) -> list[int]` "
    "that returns a new list with the integers in ascending order. "
    "Do NOT modify the input. Just give me the function definition, nothing else."
)

GRADER_CODE = r'''
import re, sys

text = sys.stdin.read()

# 先剥 markdown code fence(```python ... ``` 或 ``` ... ```)
def strip_fences(s: str) -> str:
    # 取所有 fence 块;如果有 fence,优先取 ```python/``` 内容
    fences = re.findall(r"```(?:python|py)?\s*\n(.*?)```", s, flags=re.DOTALL)
    if fences:
        return "\n".join(fences)
    return s

candidates = []
# 在去 fence 后的文本里找 def sort_integers
for chunk in [strip_fences(text), text]:
    m = re.search(r"def\s+sort_integers\s*\([^)]*\)\s*->\s*[^:]+:[^\n]*(?:\n[^\n]*)*", chunk)
    if m:
        candidates.append(m.group(0))

if not candidates:
    print(f"FAIL: no sort_integers function found. output preview: {text[:200]!r}")
    sys.exit(1)

body = candidates[0]

ns = {}
try:
    exec(body, ns)
except Exception as e:
    print(f"FAIL: syntax/runtime error in function: {e}")
    sys.exit(1)

fn = ns.get("sort_integers")
if not callable(fn):
    print("FAIL: sort_integers not defined as callable")
    sys.exit(1)

cases = [
    ([3, 1, 2], [1, 2, 3]),
    ([], []),
    ([5], [5]),
    ([2, 2, 1, 1], [1, 1, 2, 2]),
    ([-1, -5, 0, 3], [-5, -1, 0, 3]),
    ([9, 8, 7, 6, 5, 4, 3, 2, 1], [1, 2, 3, 4, 5, 6, 7, 8, 9]),
]
for inp, want in cases:
    got = fn(list(inp))
    if got != want:
        print(f"FAIL: input={inp} want={want} got={got}")
        sys.exit(1)
    if inp != list(inp):
        print("FAIL: input was mutated")
        sys.exit(1)
print("PASS")
'''