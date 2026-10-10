"""
ORBITAL OS AUTO-LEARNED SKILL: Python Code Scratchpad
"""
import ast
import sys

NAME = "Python Code Scratchpad"
DESCRIPTION = "Safe single-expression / script evaluator."
KEYWORDS = ["run code", "eval", "scratchpad", "python eval", "execute code"]

def run(prompt: str) -> str:
    code = prompt.replace("run code", "").replace("eval", "").strip()
    if not code:
        return "[Scratchpad] No code provided to execute."
    try:
        tree = ast.parse(code)
        # Verify safety
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in ["open", "eval", "exec", "__import__"]:
                    return f"[Scratchpad Security] Prohibited function call: {node.func.id}"
        loc = {}
        exec(code, {"__builtins__": {"print": print, "range": range, "len": len}}, loc)
        return f"[Scratchpad Output]: Success. Context variables: {list(loc.keys())}"
    except Exception as e:
        return f"[Scratchpad Error]: {e}"

if __name__ == "__main__":
    print(run("x = 10; y = 20; z = x + y"))
