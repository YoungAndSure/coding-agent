"""seeded_mb_05_447.py | seeded from MBPP task_id=447
类型: write_code(纯函数)
评分: exec 回答里的 Python 代码,定义出函数 cube_nums,再跑 MBPP 自带 assert 列表
"""
TASK = 'Write a function to find cubes of individual elements in a list.'

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

fn = ns.get("cube_nums")
if not callable(fn):
    print(f"FAIL: function 'cube_nums' not defined or not callable")
    sys.exit(1)

tests = ['assert cube_nums([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])==[1, 8, 27, 64, 125, 216, 343, 512, 729, 1000]', 'assert cube_nums([10,20,30])==([1000, 8000, 27000])', 'assert cube_nums([12,15])==([1728, 3375])']
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
