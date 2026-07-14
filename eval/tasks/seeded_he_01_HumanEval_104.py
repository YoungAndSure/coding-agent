"""seeded_he_01_HumanEval_104.py | seeded from HumanEval HumanEval/104
类型: write_code(纯函数)
评分: exec 回答里的 Python 代码,定义出 unique_digits,再 exec HumanEval 自带的 check(candidate)
"""
TASK = '\ndef unique_digits(x):\n    """Given a list of positive integers x. return a sorted list of all \n    elements that hasn\'t any even digit.\n\n    Note: Returned list should be sorted in increasing order.\n    \n    For example:\n    >>> unique_digits([15, 33, 1422, 1])\n    [1, 15, 33]\n    >>> unique_digits([152, 323, 1422, 10])\n    []\n    """\n'

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

fn = ns.get("unique_digits")
if not callable(fn):
    print(f"FAIL: function 'unique_digits' not defined or not callable")
    sys.exit(1)

check_src = 'def check(candidate):\n\n    # Check some simple cases\n    assert candidate([15, 33, 1422, 1]) == [1, 15, 33]\n    assert candidate([152, 323, 1422, 10]) == []\n    assert candidate([12345, 2033, 111, 151]) == [111, 151]\n    assert candidate([135, 103, 31]) == [31, 135]\n\n    # Check some edge cases that are easy to work out by hand.\n    assert True\n\n'
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
