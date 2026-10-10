"""
ORBITAL OS AUTO-LEARNED SKILL: JSON Schema Validator
"""
import json

NAME = "JSON Schema Validator"
DESCRIPTION = "Parses and validates JSON strings, returns structural keys."
KEYWORDS = ["json validate", "check json", "format json", "parse json"]

def run(prompt: str) -> str:
    raw = prompt.replace("json validate", "").replace("format json", "").strip()
    try:
        data = json.loads(raw)
        formatted = json.dumps(data, indent=2)
        if isinstance(data, dict):
            detail = f"Keys: {list(data.keys())}"
        elif isinstance(data, list):
            detail = f"Array of {len(data)} items"
        else:
            detail = f"Primitive value: {data}"
        return f"[JSON Valid]: Verified structure ({detail})"
    except Exception as e:
        return f"[JSON Error]: Invalid JSON syntax: {e}"

if __name__ == "__main__":
    print(run('{"status": "online", "version": 1.0}'))
