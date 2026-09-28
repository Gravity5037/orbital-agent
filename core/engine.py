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
    if mode == "visual" or user_input.startswith("/draw") or user_input.startswith("/generate"):
        prompt = user_input.replace("/draw", "").replace("/generate", "").strip()
        res = generate_visual(prompt)
        return f"[Nebula Creative Engine Renders]: {res.get('path', 'Complete')}"
    else:
        return query_nucleus(user_input)

if __name__ == "__main__":
    print(process_chat("System status query"))
