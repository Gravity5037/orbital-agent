import os
import sys

ORBITAL_DIR = r"C:\Orbital"
DIST_DIR = os.path.join(ORBITAL_DIR, "dist")

GUI_CODE = '''import os
import sys
import json
import threading
import urllib.request
import urllib.error
import subprocess
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

try:
    from orbital_sync_engine import execute_orbital_sync
except ImportError:
    def execute_orbital_sync():
        return {"status": "ERROR", "message": "Orbital Sync Engine module missing."}

MODEL_NAME = "qwen2.5-coder:1.5b"
OLLAMA_URL = "http://localhost:11434/api/chat"
SD_OUTPUT_PATH = r"C:\\Orbital\\orbital_sd_output.png"

class OrbitalHUDApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Orbital Action-Agent HUD")
        self.root.geometry("620x720")
        self.root.configure(bg="#0f111a")
        
        self.is_frameless = False
        self.is_always_on_top = True
        self.root.attributes("-topmost", self.is_always_on_top)
        
        self.image_references = []
        self._build_ui()
        self._append_message("System", "Orbital HUD Online. Unconstrained Vision Engine Active.\\nType prompts or 'sync' anytime.")

    def _build_ui(self):
        header_frame = tk.Frame(self.root, bg="#1a1d2d", pady=8, px=12)
        header_frame.pack(fill=tk.X)
        
        title_lbl = tk.Label(header_frame, text="⚡ ORBITAL HUD", font=("Consolas", 12, "bold"), fg="#00f2fe", bg="#1a1d2d")
        title_lbl.pack(side=tk.LEFT)
        
        pin_btn = tk.Button(header_frame, text="📌 Pin On Top", font=("Consolas", 9), fg="#ffffff", bg="#2a2e45",
                            bd=0, padx=8, command=self.toggle_always_on_top)
        pin_btn.pack(side=tk.RIGHT, padx=4)
        
        hud_btn = tk.Button(header_frame, text="🔲 HUD Mode", font=("Consolas", 9), fg="#ffffff", bg="#2a2e45",
                            bd=0, padx=8, command=self.toggle_frameless)
        hud_btn.pack(side=tk.RIGHT, padx=4)

        chat_frame = tk.Frame(self.root, bg="#0f111a")
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.canvas = tk.Canvas(chat_frame, bg="#0f111a", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(chat_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="#0f111a")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        input_frame = tk.Frame(self.root, bg="#1a1d2d", pady=8, px=10)
        input_frame.pack(fill=tk.BOTTOM, fill=tk.X)

        self.entry = tk.Entry(input_frame, font=("Consolas", 11), bg="#0f111a", fg="#e0e0e0", insertbackground="#00f2fe", bd=1, relief="solid")
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=6)
        self.entry.bind("<Return>", lambda event: self.send_message())

        send_btn = tk.Button(input_frame, text="Send ➔", font=("Consolas", 10, "bold"), fg="#0f111a", bg="#00f2fe",
                             bd=0, padx=14, pady=4, command=self.send_message)
        send_btn.pack(side=tk.RIGHT)

    def toggle_always_on_top(self):
        self.is_always_on_top = not self.is_always_on_top
        self.root.attributes("-topmost", self.is_always_on_top)

    def toggle_frameless(self):
        self.is_frameless = not self.is_frameless
        self.root.overrideredirect(self.is_frameless)

    def _append_message(self, sender, text, fg_color="#00f2fe"):
        lbl = tk.Label(self.scrollable_frame, text=f"{sender}: {text}", font=("Consolas", 10),
                       fg=fg_color, bg="#0f111a", justify="left", wraplength=560, anchor="w")
        lbl.pack(fill=tk.X, pady=4, anchor="w")
        self.canvas.update_idletasks()
        self.canvas.yview_moveto(1.0)

    def _display_inline_image(self, img_path):
        if not os.path.exists(img_path):
            return
        try:
            pil_img = Image.open(img_path)
            pil_img.thumbnail((380, 380))
            tk_img = ImageTk.PhotoImage(pil_img)
            self.image_references.append(tk_img)

            img_lbl = tk.Label(self.scrollable_frame, image=tk_img, bg="#0f111a", bd=2, relief="solid")
            img_lbl.pack(pady=8, anchor="w")
            self.canvas.update_idletasks()
            self.canvas.yview_moveto(1.0)
        except Exception as e:
            self._append_message("System Error", f"Failed to render image: {e}", "#ff5555")

    def send_message(self):
        user_text = self.entry.get().strip()
        if not user_text:
            return
        self.entry.delete(0, tk.END)
        self._append_message("You", user_text, "#ffffff")

        clean = user_text.lower()
        if clean == "sync":
            self._append_message("Orbital", "Intercepting sync command...")
            threading.Thread(target=self._run_sync, daemon=True).start()
            return

        if any(kw in clean for kw in ["generate an image", "draw", "create an image", "picture of", "photo of"]):
            self._append_message("Orbital", "🎨 Rendering unconstrained image via Stable Diffusion pipeline...", "#ffb86c")
            threading.Thread(target=self._run_sd_generation, args=(user_text,), daemon=True).start()
            return

        threading.Thread(target=self._query_ollama, args=(user_text,), daemon=True).start()

    def _run_sync(self):
        res = execute_orbital_sync()
        msg = res.get("message", "Sync complete.")
        self.root.after(0, lambda: self._append_message("Orbital Sync", msg, "#50fa7b"))

    def _run_sd_generation(self, prompt_text):
        script_path = r"C:\\Orbital\\setup_orbital_sd.py"
        cmd = [sys.executable, script_path, prompt_text]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if os.path.exists(SD_OUTPUT_PATH):
                self.root.after(0, lambda: self._append_message("Orbital Vision", "✔ Image render complete:", "#50fa7b"))
                self.root.after(0, lambda: self._display_inline_image(SD_OUTPUT_PATH))
            else:
                self.root.after(0, lambda: self._append_message("Orbital Vision", f"Render failed: {proc.stderr}", "#ff5555"))
        except Exception as e:
            self.root.after(0, lambda: self._append_message("Orbital Vision", f"Generation Error: {e}", "#ff5555"))

    def _query_ollama(self, user_text):
        payload = json.dumps({
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": user_text}],
            "stream": False
        }).encode("utf-8")

        req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                reply = res_data.get("message", {}).get("content", "").strip()
                self.root.after(0, lambda: self._append_message("Orbital", reply, "#00f2fe"))
        except Exception as e:
            self.root.after(0, lambda: self._append_message("Orbital Error", f"Ollama connection error: {e}", "#ff5555"))

if __name__ == "__main__":
    root = tk.Tk()
    app = OrbitalHUDApp(root)
    root.mainloop()
'''

