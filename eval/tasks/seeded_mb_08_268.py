"""seeded_mb_08_268.py | seeded from MBPP task_id=268
类型: write_code(纯函数)
评分: exec 回答里的 Python 代码,定义出函数 find_star_num,再跑 MBPP 自带 assert 列表
"""
TASK = "Write a function to find the n'th star number."

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

fn = ns.get("find_star_num")
if not callable(fn):
    print(f"FAIL: function 'find_star_num' not defined or not callable")
    sys.exit(1)

tests = ['assert find_star_num(3) == 37', 'assert find_star_num(4) == 73', 'assert find_star_num(5) == 121']
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
