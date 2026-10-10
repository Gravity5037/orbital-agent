import os
import sys
sys.path.append(r"C:\Orbital\core")

try:
    from nucleus_engine import query_nucleus
except ImportError:
    def query_nucleus(prompt, system_prompt=None):
        return f"[Nucleus Direct] Processed: {prompt}"

def generate_visual_lazy(prompt, output_path=None, is_video=False):
    try:
        from nebula_engine import generate_visual
        return generate_visual(prompt, output_path=output_path, is_video=is_video)
    except Exception as e:
        return f"[Nebula Engine Warning: PyTorch/Diffusers offline] {e}"

def process_chat(user_input, mode="text", image_path=None):
    stripped = user_input.strip()

    # 1. Engage Ralph Self-Evolution Loop (Reflect, Ask, Patch, Heal)
    try:
        from ralph_loop import ralph_engine
        ralph_response = ralph_engine.handle_ralph_turn(stripped, image_path=image_path)
        if ralph_response:
            return ralph_response
    except Exception:
        pass

    # 2. Check Dynamic Skills Registry (C:\Orbital\skills)
    try:
        from skill_registry import skill_registry
        matched_skill = skill_registry.match_skill(stripped)
        if matched_skill:
            return skill_registry.execute_skill(matched_skill, stripped)
    except Exception:
        pass

    if mode == "visual" or stripped.startswith("/draw") or stripped.startswith("/generate"):
        prompt = stripped.replace("/draw", "").replace("/generate", "").strip()
        res = generate_visual_lazy(prompt)
        res_path = res.get('path', res) if isinstance(res, dict) else str(res)
        return f"[Nebula Creative Engine]: {res_path}"
    elif stripped.lower().startswith("draw "):
        prompt = stripped[5:].strip()
        res = generate_visual_lazy(prompt)
        res_path = res.get('path', res) if isinstance(res, dict) else str(res)
        return f"[Nebula Creative Engine]: {res_path}"
    else:
        return query_nucleus(user_input)

class Engine:
    def __init__(self):
        pass

    def route_query(self, prompt, mode="text", image_path=None):
        return process_chat(prompt, mode=mode, image_path=image_path)

if __name__ == "__main__":
    print(process_chat("Hello Orbital AI, who are you?"))
