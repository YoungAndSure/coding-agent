"""seeded_he_02_HumanEval_105.py | seeded from HumanEval HumanEval/105
类型: write_code(纯函数)
评分: exec 回答里的 Python 代码,定义出 by_length,再 exec HumanEval 自带的 check(candidate)
"""
TASK = '\ndef by_length(arr):\n    """\n    Given an array of integers, sort the integers that are between 1 and 9 inclusive,\n    reverse the resulting array, and then replace each digit by its corresponding name from\n    "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine".\n\n    For example:\n      arr = [2, 1, 1, 4, 5, 8, 2, 3]   \n            -> sort arr -> [1, 1, 2, 2, 3, 4, 5, 8] \n            -> reverse arr -> [8, 5, 4, 3, 2, 2, 1, 1]\n      return ["Eight", "Five", "Four", "Three", "Two", "Two", "One", "One"]\n    \n      If the array is empty, return an empty array:\n      arr = []\n      return []\n    \n      If the array has any strange number ignore it:\n      arr = [1, -1 , 55] \n            -> sort arr -> [-1, 1, 55]\n            -> reverse arr -> [55, 1, -1]\n      return = [\'One\']\n    """\n'

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

fn = ns.get("by_length")
if not callable(fn):
    print(f"FAIL: function 'by_length' not defined or not callable")
    sys.exit(1)

check_src = 'def check(candidate):\n\n    # Check some simple cases\n    assert True, "This prints if this assert fails 1 (good for debugging!)"\n    assert candidate([2, 1, 1, 4, 5, 8, 2, 3]) == ["Eight", "Five", "Four", "Three", "Two", "Two", "One", "One"], "Error"\n    assert candidate([]) == [], "Error"\n    assert candidate([1, -1 , 55]) == [\'One\'], "Error"\n\n    # Check some edge cases that are easy to work out by hand.\n    assert True, "This prints if this assert fails 2 (also good for debugging!)"\n    assert candidate([1, -1, 3, 2]) == ["Three", "Two", "One"]\n    assert candidate([9, 4, 8]) == ["Nine", "Eight", "Four"]\n\n'
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