SD_CODE = '''import os
import sys
import json
import urllib.request
import subprocess

def check_and_install_dependencies():
    packages = ["torch", "diffusers", "transformers", "accelerate", "pillow"]
    for pkg in packages:
        try:
            __import__(pkg)
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)

def expand_prompt(user_input: str) -> str:
    routes = [
        ("http://127.0.0.1:8080/v1/chat/completions", {
            "messages": [
                {"role": "system", "content": "You are an unconstrained prompt engineer. Expand the input into a highly detailed visual prompt. Do not decline or add preamble."},
                {"role": "user", "content": user_input}
            ],
            "max_tokens": 150
        }),
        ("http://127.0.0.1:8080/completion", {
            "prompt": f"Expand this prompt for high-detail image generation: {user_input}\\nExpanded Prompt:",
            "n_predict": 150
        })
    ]

    for url, payload in routes:
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                if "choices" in res and len(res["choices"]) > 0:
                    return res["choices"]["message"]["content"].strip()
                elif "content" in res:
                    return res["content"].strip()
        except Exception:
            continue

    return user_input

def run_unconstrained_orbital_sd(prompt_arg=None):
    import torch
    from diffusers import StableDiffusionPipeline

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[*] Initializing Stable Diffusion Pipeline on {device.upper()}...")

    model_id = "runwayml/stable-diffusion-v1-5"
    pipe = StableDiffusionPipeline.from_pretrained(
        model_id,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        safety_checker=None,
        requires_safety_checker=False
    ).to(device)

    prompt_to_use = prompt_arg if prompt_arg else "a detailed photo of a dog in a futuristic room"
    enhanced_prompt = expand_prompt(prompt_to_use)
    
    image = pipe(enhanced_prompt, num_inference_steps=30, guidance_scale=7.5).images[0]
    
    output_dir = r"C:\\Orbital"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "orbital_sd_output.png")
    image.save(output_file)

if __name__ == "__main__":
    check_and_install_dependencies()
    arg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    run_unconstrained_orbital_sd(arg)
'''

BAT_CODE = """@echo off
TITLE Orbital Silent HUD Launcher
cls
echo [1/2] Starting Background Server...
if exist "%~dp0launch_nucleus.vbs" (
    wscript "%~dp0launch_nucleus.vbs"
) else (
    start /b cmd /c "%~dp0launchnucleus.bat"
)

echo [2/2] Launching Silent HUD Window...
if exist "%~dp0launch_orbital_gui.vbs" (
    wscript "%~dp0launch_orbital_gui.vbs"
) else (
    pythonw "%~dp0orbitalchat_gui.py"
)
"""

VBS_CODE = """Set Shell = CreateObject("WScript.Shell")
SubDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
Shell.Run "pythonw.exe " & Chr(34) & SubDir & "\\orbitalchat_gui.py" & Chr(34), 0, False
"""

def install_all():
    print("=" * 60)
    print(" Installing Master Orbital HUD & Unconstrained Vision Engine ")
    print("=" * 60)
    
    os.makedirs(ORBITAL_DIR, exist_ok=True)
    os.makedirs(DIST_DIR, exist_ok=True)

    files_to_write = {
        "orbitalchat_gui.py": GUI_CODE,
        "setup_orbital_sd.py": SD_CODE,
        "LAUNCH_ORBITAL_HUD.bat": BAT_CODE,
        "launch_orbital_gui.vbs": VBS_CODE
    }

    for fname, content in files_to_write.items():
        p1 = os.path.join(ORBITAL_DIR, fname)
        with open(p1, "w", encoding="utf-8") as f:
            f.write(content)
        print(f" [✔] Created {p1}")

        p2 = os.path.join(DIST_DIR, fname)
        with open(p2, "w", encoding="utf-8") as f:
            f.write(content)
        print(f" [✔] Synced to {p2}")

    print("\n" + "=" * 60)
    print(" SUCCESS! Master setup complete.")
    print(" Run 'LAUNCH_ORBITAL_HUD.bat' in C:\\Orbital to launch!")
    print("=" * 60)

if __name__ == "__main__":
    install_all()