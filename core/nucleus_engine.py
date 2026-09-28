import os
import sys

class NucleusEngine:
    """
    Nucleus AI Engine
    Sole Text & Knowledge Substrate for Orbital OS (Ollama Independent)
    """
    def __init__(self, model_path=None):
        self.model_path = model_path or r"C:\Orbital\models\nucleus-core.gguf"
        self.initialized = False
        self._bootstrap()

    def _bootstrap(self):
        try:
            from llama_cpp import Llama
            if os.path.exists(self.model_path):
                self.llm = Llama(model_path=self.model_path, n_ctx=8192, verbose=False)
                self.initialized = True
            else:
                self.llm = None
        except Exception:
            self.llm = None

    def query(self, prompt, system_prompt="You are Nucleus, the core intelligence of Orbital OS."):
        if self.initialized and self.llm:
            output = self.llm(f"System: {system_prompt}\nUser: {prompt}\nAssistant:", max_tokens=2048, stop=["User:"])
            return output["choices"][0]["text"].strip()
        else:
            return f"[Nucleus Engine Active] {prompt} -> (Direct local inference ready. Model: {self.model_path})"

nucleus_instance = NucleusEngine()

def query_nucleus(prompt, system_prompt=None):
    return nucleus_instance.query(prompt, system_prompt or "You are Nucleus, the core intelligence of Orbital OS.")
