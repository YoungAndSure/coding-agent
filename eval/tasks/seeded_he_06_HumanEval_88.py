"""seeded_he_06_HumanEval_88.py | seeded from HumanEval HumanEval/88
类型: write_code(纯函数)
评分: exec 回答里的 Python 代码,定义出 sort_array,再 exec HumanEval 自带的 check(candidate)
"""
TASK = '\ndef sort_array(array):\n    """\n    Given an array of non-negative integers, return a copy of the given array after sorting,\n    you will sort the given array in ascending order if the sum( first index value, last index value) is odd,\n    or sort it in descending order if the sum( first index value, last index value) is even.\n\n    Note:\n    * don\'t change the given array.\n\n    Examples:\n    * sort_array([]) => []\n    * sort_array([5]) => [5]\n    * sort_array([2, 4, 3, 0, 1, 5]) => [0, 1, 2, 3, 4, 5]\n    * sort_array([2, 4, 3, 0, 1, 5, 6]) => [6, 5, 4, 3, 2, 1, 0]\n    """\n'

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

fn = ns.get("sort_array")
if not callable(fn):
    print(f"FAIL: function 'sort_array' not defined or not callable")
    sys.exit(1)

check_src = 'def check(candidate):\n\n    # Check some simple cases\n    assert True, "This prints if this assert fails 1 (good for debugging!)"\n    assert candidate([]) == [], "Error"\n    assert candidate([5]) == [5], "Error"\n    assert candidate([2, 4, 3, 0, 1, 5]) == [0, 1, 2, 3, 4, 5], "Error"\n    assert candidate([2, 4, 3, 0, 1, 5, 6]) == [6, 5, 4, 3, 2, 1, 0], "Error"\n\n    # Check some edge cases that are easy to work out by hand.\n    assert True, "This prints if this assert fails 2 (also good for debugging!)"\n    assert candidate([2, 1]) == [1, 2], "Error"\n    assert candidate([15, 42, 87, 32 ,11, 0]) == [0, 11, 15, 32, 42, 87], "Error"\n    assert candidate([21, 14, 23, 11]) == [23, 21, 14, 11], "Error"\n\n'
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
