"""seeded_mb_09_132.py | seeded from MBPP task_id=132
类型: write_code(纯函数)
评分: exec 回答里的 Python 代码,定义出函数 tup_string,再跑 MBPP 自带 assert 列表
"""
TASK = 'Write a function to convert a tuple to a string.'

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

fn = ns.get("tup_string")
if not callable(fn):
    print(f"FAIL: function 'tup_string' not defined or not callable")
    sys.exit(1)

tests = ['assert tup_string((\'e\', \'x\', \'e\', \'r\', \'c\', \'i\', \'s\', \'e\', \'s\'))==("exercises")', 'assert tup_string((\'p\',\'y\',\'t\',\'h\',\'o\',\'n\'))==("python")', 'assert tup_string((\'p\',\'r\',\'o\',\'g\',\'r\',\'a\',\'m\'))==("program")']
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
