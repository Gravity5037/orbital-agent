import os
import sys
import subprocess

class NucleusEngine:
    """
    Nucleus AI Engine
    Local Intelligence Substrate for Orbital OS (Bundled llama.cpp + GGUF)
    """
    def __init__(self, model_path=None):
        base_dir = r"C:\Orbital"
        self.model_path = model_path or os.path.join(base_dir, "Nucleus", "model.gguf")
        if not os.path.exists(self.model_path):
            self.model_path = os.path.join(base_dir, "models", "nucleus-core.gguf")
        self.cli_exe = os.path.join(base_dir, "Nucleus", "llama-cli.exe")
        self.initialized = os.path.exists(self.model_path) and os.path.exists(self.cli_exe)

    def query(self, prompt, system_prompt="You are Nucleus, the core intelligence of Orbital OS."):
        if not self.initialized:
            return f"[Nucleus AI Fallback] Received: '{prompt}'. (Model file missing at {self.model_path})"

        formatted_prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
        cmd = [
            self.cli_exe,
            "-m", self.model_path,
            "-p", formatted_prompt,
            "-n", "256",
            "--no-display-prompt",
            "-no-cnv",
            "--simple-io"
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
            output = res.stdout.strip()
            for stop in ["<|im_end|>", "[end of text]", "<|endoftext|>"]:
                if stop in output:
                    output = output.split(stop)[0].strip()
            return output if output else "[Nucleus AI] Completed."
        except Exception as e:
            return f"[Nucleus Inference Exception] {e}"

nucleus_instance = NucleusEngine()

def query_nucleus(prompt, system_prompt=None):
    return nucleus_instance.query(prompt, system_prompt or "You are Nucleus, the core intelligence of Orbital OS.")

if __name__ == "__main__":
    test_q = sys.argv[1] if len(sys.argv) > 1 else "Status check"
    print(query_nucleus(test_q))
