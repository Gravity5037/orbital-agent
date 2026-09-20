import os
import json
import http.server

try:
    from llama_cpp import Llama
    LLAMA_AVAILABLE = True
except ImportError:
    LLAMA_AVAILABLE = False

MODEL_PATH = os.path.join("Nucleus", "model.gguf")

class NucleusEngine:
    def __init__(self):
        self.llm = None
        if LLAMA_AVAILABLE and os.path.exists(MODEL_PATH):
            print(f"[Nucleus] Loading model weights from {MODEL_PATH} onto GPU/CPU...")
            try:
                self.llm = Llama(model_path=MODEL_PATH, n_gpu_layers=-1, n_ctx=4096, verbose=False)
                print("[Nucleus] GGUF Model successfully loaded into GPU memory!")
            except Exception as e:
                print(f"[Nucleus Warning] GPU offload fallback: {e}")
                try:
                    self.llm = Llama(model_path=MODEL_PATH, n_ctx=2048, verbose=False)
                    print("[Nucleus] GGUF Model loaded in CPU mode.")
                except Exception as ex:
                    print(f"[Nucleus Error] Could not initialize model: {ex}")

    def generate(self, prompt_text):
        if self.llm:
            try:
                res = self.llm(prompt_text, max_tokens=512, stop=["User:", "

User:"])
                return res["choices"][0]["text"].strip()
            except Exception as e:
                return f"Nucleus Generation Error: {e}"
        return "Nucleus Microkernel online and ready."

engine_instance = NucleusEngine()

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "Nucleus Engine Active", "gpu_active": LLAMA_AVAILABLE}).encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body_str = ""
        if length > 0:
            body_str = self.rfile.read(length).decode("utf-8", errors="ignore")
        
        prompt = "Hello"
        if body_str:
            try:
                data = json.loads(body_str)
                messages = data.get("messages", [])
                if messages:
                    prompt = messages[-1].get("content", prompt)
                elif "prompt" in data:
                    prompt = data["prompt"]
            except Exception:
                pass

        reply_text = engine_instance.generate(prompt)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = {
            "model": "Nucleus",
            "message": {"role": "assistant", "content": reply_text},
            "done": True
        }
        self.wfile.write(json.dumps(response).encode())

    def log_message(self, format, *args):
        return

if __name__ == "__main__":
    print("Nucleus Engine Active on http://127.0.0.1:11434")
    server = http.server.HTTPServer(("127.0.0.1", 11434), Handler)
    server.serve_forever()
