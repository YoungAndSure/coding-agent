"""seeded_he_04_HumanEval_145.py | seeded from HumanEval HumanEval/145
类型: write_code(纯函数)
评分: exec 回答里的 Python 代码,定义出 order_by_points,再 exec HumanEval 自带的 check(candidate)
"""
TASK = '\ndef order_by_points(nums):\n    """\n    Write a function which sorts the given list of integers\n    in ascending order according to the sum of their digits.\n    Note: if there are several items with similar sum of their digits,\n    order them based on their index in original list.\n\n    For example:\n    >>> order_by_points([1, 11, -1, -11, -12]) == [-1, -11, 1, -12, 11]\n    >>> order_by_points([]) == []\n    """\n'

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

fn = ns.get("order_by_points")
if not callable(fn):
    print(f"FAIL: function 'order_by_points' not defined or not callable")
    sys.exit(1)

check_src = 'def check(candidate):\n\n    # Check some simple cases\n    assert candidate([1, 11, -1, -11, -12]) == [-1, -11, 1, -12, 11]\n    assert candidate([1234,423,463,145,2,423,423,53,6,37,3457,3,56,0,46]) == [0, 2, 3, 6, 53, 423, 423, 423, 1234, 145, 37, 46, 56, 463, 3457]\n    assert candidate([]) == []\n    assert candidate([1, -11, -32, 43, 54, -98, 2, -3]) == [-3, -32, -98, -11, 1, 2, 43, 54]\n    assert candidate([1,2,3,4,5,6,7,8,9,10,11]) == [1, 10, 2, 11, 3, 4, 5, 6, 7, 8, 9]\n    assert candidate([0,6,6,-76,-21,23,4]) == [-76, -21, 0, 4, 23, 6, 6]\n\n    # Check some edge cases that are easy to work out by hand.\n    assert True, "This prints if this assert fails 2 (also good for debugging!)"\n\n'
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
