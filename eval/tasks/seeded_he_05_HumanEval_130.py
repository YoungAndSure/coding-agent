"""seeded_he_05_HumanEval_130.py | seeded from HumanEval HumanEval/130
类型: write_code(纯函数)
评分: exec 回答里的 Python 代码,定义出 tri,再 exec HumanEval 自带的 check(candidate)
"""
TASK = '\ndef tri(n):\n    """Everyone knows Fibonacci sequence, it was studied deeply by mathematicians in \n    the last couple centuries. However, what people don\'t know is Tribonacci sequence.\n    Tribonacci sequence is defined by the recurrence:\n    tri(1) = 3\n    tri(n) = 1 + n / 2, if n is even.\n    tri(n) =  tri(n - 1) + tri(n - 2) + tri(n + 1), if n is odd.\n    For example:\n    tri(2) = 1 + (2 / 2) = 2\n    tri(4) = 3\n    tri(3) = tri(2) + tri(1) + tri(4)\n           = 2 + 3 + 3 = 8 \n    You are given a non-negative integer number n, you have to a return a list of the \n    first n + 1 numbers of the Tribonacci sequence.\n    Examples:\n    tri(3) = [1, 3, 2, 8]\n    """\n'

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

fn = ns.get("tri")
if not callable(fn):
    print(f"FAIL: function 'tri' not defined or not callable")
    sys.exit(1)

check_src = 'def check(candidate):\n\n    # Check some simple cases\n    \n    assert candidate(3) == [1, 3, 2.0, 8.0]\n    assert candidate(4) == [1, 3, 2.0, 8.0, 3.0]\n    assert candidate(5) == [1, 3, 2.0, 8.0, 3.0, 15.0]\n    assert candidate(6) == [1, 3, 2.0, 8.0, 3.0, 15.0, 4.0]\n    assert candidate(7) == [1, 3, 2.0, 8.0, 3.0, 15.0, 4.0, 24.0]\n    assert candidate(8) == [1, 3, 2.0, 8.0, 3.0, 15.0, 4.0, 24.0, 5.0]\n    assert candidate(9) == [1, 3, 2.0, 8.0, 3.0, 15.0, 4.0, 24.0, 5.0, 35.0]\n    assert candidate(20) == [1, 3, 2.0, 8.0, 3.0, 15.0, 4.0, 24.0, 5.0, 35.0, 6.0, 48.0, 7.0, 63.0, 8.0, 80.0, 9.0, 99.0, 10.0, 120.0, 11.0]\n\n    # Check some edge cases that are easy to work out by hand.\n    assert candidate(0) == [1]\n    assert candidate(1) == [1, 3]\n'
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
