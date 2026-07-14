"""seeded_mb_00_472.py | seeded from MBPP task_id=472
类型: write_code(纯函数)
评分: exec 回答里的 Python 代码,定义出函数 check_Consecutive,再跑 MBPP 自带 assert 列表
"""
TASK = 'Write a python function to check whether the given list contains consecutive numbers or not.'

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

fn = ns.get("check_Consecutive")
if not callable(fn):
    print(f"FAIL: function 'check_Consecutive' not defined or not callable")
    sys.exit(1)

tests = ['assert check_Consecutive([1,2,3,4,5]) == True', 'assert check_Consecutive([1,2,3,5,6]) == False', 'assert check_Consecutive([1,2,1]) == False']
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
