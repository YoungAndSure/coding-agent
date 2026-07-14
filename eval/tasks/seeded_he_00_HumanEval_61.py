"""seeded_he_00_HumanEval_61.py | seeded from HumanEval HumanEval/61
类型: write_code(纯函数)
评分: exec 回答里的 Python 代码,定义出 correct_bracketing,再 exec HumanEval 自带的 check(candidate)
"""
TASK = '\n\ndef correct_bracketing(brackets: str):\n    """ brackets is a string of "(" and ")".\n    return True if every opening bracket has a corresponding closing bracket.\n\n    >>> correct_bracketing("(")\n    False\n    >>> correct_bracketing("()")\n    True\n    >>> correct_bracketing("(()())")\n    True\n    >>> correct_bracketing(")(()")\n    False\n    """\n'

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

fn = ns.get("correct_bracketing")
if not callable(fn):
    print(f"FAIL: function 'correct_bracketing' not defined or not callable")
    sys.exit(1)

check_src = '\n\nMETADATA = {}\n\n\ndef check(candidate):\n    assert candidate("()")\n    assert candidate("(()())")\n    assert candidate("()()(()())()")\n    assert candidate("()()((()()())())(()()(()))")\n    assert not candidate("((()())))")\n    assert not candidate(")(()")\n    assert not candidate("(")\n    assert not candidate("((((")\n    assert not candidate(")")\n    assert not candidate("(()")\n    assert not candidate("()()(()())())(()")\n    assert not candidate("()()(()())()))()")\n\n'
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
