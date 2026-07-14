"""seeded_he_08_HumanEval_137.py | seeded from HumanEval HumanEval/137
类型: write_code(纯函数)
评分: exec 回答里的 Python 代码,定义出 compare_one,再 exec HumanEval 自带的 check(candidate)
"""
TASK = '\ndef compare_one(a, b):\n    """\n    Create a function that takes integers, floats, or strings representing\n    real numbers, and returns the larger variable in its given variable type.\n    Return None if the values are equal.\n    Note: If a real number is represented as a string, the floating point might be . or ,\n\n    compare_one(1, 2.5) ➞ 2.5\n    compare_one(1, "2,3") ➞ "2,3"\n    compare_one("5,1", "6") ➞ "6"\n    compare_one("1", 1) ➞ None\n    """\n'

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
try:
    exec(src, ns)
except Exception as e:
    print(f"FAIL: exec error: {e}")
    sys.exit(1)

fn = ns.get("compare_one")
if not callable(fn):
    print(f"FAIL: function 'compare_one' not defined or not callable")
    sys.exit(1)

check_src = 'def check(candidate):\n\n    # Check some simple cases\n    assert candidate(1, 2) == 2\n    assert candidate(1, 2.5) == 2.5\n    assert candidate(2, 3) == 3\n    assert candidate(5, 6) == 6\n    assert candidate(1, "2,3") == "2,3"\n    assert candidate("5,1", "6") == "6"\n    assert candidate("1", "2") == "2"\n    assert candidate("1", 1) == None\n\n    # Check some edge cases that are easy to work out by hand.\n    assert True\n\n'
try:
    exec(check_src, globals())
except Exception as e:
    print(f"FAIL: cannot define check(): {e}")
    sys.exit(1)

try:
    check(fn)
except AssertionError as e:
    print(f"FAIL: check() assertion failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"FAIL: check() raised: {type(e).__name__}: {e}")
    sys.exit(1)

print("PASS")
'''
