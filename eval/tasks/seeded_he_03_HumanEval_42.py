"""seeded_he_03_HumanEval_42.py | seeded from HumanEval HumanEval/42
类型: write_code(纯函数)
评分: exec 回答里的 Python 代码,定义出 incr_list,再 exec HumanEval 自带的 check(candidate)
"""
TASK = '\n\ndef incr_list(l: list):\n    """Return list with elements incremented by 1.\n    >>> incr_list([1, 2, 3])\n    [2, 3, 4]\n    >>> incr_list([5, 3, 5, 2, 3, 3, 9, 0, 123])\n    [6, 4, 6, 3, 4, 4, 10, 1, 124]\n    """\n'

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

fn = ns.get("incr_list")
if not callable(fn):
    print(f"FAIL: function 'incr_list' not defined or not callable")
    sys.exit(1)

check_src = '\n\nMETADATA = {}\n\n\ndef check(candidate):\n    assert candidate([]) == []\n    assert candidate([3, 2, 1]) == [4, 3, 2]\n    assert candidate([5, 2, 5, 2, 3, 3, 9, 0, 123]) == [6, 3, 6, 3, 4, 4, 10, 1, 124]\n\n'
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
