"""
ORBITAL OS - Dynamic Skill Registry & Auto-Loader Substrate
Manages all modular, self-learned, and user-extended skills in C:\\Orbital\\skills.
Enables hot-reloading, intent matching, and isolated execution.
"""

import os
import sys
import importlib.util
import time

BASE_DIR = r"C:\Orbital"
SKILLS_DIR = os.path.join(BASE_DIR, "skills")

class SkillRegistry:
    def __init__(self):
        os.makedirs(SKILLS_DIR, exist_ok=True)
        self.skills = {}
        self.last_scanned = 0
        self.reload_skills()

    def reload_skills(self):
        """Scans C:\\Orbital\\skills and imports all valid python skill modules."""
        self.skills.clear()
        if not os.path.exists(SKILLS_DIR):
            return

        for fname in os.listdir(SKILLS_DIR):
            if fname.endswith(".py") and not fname.startswith("__"):
                fpath = os.path.join(SKILLS_DIR, fname)
                mod_name = fname[:-3]
                try:
                    spec = importlib.util.spec_from_file_location(mod_name, fpath)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)

                    if hasattr(mod, "run"):
                        self.skills[mod_name] = {
                            "name": getattr(mod, "NAME", mod_name.replace("_", " ").title()),
                            "description": getattr(mod, "DESCRIPTION", "Custom Orbital Skill"),
                            "keywords": getattr(mod, "KEYWORDS", [mod_name.replace("_", " ")]),
                            "module": mod,
                            "path": fpath
                        }
                except Exception as e:
                    print(f"[!] Warning: Failed to load skill {fname}: {e}")

        self.last_scanned = time.time()

    def list_skills(self):
        """Returns catalog of all registered skills."""
        return [
            {
                "id": k,
                "name": v["name"],
                "description": v["description"],
                "keywords": v["keywords"]
            }
            for k, v in self.skills.items()
        ]

    def match_skill(self, prompt):
        """Matches a user prompt to the best registered skill."""
        p_lower = prompt.lower()
        for skill_id, info in self.skills.items():
            for kw in info["keywords"]:
                if kw.lower() in p_lower:
                    return skill_id
        return None

    def execute_skill(self, skill_id, prompt):
        """Safely executes a skill within a protective try/except sandbox."""
        if skill_id not in self.skills:
            return f"[Skill Registry] Skill '{skill_id}' not found."

        skill = self.skills[skill_id]
        try:
            res = skill["module"].run(prompt)
            return str(res)
        except Exception as e:
            return f"[Skill Error ({skill['name']})]: Exception during execution: {e}"

skill_registry = SkillRegistry()

if __name__ == "__main__":
    print(f"Loaded {len(skill_registry.skills)} skills from C:\\Orbital\\skills.")
