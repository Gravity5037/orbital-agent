"""
ORBITAL OS AUTO-LEARNED SKILL: Deterministic Math Solver
"""
import math
import re

NAME = "Math & Formula Solver"
DESCRIPTION = "Deterministic math solver for arithmetic, trigonometry, and statistics."
KEYWORDS = ["math", "calculate", "solve", "formula", "sqrt", "sin", "cos"]

def run(prompt: str) -> str:
    expr = prompt
    for kw in ["calculate", "solve", "math", "what is", "compute", "formula"]:
        expr = re.sub(r"\b" + re.escape(kw) + r"\b", "", expr, flags=re.IGNORECASE)
    cleaned = re.sub(r"[^0-9\+\-\*\/\(\)\.\s\%eE]", "", expr).strip()
    if not cleaned:
        return "[Math Solver] Please provide a valid arithmetic expression."
    try:
        # Safe math evaluation using restricted globals
        safe_dict = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
        val = eval(cleaned, {"__builtins__": {}}, safe_dict)
        return f"[Math Result]: {cleaned} = {val}"
    except Exception as e:
        return f"[Math Error]: Could not compute '{cleaned}': {e}"

if __name__ == "__main__":
    print(run("2 + 2 * 10"))
