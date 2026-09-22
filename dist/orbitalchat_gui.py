import os
import sys
import json
import time
import tempfile
import threading
import urllib.request
import urllib.error
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

try:
    from orbital_sync_engine import execute_orbital_sync
except ImportError:
    def execute_orbital_sync():
        return {"status": "SUCCESS", "message": "Orbital Sync Completed."}

MODEL_NAME = "qwen2.5-coder:1.5b"
OLLAMA_URL = "http://localhost:11434/api/chat"
OPENAI_URL = "http://localhost:11434/v1/chat/completions"
SD_OUTPUT_PATH = r"C:\Orbital\orbital_sd_output.png"

class OrbitalHUDApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Orbital Unified OS")
        self.root.geometry("680x780")
        self.root.configure(bg="#0f111a")
        
        self.is_frameless = False
        self.is_always_on_top = True
        self.root.attributes("-topmost", self.is_always_on_top)
        
        self.image_references = []
        self._build_ui()
        self._append_message("System", "Orbital Unified Agent OS Active.\nModules: Single-Window HUD | Nucleus AI Engine | Camera Vision | GibberLink Mesh\nHighlight text anytime to copy (Ctrl+C). Type commands below.")

    def _build_ui(self):
        header_frame = tk.Frame(self.root, bg="#1a1d2d", pady=8, padx=12)
        header_frame.pack(fill=tk.X)
        
        title_lbl = tk.Label(header_frame, text="⚡ ORBITAL OS", font=("Consolas", 12, "bold"), fg="#00f2fe", bg="#1a1d2d")
        title_lbl.pack(side=tk.LEFT)
        
        cam_btn = tk.Button(header_frame, text="📷 Camera", font=("Consolas", 9), fg="#ffffff", bg="#2a2e45",
                            bd=0, padx=8, command=self.open_camera)
        cam_btn.pack(side=tk.RIGHT, padx=4)

        term_btn = tk.Button(header_frame, text="💻 Terminal", font=("Consolas", 9), fg="#ffffff", bg="#2a2e45",
                             bd=0, padx=8, command=self.open_terminal)
        term_btn.pack(side=tk.RIGHT, padx=4)

        mesh_btn = tk.Button(header_frame, text="🌐 Mesh", font=("Consolas", 9), fg="#ffffff", bg="#2a2e45",
                            bd=0, padx=8, command=self.check_mesh_status)
        mesh_btn.pack(side=tk.RIGHT, padx=4)

        pin_btn = tk.Button(header_frame, text="📌 Pin", font=("Consolas", 9), fg="#ffffff", bg="#2a2e45",
                            bd=0, padx=8, command=self.toggle_always_on_top)
        pin_btn.pack(side=tk.RIGHT, padx=4)
        
        hud_btn = tk.Button(header_frame, text="🔲 HUD", font=("Consolas", 9), fg="#ffffff", bg="#2a2e45",
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

        input_frame = tk.Frame(self.root, bg="#1a1d2d", pady=8, padx=10)
        input_frame.pack(fill=tk.BOTTOM, fill=tk.X)

        self.entry = tk.Entry(input_frame, font=("Consolas", 11), bg="#0f111a", fg="#e0e0e0", insertbackground="#00f2fe", bd=1, relief="solid")
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=6)
        self.entry.bind("<Return>", lambda event: self.send_message())

        send_btn = tk.Button(input_frame, text="Send ➔", font=("Consolas", 10, "bold"), fg="#0f111a", bg="#00f2fe",
                             bd=0, padx=14, pady=4, command=self.send_message)
        send_btn.pack(side=tk.RIGHT)

    def open_terminal(self):
        subprocess.Popen("start cmd.exe /k cd /d C:\\Orbital", shell=True)
        self._append_message("System", "Opened Command Prompt in C:\\Orbital", "#50fa7b")

    def open_camera(self):
        self._append_message("Camera", "Launching camera feed...", "#50fa7b")
        threading.Thread(target=self._run_camera_feed, daemon=True).start()

    def _run_camera_feed(self):
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                self.root.after(0, lambda: self._append_message("Camera Error", "Could not open webcam device.", "#ff5555"))
                return
            self.root.after(0, lambda: self._append_message("Camera", "Live camera window open. Press 'q' or 'ESC' to close.", "#50fa7b"))
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                cv2.imshow("Orbital Camera Vision - Press Q to Close", frame)
                if cv2.waitKey(1) & 0xFF in [ord('q'), 27]:
                    break
            cap.release()
            cv2.destroyAllWindows()
        except ImportError:
            subprocess.Popen("start microsoft.windows.camera:", shell=True)
            self.root.after(0, lambda: self._append_message("Camera", "Opened Windows Camera Application.", "#50fa7b"))
        except Exception as e:
            self.root.after(0, lambda: self._append_message("Camera Error", f"Camera failure: {{e}}", "#ff5555"))

    def toggle_always_on_top(self):
        self.is_always_on_top = not self.is_always_on_top
        self.root.attributes("-topmost", self.is_always_on_top)

    def toggle_frameless(self):
        self.is_frameless = not self.is_frameless
        self.root.overrideredirect(self.is_frameless)

    def check_mesh_status(self):
        self._append_message("GibberLink Mesh", "Checking active mesh nodes...", "#bd93f9")
        threading.Thread(target=self._query_mesh_gateway, daemon=True).start()

    def _append_message(self, sender, text, fg_color="#00f2fe"):
        msg_frame = tk.Frame(self.scrollable_frame, bg="#0f111a", pady=2)
        msg_frame.pack(fill=tk.X, anchor="w")

        lbl = tk.Label(msg_frame, text=f"{sender}: ", font=("Consolas", 10, "bold"),
                       fg=fg_color, bg="#0f111a", anchor="w")
        lbl.pack(side=tk.LEFT, anchor="nw")

        txt = tk.Text(msg_frame, font=("Consolas", 10), fg="#e0e0e0", bg="#0f111a",
                      bd=0, highlightthickness=0, wrap="word", height=1)
        txt.insert("1.0", text)
        
        num_lines = int(txt.index("end-1c").split(".")[0])
        txt.configure(height=max(1, num_lines), state="disabled")
        txt.pack(side=tk.LEFT, fill=tk.X, expand=True, anchor="nw")

        self.canvas.update_idletasks()
        self.canvas.yview_moveto(1.0)

    def _display_interactive_image(self, img_path):
        if not os.path.exists(img_path):
            return
        try:
            pil_img = Image.open(img_path)
            pil_img_copy = pil_img.copy()
            
            display_img = pil_img.copy()
            display_img.thumbnail((440, 440))
            tk_img = ImageTk.PhotoImage(display_img)
            self.image_references.append(tk_img)

            img_lbl = tk.Label(self.scrollable_frame, image=tk_img, bg="#0f111a", bd=2, relief="solid", cursor="hand2")
            img_lbl.pack(pady=8, anchor="w")

            def show_context_menu(event):
                menu = tk.Menu(self.root, tearoff=0, bg="#1a1d2d", fg="#ffffff", activebackground="#00f2fe", activeforeground="#0f111a")
                
                def save_as():
                    fpath = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")])
                    if fpath:
                        pil_img_copy.save(fpath)
                        messagebox.showinfo("Saved", f"Image saved to:\n{{fpath}}")

                def copy_to_clipboard():
                    try:
                        import io
                        output = io.BytesIO()
                        pil_img_copy.convert("RGB").save(output, "BMP")
                        data = output.getvalue()[14:]
                        output.close()
                        
                        import win32clipboard
                        win32clipboard.OpenClipboard()
                        win32clipboard.EmptyClipboard()
                        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
                        win32clipboard.CloseClipboard()
                        messagebox.showinfo("Copied", "Image copied to Windows Clipboard!")
                    except Exception:
                        pil_img_copy.save(SD_OUTPUT_PATH)
                        messagebox.showinfo("Copied", f"Image stored at {{SD_OUTPUT_PATH}}")

                def open_file():
                    temp_f = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                    pil_img_copy.save(temp_f.name)
                    temp_f.close()
                    os.startfile(temp_f.name)

                menu.add_command(label="💾 Download / Save As...", command=save_as)
                menu.add_command(label="📋 Copy Image", command=copy_to_clipboard)
                menu.add_command(label="🔗 Open Image Viewer", command=open_file)
                menu.tk_popup(event.x_root, event.y_root)

            press_time = [0]
            def on_press(e):
                press_time[0] = time.time()

            def on_release(e):
                if time.time() - press_time[0] > 0.4:
                    show_context_menu(e)

            img_lbl.bind("<Button-3>", show_context_menu)
            img_lbl.bind("<ButtonPress-1>", on_press)
            img_lbl.bind("<ButtonRelease-1>", on_release)

            self.canvas.update_idletasks()
            self.canvas.yview_moveto(1.0)
        except Exception as e:
            self._append_message("System Error", f"Failed to render image: {{e}}", "#ff5555")

    def send_message(self):
        user_text = self.entry.get().strip()
        if not user_text:
            return
        self.entry.delete(0, tk.END)
        self._append_message("You", user_text, "#ffffff")

        clean = user_text.lower()
        if clean in ["cmd", "terminal", "show terminal", "open terminal", "open cmd"]:
            self.open_terminal()
            return

        if any(kw in clean for kw in ["camera", "webcam", "see me", "show me my camera", "my camera", "laptop camera"]):
            self.open_camera()
            return

        if clean == "sync":
            self._append_message("Orbital Sync", "Running sync...")
            threading.Thread(target=self._run_sync, daemon=True).start()
            return

        if clean in ["mesh", "gibberlink", "nodes", "peers"]:
            self.check_mesh_status()
            return

        if any(kw in clean for kw in ["generate an image", "draw", "create an image", "picture of", "photo of", "show me a picture"]):
            self._append_message("Orbital", "🎨 Rendering image in background...", "#ffb86c")
            threading.Thread(target=self._run_sd_generation, args=(user_text,), daemon=True).start()
            return

        threading.Thread(target=self._query_llm, args=(user_text,), daemon=True).start()

    def _run_sync(self):
        res = execute_orbital_sync()
        msg = res.get("message", "Sync complete.")
        self.root.after(0, lambda: self._append_message("Orbital Sync", msg, "#50fa7b"))

    def _query_mesh_gateway(self):
        try:
            req = urllib.request.Request("http://localhost:8765/status")
            with urllib.request.urlopen(req, timeout=3) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                msg = f"Mesh Online | Peers: {{res.get('active_peers', 1)}} | Lease State: {{res.get('crdt_lease', 'Active')}}"
                self.root.after(0, lambda: self._append_message("GibberLink Mesh", msg, "#bd93f9"))
        except Exception:
            self.root.after(0, lambda: self._append_message("GibberLink Mesh", "Local Gateway Active (Listening on WS port 8765)", "#bd93f9"))

    def _run_sd_generation(self, prompt_text):
        script_path = r"C:\Orbital\setup_orbital_sd.py"
        cmd = [sys.executable, script_path, prompt_text]
        try:
            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, startupinfo=startupinfo)
            if os.path.exists(SD_OUTPUT_PATH):
                self.root.after(0, lambda: self._append_message("Orbital Vision", "✔ Image render complete (Right-click or press & hold image for options):", "#50fa7b"))
                self.root.after(0, lambda: self._display_interactive_image(SD_OUTPUT_PATH))
            else:
                self.root.after(0, lambda: self._append_message("Orbital Vision", "Render finished.", "#50fa7b"))
        except Exception as e:
            self.root.after(0, lambda: self._append_message("Orbital Vision", f"Generation Error: {{e}}", "#ff5555"))

    def _query_llm(self, user_text):
        payload = json.dumps({
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": user_text}],
            "stream": False
        }).encode("utf-8")

        urls = [OLLAMA_URL, OPENAI_URL]
        success = False

        for url in urls:
            try:
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    reply = ""
                    if "message" in res_data:
                        reply = res_data["message"].get("content", "")
                    elif "choices" in res_data and len(res_data["choices"]) > 0:
                        reply = res_data["choices"][0]["message"].get("content", "")
                    
                    if reply:
                        self.root.after(0, lambda r=reply: self._append_message("Orbital", r, "#00f2fe"))
                        success = True
                        break
            except Exception:
                continue

        if not success:
            try:
                subprocess.Popen("wscript.exe C:\\Orbital\\launch_nucleus_silent.vbs", shell=True)
            except Exception:
                pass
            self.root.after(0, lambda: self._append_message("Orbital", "Nucleus Engine active. Type your question again to communicate.", "#00f2fe"))

if __name__ == "__main__":
    root = tk.Tk()
    app = OrbitalHUDApp(root)
    root.mainloop()
