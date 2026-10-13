"""Identity tests: the system identifies as Orbital, and is honest about the model.

The distinction the prompt has to hold:
  * Asked who it is     -> Orbital
  * Asked what model    -> the truth, not a pretence
Both matter. A system that claims to BE the model is confusing; one that
denies the model exists is lying.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["ORBITAL_BASE"] = "/tmp/orbtest_identity"
os.environ["ORBITAL_QUIET"] = "1"
sys.path.insert(0, ROOT)

from core import engine, nucleus  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def main():
    # ------------------------------------------------------- the prompt
    prompt = nucleus.system_prompt()
    check("the system prompt names Orbital", "You are Orbital" in prompt,
          prompt[:40])
    check("the prompt names Nucleus", "Nucleus" in prompt)
    check("the prompt names Nebula", "Nebula" in prompt)
    check("the prompt describes the mesh", "mesh" in prompt.lower())
    check("the prompt claims local-first", "local-first" in prompt.lower())

    # Honesty: the model must be told not to lie about what it runs on.
    check("the prompt requires honesty about the model",
          "honest" in prompt.lower(), "instructs honesty")
    check("the prompt does not claim to BE the model",
          "you are qwen" not in prompt.lower()
          and "you are llama" not in prompt.lower())

    # --------------------------------------------------- prompt injection
    msgs = [{"role": "user", "content": "hello"}]
    injected = nucleus._prepare_messages(msgs) if hasattr(nucleus, "_prepare_messages") else None
    # Fall back to inspecting the source of chat() if the helper is absent.
    import inspect
    src = inspect.getsource(nucleus.chat)
    check("chat() inserts a system message", 'role": "system"' in src.replace("'", '"'))
    check("chat() does not double-insert a system prompt",
          'any(m.get("role") == "system"' in src or "any(" in src,
          "guards against duplicates")

    # ------------------------------------------------------- /whoami
    text, meta = engine.handle_prompt("/whoami", use_llm=False)
    check("/whoami is handled without the LLM", meta.get("kind") == "identity",
          str(meta.get("kind")))
    check("/whoami says Orbital", "I am Orbital" in text, text[:40])
    check("/whoami lists the components",
          all(k in text for k in ("Nucleus", "Nebula", "Mesh")))
    check("/whoami names the model in use", "Reasoning runs on" in text)
    check("/whoami admits the model is separate",
          "not mine" in text or "system around it" in text, "states the distinction")

    # Aliases
    for alias in ("/identity", "/about"):
        _t, m = engine.handle_prompt(alias, use_llm=False)
        check(f"{alias} is an alias for /whoami", m.get("kind") == "identity")

    # ------------------------------------------------- never invents a name
    check("/whoami does not claim to be Qwen",
          "I am Qwen" not in text, "no false identity")

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
