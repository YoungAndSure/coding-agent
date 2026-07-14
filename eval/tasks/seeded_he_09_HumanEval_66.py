"""seeded_he_09_HumanEval_66.py | seeded from HumanEval HumanEval/66
类型: write_code(纯函数)
评分: exec 回答里的 Python 代码,定义出 digitSum,再 exec HumanEval 自带的 check(candidate)
"""
TASK = '\ndef digitSum(s):\n    """Task\n    Write a function that takes a string as input and returns the sum of the upper characters only\'\n    ASCII codes.\n\n    Examples:\n        digitSum("") => 0\n        digitSum("abAB") => 131\n        digitSum("abcCd") => 67\n        digitSum("helloE") => 69\n        digitSum("woArBld") => 131\n        digitSum("aAaaaXa") => 153\n    """\n'

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

fn = ns.get("digitSum")
if not callable(fn):
    print(f"FAIL: function 'digitSum' not defined or not callable")
    sys.exit(1)

check_src = 'def check(candidate):\n\n    # Check some simple cases\n    assert True, "This prints if this assert fails 1 (good for debugging!)"\n    assert candidate("") == 0, "Error"\n    assert candidate("abAB") == 131, "Error"\n    assert candidate("abcCd") == 67, "Error"\n    assert candidate("helloE") == 69, "Error"\n    assert candidate("woArBld") == 131, "Error"\n    assert candidate("aAaaaXa") == 153, "Error"\n\n    # Check some edge cases that are easy to work out by hand.\n    assert True, "This prints if this assert fails 2 (also good for debugging!)"\n    assert candidate(" How are yOu?") == 151, "Error"\n    assert candidate("You arE Very Smart") == 327, "Error"\n\n'
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
