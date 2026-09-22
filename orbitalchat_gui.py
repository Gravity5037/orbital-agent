import os
import sys
import json
import threading
import urllib.request
import urllib.error
import subprocess
import time
import tkinter as tk
from tkinter import ttk, messagebox

MODEL_NAME = "qwen2.5-coder:1.5b"
OLLAMA_URL = "http://localhost:11434/api/chat"

def ensure_nucleus_running():
    try:
        req = urllib.request.Request("http://localhost:11434/", headers={"User-Agent": "Orbital"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return True
    except Exception:
        pass

    app_dir = os.path.dirname(os.path.abspath(__file__))
    engine_paths = [
        os.path.join(app_dir, "engine.py"),
        r"C:\Orbital\engine.py",
        r"C:\Orbital_FlashDrive\engine.py"
    ]
    for ep in engine_paths:
        if os.path.exists(ep):
            try:
                startupinfo = None
                if os.name == "nt":
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = 0
                subprocess.Popen([sys.executable, ep], startupinfo=startupinfo)
                time.sleep(1.0)
                return True
            except Exception:
                pass
    return False

class OrbitalNavigatorWorkstation:
    def __init__(self, root):
        self.root = root
        self.root.title("Orbital Workstation Navigator")
        self.root.geometry("980x720")
        self.root.configure(bg="#0b0d17")
        self._build_ui()
        threading.Thread(target=ensure_nucleus_running, daemon=True).start()

    def _build_ui(self):
        self.sidebar = tk.Frame(self.root, bg="#131625", width=210)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        brand_lbl = tk.Label(self.sidebar, text="⚡ ORBITAL OS", font=("Consolas", 14, "bold"), fg="#00f2fe", bg="#131625", pady=15)
        brand_lbl.pack(fill=tk.X)

        self.nav_buttons = {}
        tabs = [
            ("💬 AI Chat HUD", "chat"),
            ("📡 Presence Sensing", "presence"),
            ("📷 Web Cameras", "camera"),
            ("🎨 Image Generator", "image_gen"),
            ("🎵 Media Control", "media"),
            ("📬 Inbox DMs", "inbox")
        ]

        for text, key in tabs:
            btn = tk.Button(self.sidebar, text=text, font=("Consolas", 10, "bold"), fg="#a0aab8", bg="#131625",
                            activebackground="#00f2fe", activeforeground="#0b0d17", bd=0, anchor="w", padx=16, pady=10,
                            command=lambda k=key: self.switch_tab(k))
            btn.pack(fill=tk.X)
            self.nav_buttons[key] = btn

        self.main_content = tk.Frame(self.root, bg="#0b0d17")
        self.main_content.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.frames = {}
        for _, key in tabs:
            f = tk.Frame(self.main_content, bg="#0b0d17")
            self.frames[key] = f

        self._build_chat_tab()
        self._build_presence_tab()
        self._build_camera_tab()
        self._build_image_gen_tab()
        self._build_media_tab()
        self._build_inbox_tab()

        self.switch_tab("chat")

    def switch_tab(self, key):
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.config(bg="#00f2fe", fg="#0b0d17")
            else:
                btn.config(bg="#131625", fg="#a0aab8")
        for f in self.frames.values():
            f.pack_forget()
        self.frames[key].pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

    def _build_chat_tab(self):
        f = self.frames["chat"]
        lbl = tk.Label(f, text="💬 Orbital AI Chat HUD", font=("Consolas", 12, "bold"), fg="#00f2fe", bg="#0b0d17")
        lbl.pack(anchor="w", pady=(0, 10))

        chat_frame = tk.Frame(f, bg="#0b0d17")
        chat_frame.pack(fill=tk.BOTH, expand=True)

        self.chat_text = tk.Text(chat_frame, bg="#131625", fg="#e0e0e0", font=("Consolas", 10), wrap="word", bd=0,
                                 selectbackground="#2a2e45", selectforeground="#00f2fe")
        sb = ttk.Scrollbar(chat_frame, orient="vertical", command=self.chat_text.yview)
        self.chat_text.configure(yscrollcommand=sb.set)
        self.chat_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.chat_text.tag_config("sys_tag", foreground="#50fa7b", font=("Consolas", 10, "bold"))
        self.chat_text.tag_config("user_tag", foreground="#ffffff", font=("Consolas", 10, "bold"))
        self.chat_text.tag_config("orb_tag", foreground="#00f2fe", font=("Consolas", 10, "bold"))

        input_frame = tk.Frame(f, bg="#131625", pady=8, padx=10)
        input_frame.pack(fill=tk.X, pady=(10, 0))

        self.entry = tk.Entry(input_frame, font=("Consolas", 11), bg="#0b0d17", fg="#e0e0e0", insertbackground="#00f2fe", bd=1)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=6)
        self.entry.bind("<Return>", lambda e: self.send_chat())

        send_btn = tk.Button(input_frame, text="Send ➔", font=("Consolas", 10, "bold"), fg="#0b0d17", bg="#00f2fe", bd=0, padx=14, command=self.send_chat)
        send_btn.pack(side=tk.RIGHT)

        self._append_chat("System", "Orbital Navigator Chat HUD Active. Ready.")

    def _append_chat(self, sender, text):
        self.chat_text.config(state="normal")
        tag = "sys_tag" if sender.lower() == "system" else ("user_tag" if sender.lower() == "you" else "orb_tag")
        self.chat_text.insert(tk.END, f"{sender}: ", tag)
        self.chat_text.insert(tk.END, f"{text}\n\n")
        self.chat_text.config(state="disabled")
        self.chat_text.see(tk.END)

    def send_chat(self):
        val = self.entry.get().strip()
        if not val:
            return
        self.entry.delete(0, tk.END)
        self._append_chat("You", val)
        threading.Thread(target=self._query_ai, args=(val,), daemon=True).start()

    def _query_ai(self, prompt):
        ensure_nucleus_running()
        payload = json.dumps({"model": MODEL_NAME, "messages": [{"role": "user", "content": prompt}], "stream": False}).encode("utf-8")
        req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                reply = data.get("message", {}).get("content", "Received prompt.")
                self.root.after(0, lambda: self._append_chat("Orbital", reply))
        except Exception as e:
            self.root.after(0, lambda: self._append_chat("Orbital Error", f"Nucleus Connection: {e}"))

    def _build_presence_tab(self):
        f = self.frames["presence"]
        lbl = tk.Label(f, text="📡 Wi-Fi CSI Spatial Presence Sensing", font=("Consolas", 12, "bold"), fg="#50fa7b", bg="#0b0d17")
        lbl.pack(anchor="w", pady=(0, 10))
        desc = tk.Label(f, text="Monitors sub-GHz Wi-Fi disruption frequency fields for non-optical room presence tracking.", font=("Consolas", 9), fg="#a0aab8", bg="#0b0d17")
        desc.pack(anchor="w", pady=(0, 15))
        scan_btn = tk.Button(f, text="⚡ Run 3D CSI Room Radar Scan", font=("Consolas", 10, "bold"), fg="#0b0d17", bg="#50fa7b", bd=0, padx=16, pady=8, command=self._run_csi_scan)
        scan_btn.pack(anchor="w")

    def _run_csi_scan(self):
        messagebox.showinfo("CSI Sensing", "Initiating Wi-Fi disruption channel frequency sweep...\nGenerating live 3D Room Spatial Map.")

    def _build_camera_tab(self):
        f = self.frames["camera"]
        lbl = tk.Label(f, text="📷 Web Cameras & Optical Feed", font=("Consolas", 12, "bold"), fg="#00f2fe", bg="#0b0d17")
        lbl.pack(anchor="w", pady=(0, 10))
        cam_btn = tk.Button(f, text="📹 View Connected Optical Feeds", font=("Consolas", 10, "bold"), fg="#0b0d17", bg="#00f2fe", bd=0, padx=16, pady=8, command=self._open_cam)
        cam_btn.pack(anchor="w")

    def _open_cam(self):
        messagebox.showinfo("Web Cameras", "Opening connected web camera stream feed...")

    def _build_image_gen_tab(self):
        f = self.frames["image_gen"]
        lbl = tk.Label(f, text="🎨 Unconstrained Image Generator", font=("Consolas", 12, "bold"), fg="#ffb86c", bg="#0b0d17")
        lbl.pack(anchor="w", pady=(0, 10))
        self.img_prompt = tk.Entry(f, font=("Consolas", 11), bg="#131625", fg="#e0e0e0", insertbackground="#ffb86c")
        self.img_prompt.insert(0, "A cybernetic orbital station above earth in dark aesthetic")
        self.img_prompt.pack(fill=tk.X, pady=(0, 10), ipady=6)
        gen_btn = tk.Button(f, text="🎨 Render Image", font=("Consolas", 10, "bold"), fg="#0b0d17", bg="#ffb86c", bd=0, padx=16, pady=8, command=self._gen_img)
        gen_btn.pack(anchor="w")

    def _gen_img(self):
        messagebox.showinfo("Image Generator", f"Rendering image for prompt:\n'{self.img_prompt.get()}'")

    def _build_media_tab(self):
        f = self.frames["media"]
        lbl = tk.Label(f, text="🎵 Connected Media & Spotify Controller", font=("Consolas", 12, "bold"), fg="#bd93f9", bg="#0b0d17")
        lbl.pack(anchor="w", pady=(0, 10))
        m_frame = tk.Frame(f, bg="#131625", padx=20, pady=20)
        m_frame.pack(fill=tk.X, pady=(0, 15))
        now_playing = tk.Label(m_frame, text="▶ Now Playing: Orbital Atmospheric Ambient (Wi-Fi Node #1)", font=("Consolas", 10, "bold"), fg="#bd93f9", bg="#131625")
        now_playing.pack(anchor="w", pady=(0, 15))
        ctrl_frame = tk.Frame(m_frame, bg="#131625")
        ctrl_frame.pack(anchor="w")
        tk.Button(ctrl_frame, text="⏮ Prev", font=("Consolas", 9, "bold"), fg="#ffffff", bg="#2a2e45", bd=0, padx=12, pady=6).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(ctrl_frame, text="⏯ Play/Pause", font=("Consolas", 9, "bold"), fg="#0b0d17", bg="#bd93f9", bd=0, padx=12, pady=6).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(ctrl_frame, text="⏭ Next", font=("Consolas", 9, "bold"), fg="#ffffff", bg="#2a2e45", bd=0, padx=12, pady=6).pack(side=tk.LEFT)

    def _build_inbox_tab(self):
        f = self.frames["inbox"]
        lbl = tk.Label(f, text="📬 Inbox & Direct Messages (DMs)", font=("Consolas", 12, "bold"), fg="#ff79c6", bg="#0b0d17")
        lbl.pack(anchor="w", pady=(0, 10))
        msg_box = tk.Text(f, bg="#131625", fg="#e0e0e0", font=("Consolas", 10), wrap="word", bd=0)
        msg_box.pack(fill=tk.BOTH, expand=True)
        msg_box.insert(tk.END, "📬 System Inbox:\n- [SYSTEM]: Security verification logged for user Gravity.\n- [MESH]: Node 192.168.1.102 connected to local mesh.\n- [ADMIN]: Account cooldown policy active.")
        msg_box.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    app = OrbitalNavigatorWorkstation(root)
    root.mainloop()
