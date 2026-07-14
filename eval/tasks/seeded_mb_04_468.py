"""seeded_mb_04_468.py | seeded from MBPP task_id=468
类型: write_code(纯函数)
评分: exec 回答里的 Python 代码,定义出函数 max_product,再跑 MBPP 自带 assert 列表
"""
TASK = 'Write a function to find the maximum product formed by multiplying numbers of an increasing subsequence of that array.'

GRADER_CODE = r'''
import re, sys

text = sys.stdin.read()

def strip_fences(s):
    fences = re.findall(r"```(?:python|py)?\s*\n(.*?)```", s, flags=re.DOTALL)
    if fences:
        return "\n".join(fences)
    return s

src = strip_fences(text)

ns = {}
import_lines = []
try:
    for ln in import_lines:
        if ln and ln.strip():
            exec(ln, ns)
    exec(src, ns)
except Exception as e:
    print(f"FAIL: exec error: {e}")
    sys.exit(1)

fn = ns.get("max_product")
if not callable(fn):
    print(f"FAIL: function 'max_product' not defined or not callable")
    sys.exit(1)

tests = ['assert max_product([3, 100, 4, 5, 150, 6]) == 3000', 'assert max_product([4, 42, 55, 68, 80]) == 50265600', 'assert max_product([10, 22, 9, 33, 21, 50, 41, 60]) == 2460']
for t in tests:
    try:
        exec(t, ns)
    except AssertionError as e:
        print(f"FAIL: {t} -> {e}")
        sys.exit(1)
    except Exception as e:
        print(f"FAIL: {t} -> {type(e).__name__}: {e}")
        sys.exit(1)

print("PASS")
'''
