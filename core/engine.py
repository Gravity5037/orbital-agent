import os
import sys
sys.path.append(r"C:\Orbital\core")

try:
    from nucleus_engine import query_nucleus
except ImportError:
    def query_nucleus(prompt, system_prompt=None):
        return f"[Nucleus Direct] Processed: {prompt}"

try:
    from nebula_engine import generate_visual
except ImportError:
    def generate_visual(prompt, output_path=None, is_video=False):
        return {"status": "simulated", "prompt": prompt}

def process_chat(user_input, mode="text"):
    stripped = user_input.strip()
    if mode == "visual" or stripped.startswith("/draw") or stripped.startswith("/generate"):
        prompt = stripped.replace("/draw", "").replace("/generate", "").strip()
        res = generate_visual(prompt)
        res_path = res.get('path', res) if isinstance(res, dict) else str(res)
        return f"[Nebula Creative Engine Renders]: {res_path}"
    elif stripped.lower().startswith("draw "):
        prompt = stripped[5:].strip()
        res = generate_visual(prompt)
        res_path = res.get('path', res) if isinstance(res, dict) else str(res)
        return f"[Nebula Creative Engine Renders]: {res_path}"
    else:
        return query_nucleus(user_input)

class Engine:
    def __init__(self):
        pass

    def route_query(self, prompt, mode="text"):
        return process_chat(prompt, mode=mode)

if __name__ == "__main__":
    print(process_chat("System status query"))
