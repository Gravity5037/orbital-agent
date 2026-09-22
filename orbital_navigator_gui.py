import os
import sys
import json
import time
import urllib.request
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

DB_PATH = r"C:\Orbital\users_db.json"
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5-coder:1.5b"

PALETTES = {
    "Midnight Dream": {
        "bg": "#0a0e1a", "card": "#121829", "border": "#2a344e",
        "text": "#f3f4f6", "muted": "#9ca3af", "accent": "#8b5cf6",
        "accent_glow": "#a78bfa", "entry_bg": "#1c233d", "btn_text": "#ffffff"
    },
    "Aquatic Depths": {
        "bg": "#03131e", "card": "#0a2540", "border": "#1e3a5f",
        "text": "#e0f2fe", "muted": "#7dd3fc", "accent": "#00f2fe",
        "accent_glow": "#38bdf8", "entry_bg": "#0f3456", "btn_text": "#03131e"
    },
    "Obsidian Stealth": {
        "bg": "#080808", "card": "#141416", "border": "#27272a",
        "text": "#f4f4f5", "muted": "#a1a1aa", "accent": "#10b981",
        "accent_glow": "#34d399", "entry_bg": "#1f1f23", "btn_text": "#ffffff"
    },
    "Sunset Cosmic": {
        "bg": "#181a2f", "card": "#242e49", "border": "#37415c",
        "text": "#fef2f2", "muted": "#fca5a5", "accent": "#b4182d",
        "accent_glow": "#fda481", "entry_bg": "#2d3859", "btn_text": "#ffffff"
    },
    "Oceanic Abyssal": {
        "bg": "#031716", "card": "#032f30", "border": "#0a7075",
        "text": "#e6f4f1", "muted": "#6ba3be", "accent": "#0c969c",
        "accent_glow": "#274d60", "entry_bg": "#064244", "btn_text": "#ffffff"
    }
}

def load_db():
    if not os.path.exists(r"C:\Orbital"):
        os.makedirs(r"C:\Orbital", exist_ok=True)
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                db = json.load(f)
                if "users" not in db: db["users"] = {}
                if "cooldowns" not in db: db["cooldowns"] = {}
                if "friends" not in db: db["friends"] = {}
                if "friend_requests" not in db: db["friend_requests"] = {}
                return db
        except Exception:
            pass
    db = {"users": {}, "cooldowns": {}, "friends": {}, "friend_requests": {}}
    save_db(db)
    return db

def save_db(db):
    for k in ["users", "cooldowns", "friends", "friend_requests"]:
        if k not in db or not isinstance(db[k], dict):
            db[k] = {}
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4)

def run_github_sync(repo_dir=r"C:\Orbital", auto_push=True):
    if not os.path.exists(os.path.join(repo_dir, ".git")):
        if os.path.exists(r"C:\Orbital_FlashDrive\.git"):
            repo_dir = r"C:\Orbital_FlashDrive"
        else:
            return "error", "Git repo not initialized in C:\\Orbital."
    try:
        subprocess.run(["git", "fetch", "origin"], cwd=repo_dir, capture_output=True, text=True, timeout=12)
        head_hash = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True).stdout.strip()
        up_res = subprocess.run(["git", "rev-parse", "@{u}"], cwd=repo_dir, capture_output=True, text=True)
        up_hash = up_res.stdout.strip() if up_res.returncode == 0 else ""
        
        status_res = subprocess.run(["git", "status", "--porcelain"], cwd=repo_dir, capture_output=True, text=True)
        has_changes = bool(status_res.stdout.strip())
        
        if has_changes and auto_push:
            subprocess.run(["git", "add", "-A"], cwd=repo_dir, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Orbital auto-sync update"], cwd=repo_dir, capture_output=True)
            push_res = subprocess.run(["git", "push", "origin", "main"], cwd=repo_dir, capture_output=True, text=True, timeout=20)
            if push_res.returncode == 0:
                return "pushed", "Local updates pushed to GitHub successfully!"
        
        if up_hash and head_hash != up_hash:
            return "newer_available", "Newer version detected on GitHub!"
        return "up_to_date", "Orbital is fully up-to-date with GitHub."
    except Exception as e:
        return "error", f"GitHub Sync: {e}"

def ensure_nucleus_running():
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                return True
    except Exception:
        pass
    app_dir = os.path.dirname(os.path.abspath(__file__))
    engine_path = os.path.join(app_dir, "engine.py")
    if os.path.exists(engine_path):
        try:
            subprocess.Popen([sys.executable, engine_path])
            time.sleep(1.5)
        except Exception:
            pass
    return False

class DragDropTransferHub(tk.Frame):
    def __init__(self, master, current_user="Guest", palette=None, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.current_user = current_user
        self.palette = palette or PALETTES["Midnight Dream"]
        self.config(bg=self.palette["bg"])
        self.selected_file = None
        self._build_ui()

    def _build_ui(self):
        lbl = tk.Label(self, text="📦 Cross-Instance Drag & Drop Transfer Hub", font=("Consolas", 12, "bold"), fg=self.palette["accent"], bg=self.palette["bg"])
        lbl.pack(anchor="w", pady=(0, 10))

        desc = tk.Label(self, text="Select files, nodes, or checkpoints to route and sync across active Orbital instance profiles.", font=("Consolas", 9), fg=self.palette["muted"], bg=self.palette["bg"])
        desc.pack(anchor="w", pady=(0, 15))

        self.drop_zone = tk.Canvas(self, bg=self.palette["card"], bd=1, relief="solid", highlightbackground=self.palette["border"], highlightthickness=1, height=120)
        self.drop_zone.pack(fill=tk.X, pady=(0, 15))

        self.drop_text = self.drop_zone.create_text(280, 60, text="📁 Click Here or Drag & Drop Payload File", font=("Consolas", 11, "bold"), fill=self.palette["accent_glow"])
        self.drop_zone.bind("<Button-1>", lambda e: self._select_file())

        target_frame = tk.Frame(self, bg=self.palette["bg"])
        target_frame.pack(fill=tk.X, pady=(0, 15))

        tk.Label(target_frame, text="Target User Instance:", font=("Consolas", 10, "bold"), fg=self.palette["text"], bg=self.palette["bg"]).pack(side=tk.LEFT, padx=(0, 10))

        self.target_var = tk.StringVar(value="Select Target User...")
        self.target_dropdown = ttk.Combobox(target_frame, textvariable=self.target_var, state="readonly", font=("Consolas", 10))
        self.target_dropdown.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.refresh_targets()

        send_btn = tk.Button(target_frame, text="⚡ Transfer Payload", font=("Consolas", 10, "bold"), fg=self.palette["btn_text"], bg=self.palette["accent"], bd=0, padx=16, pady=6, command=self._transfer_file)
        send_btn.pack(side=tk.RIGHT)

        self.status_lbl = tk.Label(self, text="Ready for transfer.", font=("Consolas", 9), fg=self.palette["muted"], bg=self.palette["bg"])
        self.status_lbl.pack(anchor="w")

    def refresh_targets(self):
        db = load_db()
        users = [u for u in db.get("users", {}).keys() if u != self.current_user]
        if not users:
            users = ["No Other Instances Found"]
        self.target_dropdown["values"] = users
        if users:
            self.target_var.set(users[0])

    def _select_file(self):
        f = filedialog.askopenfilename(title="Select Payload File to Transfer")
        if f:
            self.selected_file = f
            fname = os.path.basename(f)
            self.drop_zone.itemconfig(self.drop_text, text=f"📄 Selected Payload: {fname}")
            self.status_lbl.config(text=f"Selected file: {f}")

    def _transfer_file(self):
        if not self.selected_file or not os.path.exists(self.selected_file):
            messagebox.showwarning("No File", "Please select a file to transfer first.")
            return
        target_user = self.target_var.get()
        if target_user in ["Select Target User...", "No Other Instances Found"]:
            messagebox.showwarning("Invalid Target", "Please select a valid target user instance.")
            return

        target_dir = os.path.join(r"C:\Orbital\users", target_user)
        os.makedirs(target_dir, exist_ok=True)

        fname = os.path.basename(self.selected_file)
        dest_path = os.path.join(target_dir, fname)

        try:
            import shutil
            shutil.copy(self.selected_file, dest_path)
            self.status_lbl.config(text=f"✔ Transferred '{fname}' to user '{target_user}' workspace successfully!")
            messagebox.showinfo("Transfer Success", f"Payload '{fname}' successfully synced to '{target_user}' workspace!\n\nDestination:\n{dest_path}")
        except Exception as e:
            messagebox.showerror("Transfer Error", f"Failed to transfer file: {e}")

class OnboardingWizard(tk.Toplevel):
    def __init__(self, master, username, palette, on_complete):
        super().__init__(master)
        self.username = username
        self.palette = palette
        self.on_complete = on_complete
        self.step = 1

        self.title("Orbital OS - New User Onboarding")
        self.geometry("540x440")
        self.configure(bg=self.palette["bg"])
        self.resizable(False, False)

        self._build_step()

    def _build_step(self):
        for w in self.winfo_children():
            w.destroy()

        card = tk.Frame(self, bg=self.palette["card"], bd=1, relief="solid", highlightbackground=self.palette["border"], highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        if self.step == 1:
            tk.Label(card, text="🚀 Welcome to Orbital OS!", font=("Consolas", 14, "bold"), fg=self.palette["accent"], bg=self.palette["card"]).pack(anchor="w", padx=20, pady=(20, 10))
            desc = f"Hello {self.username}!\n\nOrbital OS is your persistent, self-evolving workstation.\n\nKey Sub-Systems:\n- 💬 Local Nucleus AI Chat\n- 📡 Omnipose CSI Spatial Presence Sensing\n- 📷 Live Web Camera Video Feeds\n- 🎨 Unconstrained Image Generator\n- 🎵 Connected Media Controller\n- 📬 Inbox & Direct Messaging\n- 📦 Drag & Drop Payload Transfers"
            tk.Label(card, text=desc, font=("Consolas", 10), fg=self.palette["text"], bg=self.palette["card"], justify="left").pack(anchor="w", padx=20, pady=10)

        elif self.step == 2:
            tk.Label(card, text="🎵 Connect Music Ecosystem", font=("Consolas", 14, "bold"), fg=self.palette["accent"], bg=self.palette["card"]).pack(anchor="w", padx=20, pady=(20, 10))
            tk.Label(card, text="Select your primary streaming music platform to link with Orbital Media Controller:", font=("Consolas", 10), fg=self.palette["text"], bg=self.palette["card"], justify="left").pack(anchor="w", padx=20, pady=10)

            self.music_var = tk.StringVar(value="Spotify")
            for app in ["Spotify", "Apple Music", "Pandora", "YouTube Music"]:
                rb = tk.Radiobutton(card, text=app, value=app, variable=self.music_var, font=("Consolas", 10, "bold"), fg=self.palette["text"], bg=self.palette["card"], selectcolor=self.palette["card"], activebackground=self.palette["card"])
                rb.pack(anchor="w", padx=40, pady=5)

        elif self.step == 3:
            tk.Label(card, text="🎨 Choose Your Theme", font=("Consolas", 14, "bold"), fg=self.palette["accent"], bg=self.palette["card"]).pack(anchor="w", padx=20, pady=(20, 10))
            tk.Label(card, text="Select your initial aesthetic color palette:", font=("Consolas", 10), fg=self.palette["text"], bg=self.palette["card"]).pack(anchor="w", padx=20, pady=10)

            self.theme_var = tk.StringVar(value="Midnight Dream")
            for t_name in PALETTES.keys():
                rb = tk.Radiobutton(card, text=t_name, value=t_name, variable=self.theme_var, font=("Consolas", 10, "bold"), fg=self.palette["text"], bg=self.palette["card"], selectcolor=self.palette["card"], activebackground=self.palette["card"])
                rb.pack(anchor="w", padx=40, pady=5)

        elif self.step == 4:
            tk.Label(card, text="✔ Onboarding Complete!", font=("Consolas", 14, "bold"), fg=self.palette["accent"], bg=self.palette["card"]).pack(anchor="w", padx=20, pady=(20, 10))
            desc = f"Your profile '{self.username}' is fully configured and ready.\n\nClick Finish below to launch your workstation!"
            tk.Label(card, text=desc, font=("Consolas", 10), fg=self.palette["text"], bg=self.palette["card"], justify="left").pack(anchor="w", padx=20, pady=20)

        nav_frame = tk.Frame(card, bg=self.palette["card"])
        nav_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=20)

        if self.step > 1:
            btn_back = tk.Button(nav_frame, text="◀ Back", font=("Consolas", 10, "bold"), fg=self.palette["text"], bg=self.palette["entry_bg"], bd=0, padx=14, pady=6, command=self._prev_step)
            btn_back.pack(side=tk.LEFT)

        btn_text = "Finish ➔" if self.step == 4 else "Next ➔"
        btn_next = tk.Button(nav_frame, text=btn_text, font=("Consolas", 10, "bold"), fg=self.palette["btn_text"], bg=self.palette["accent"], bd=0, padx=16, pady=6, command=self._next_step)
        btn_next.pack(side=tk.RIGHT)

    def _prev_step(self):
        if self.step > 1:
            self.step -= 1
            self._build_step()

    def _next_step(self):
        db = load_db()
        if self.step == 2:
            if self.username in db["users"]:
                db["users"][self.username]["music_app"] = self.music_var.get()
                save_db(db)
        elif self.step == 3:
            if self.username in db["users"]:
                db["users"][self.username]["theme"] = self.theme_var.get()
                save_db(db)

        if self.step < 4:
            self.step += 1
            self._build_step()
        else:
            self.destroy()
            if self.on_complete:
                self.on_complete()

class SettingsModal(tk.Toplevel):
    def __init__(self, master, username, palette, on_theme_change):
        super().__init__(master)
        self.username = username
        self.palette = palette
        self.on_theme_change = on_theme_change
        self.db = load_db()

        self.title(f"Orbital User Settings - {self.username}")
        self.geometry("560x560")
        self.configure(bg=self.palette["bg"])
        self.resizable(False, False)

        self._build_ui()

    def _build_ui(self):
        card = tk.Frame(self, bg=self.palette["card"], bd=1, relief="solid", highlightbackground=self.palette["border"], highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        lbl = tk.Label(card, text=f"⚙️ Account Settings ({self.username})", font=("Consolas", 14, "bold"), fg=self.palette["accent"], bg=self.palette["card"])
        lbl.pack(anchor="w", padx=20, pady=(20, 10))

        tk.Label(card, text="Email or Contact:", font=("Consolas", 9, "bold"), fg=self.palette["muted"], bg=self.palette["card"]).pack(anchor="w", padx=20)
        self.email_entry = tk.Entry(card, font=("Consolas", 10), bg=self.palette["entry_bg"], fg=self.palette["text"], insertbackground=self.palette["text"], bd=1, relief="solid")
        curr_contact = self.db.get("users", {}).get(self.username, {}).get("contact", "")
        self.email_entry.insert(0, curr_contact)
        self.email_entry.pack(fill=tk.X, padx=20, pady=(2, 10), ipady=4)

        tk.Label(card, text="New Password:", font=("Consolas", 9, "bold"), fg=self.palette["muted"], bg=self.palette["card"]).pack(anchor="w", padx=20)
        self.pass_entry = tk.Entry(card, show="*", font=("Consolas", 10), bg=self.palette["entry_bg"], fg=self.palette["text"], insertbackground=self.palette["text"], bd=1, relief="solid")
        self.pass_entry.pack(fill=tk.X, padx=20, pady=(2, 10), ipady=4)

        tk.Label(card, text="Active Theme:", font=("Consolas", 9, "bold"), fg=self.palette["muted"], bg=self.palette["card"]).pack(anchor="w", padx=20)
        self.theme_var = tk.StringVar(value=self.db.get("users", {}).get(self.username, {}).get("theme", "Midnight Dream"))
        theme_dropdown = ttk.Combobox(card, textvariable=self.theme_var, values=list(PALETTES.keys()), state="readonly", font=("Consolas", 10))
        theme_dropdown.pack(fill=tk.X, padx=20, pady=(2, 15))

        btn_row = tk.Frame(card, bg=self.palette["card"])
        btn_row.pack(fill=tk.X, padx=20, pady=(0, 15))

        save_btn = tk.Button(btn_row, text="💾 Save Changes", font=("Consolas", 10, "bold"), fg=self.palette["btn_text"], bg=self.palette["accent"], bd=0, padx=14, pady=6, command=self._save_settings)
        save_btn.pack(side=tk.LEFT, padx=(0, 10))

        sync_btn = tk.Button(btn_row, text="🔄 GitHub Sync", font=("Consolas", 10, "bold"), fg=self.palette["btn_text"], bg=self.palette["accent_glow"], bd=0, padx=14, pady=6, command=self._trigger_sync)
        sync_btn.pack(side=tk.LEFT)

        tk.Frame(card, bg=self.palette["border"], height=1).pack(fill=tk.X, padx=20, pady=10)

        del_frame = tk.Frame(card, bg=self.palette["card"])
        del_frame.pack(fill=tk.X, padx=20, pady=10)

        if self.username == "Gravity":
            tk.Label(del_frame, text="🔒 Admin Account Protected (Cannot Be Deleted)", font=("Consolas", 9, "bold"), fg=self.palette["accent_glow"], bg=self.palette["card"]).pack(anchor="w")
        else:
            del_btn = tk.Button(del_frame, text="🗑️ Delete Account & Data", font=("Consolas", 10, "bold"), fg="#ffffff", bg="#b4182d", bd=0, padx=14, pady=6, command=self._prompt_delete)
            del_btn.pack(anchor="w")

    def _trigger_sync(self):
        st_type, msg = run_github_sync(auto_push=True)
        if st_type == "pushed":
            messagebox.showinfo("GitHub Sync", f"✔ Success: {msg}")
        elif st_type == "newer_available":
            ans = messagebox.askyesno("Update Available", f"{msg}\n\nWould you like to pull the newest version from GitHub now?")
            if ans:
                subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=r"C:\Orbital", capture_output=True)
                messagebox.showinfo("Updated", "Orbital has been updated to the latest GitHub version! Please restart.")
        elif st_type == "up_to_date":
            messagebox.showinfo("GitHub Sync", f"✔ Up-to-date: {msg}")
        else:
            messagebox.showwarning("Sync Warning", msg)

    def _save_settings(self):
        new_contact = self.email_entry.get().strip()
        new_pass = self.pass_entry.get().strip()
        new_theme = self.theme_var.get()

        if self.username in self.db["users"]:
            if new_contact: self.db["users"][self.username]["contact"] = new_contact
            if new_pass: self.db["users"][self.username]["password"] = new_pass
            self.db["users"][self.username]["theme"] = new_theme
            save_db(self.db)
            messagebox.showinfo("Saved", "Settings updated successfully!")
            if self.on_theme_change:
                self.on_theme_change(new_theme)
            self.destroy()

    def _prompt_delete(self):
        DelConfirmModal(self, self.username, self.palette)

class DelConfirmModal(tk.Toplevel):
    def __init__(self, master, username, palette):
        super().__init__(master)
        self.username = username
        self.palette = palette
        self.count = 5

        self.title("Confirm Account Deletion")
        self.geometry("480x280")
        self.configure(bg=self.palette["bg"])
        self.resizable(False, False)

        self._build_ui()

    def _build_ui(self):
        card = tk.Frame(self, bg=self.palette["card"], bd=1, relief="solid", highlightbackground=self.palette["border"], highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        tk.Label(card, text="⚠️ PERMANENT ACCOUNT DELETION", font=("Consolas", 12, "bold"), fg="#b4182d", bg=self.palette["card"]).pack(anchor="w", padx=15, pady=(15, 10))

        desc = f"Are you sure you want to delete account '{self.username}'?\n\n- All local workspace files will be permanently purged.\n- Your username will be placed on a 7-day reservation cooldown.\n- This action CANNOT be undone."
        tk.Label(card, text=desc, font=("Consolas", 9), fg=self.palette["text"], bg=self.palette["card"], justify="left").pack(anchor="w", padx=15, pady=5)

        self.btn = tk.Button(card, text=f"Yes, I'm sure I would like to delete my account and data ({self.count}s)", font=("Consolas", 9, "bold"), fg="#ffffff", bg="#555555", state="disabled", bd=0, padx=10, pady=8, command=self._execute_delete)
        self.btn.pack(pady=15)

        self._countdown()

    def _countdown(self):
        if self.count > 0:
            self.btn.config(text=f"Yes, I'm sure I would like to delete my account and data ({self.count}s)")
            self.count -= 1
            self.after(1000, self._countdown)
        else:
            self.btn.config(text="Yes, I'm sure I would like to delete my account and data", state="normal", bg="#b4182d")

    def _execute_delete(self):
        db = load_db()
        if self.username in db["users"]:
            del db["users"][self.username]
            db["cooldowns"][self.username] = datetime.datetime.now().isoformat()
            save_db(db)
            messagebox.showinfo("Account Deleted", f"Account '{self.username}' has been deleted. Username is reserved for 7 days.")
            os._exit(0)

class OrbitalNavigatorWorkstation:
    def __init__(self, root, username="Operator"):
        self.root = root
        self.username = username
        self.db = load_db()

        u_data = self.db.get("users", {}).get(self.username, {})
        self.theme_name = u_data.get("theme", "Midnight Dream")
        self.palette = PALETTES.get(self.theme_name, PALETTES["Midnight Dream"])

        self.root.title(f"Orbital OS Workstation - {self.username}")
        self.root.geometry("1024x720")
        self.root.configure(bg=self.palette["bg"])

        self.cam_running = False
        self.cam_thread = None

        self._build_ui()
        self._start_background_sync()

        if "--onboard" in sys.argv:
            OnboardingWizard(self.root, self.username, self.palette, on_complete=self._refresh_theme_from_db)

    def _start_background_sync(self):
        def _auto_sync_loop():
            while True:
                time.sleep(300)
                st, msg = run_github_sync(auto_push=True)
                if st == "newer_available":
                    self.root.after(0, lambda: self.sync_status_lbl.config(text="⚡ Update Available on GitHub!", fg="#00f2fe"))
                elif st in ["pushed", "up_to_date"]:
                    self.root.after(0, lambda: self.sync_status_lbl.config(text="🟢 GitHub Sync: Active (Every 5m)", fg=self.palette["accent_glow"]))

        threading.Thread(target=_auto_sync_loop, daemon=True).start()

    def _refresh_theme_from_db(self):
        self.db = load_db()
        u_data = self.db.get("users", {}).get(self.username, {})
        self.theme_name = u_data.get("theme", "Midnight Dream")
        self.palette = PALETTES.get(self.theme_name, PALETTES["Midnight Dream"])
        self.apply_theme(self.theme_name)

    def apply_theme(self, t_name):
        self.theme_name = t_name
        self.palette = PALETTES[t_name]

        self.root.configure(bg=self.palette["bg"])
        self.top_bar.configure(bg=self.palette["bg"])
        self.nav_frame.configure(bg=self.palette["card"], highlightbackground=self.palette["border"])
        self.main_content.configure(bg=self.palette["bg"])

        for f in self.frames.values():
            f.configure(bg=self.palette["bg"])

        self.switch_tab("chat")

    def _build_ui(self):
        self.top_bar = tk.Frame(self.root, bg=self.palette["bg"], pady=8, padx=15)
        self.top_bar.pack(fill=tk.X)

        title = tk.Label(self.top_bar, text=f"🛸 ORBITAL WORKSTATION // {self.username.upper()}", font=("Consolas", 12, "bold"), fg=self.palette["accent"], bg=self.palette["bg"])
        title.pack(side=tk.LEFT)

        self.sync_status_lbl = tk.Label(self.top_bar, text="🟢 GitHub Sync: Active (Every 5m)", font=("Consolas", 9, "bold"), fg=self.palette["accent_glow"], bg=self.palette["bg"])
        self.sync_status_lbl.pack(side=tk.LEFT, padx=(20, 0))

        settings_btn = tk.Button(self.top_bar, text="⚙️ Settings", font=("Consolas", 9, "bold"), fg=self.palette["btn_text"], bg=self.palette["accent"], bd=0, padx=12, pady=4, command=self._open_settings)
        settings_btn.pack(side=tk.RIGHT)

        body = tk.Frame(self.root, bg=self.palette["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        self.nav_frame = tk.Frame(body, bg=self.palette["card"], width=220, bd=1, relief="solid", highlightbackground=self.palette["border"], highlightthickness=1)
        self.nav_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        self.nav_frame.pack_propagate(False)

        self.main_content = tk.Frame(body, bg=self.palette["bg"])
        self.main_content.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tk.Label(self.nav_frame, text="🔮 ORB HUB", font=("Consolas", 11, "bold"), fg=self.palette["accent_glow"], bg=self.palette["card"]).pack(anchor="w", padx=15, pady=15)

        tabs = [
            ("💬 AI Chat HUD", "chat"),
            ("📡 Omnipose Sensing", "presence"),
            ("📷 Web Cameras", "camera"),
            ("🎨 Image Generator", "image_gen"),
            ("🎵 Connected Media", "media"),
            ("📬 Inbox & DMs", "inbox"),
            ("📦 Drag/Drop Hub", "transfer")
        ]

        self.nav_buttons = {}
        for text, key in tabs:
            btn = tk.Button(self.nav_frame, text=text, font=("Consolas", 10, "bold"), fg=self.palette["muted"], bg=self.palette["card"], activebackground=self.palette["entry_bg"], bd=0, anchor="w", padx=15, pady=8, command=lambda k=key: self.switch_tab(k))
            btn.pack(fill=tk.X, pady=2)
            self.nav_buttons[key] = btn

        self.frames = {}
        for _, key in tabs:
            f = tk.Frame(self.main_content, bg=self.palette["bg"])
            self.frames[key] = f

        self._build_chat_tab()
        self._build_presence_tab()
        self._build_camera_tab()
        self._build_image_gen_tab()
        self._build_media_tab()
        self._build_inbox_tab()
        self._build_transfer_tab()

        self.switch_tab("chat")

    def _open_settings(self):
        SettingsModal(self.root, self.username, self.palette, on_theme_change=self.apply_theme)

    def switch_tab(self, key):
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.config(bg=self.palette["accent"], fg=self.palette["btn_text"])
            else:
                btn.config(bg=self.palette["card"], fg=self.palette["muted"])
        for f in self.frames.values():
            f.pack_forget()
        self.frames[key].pack(fill=tk.BOTH, expand=True)

    def _build_chat_tab(self):
        f = self.frames["chat"]
        lbl = tk.Label(f, text="💬 Orbital AI Chat HUD", font=("Consolas", 12, "bold"), fg=self.palette["accent"], bg=self.palette["bg"])
        lbl.pack(anchor="w", pady=(0, 10))

        chat_frame = tk.Frame(f, bg=self.palette["bg"])
        chat_frame.pack(fill=tk.BOTH, expand=True)

        self.chat_text = tk.Text(chat_frame, bg=self.palette["card"], fg=self.palette["text"], font=("Consolas", 10), wrap="word", bd=1, relief="solid", highlightbackground=self.palette["border"])
        sb = ttk.Scrollbar(chat_frame, orient="vertical", command=self.chat_text.yview)
        self.chat_text.configure(yscrollcommand=sb.set)
        self.chat_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.chat_text.tag_config("sys_tag", foreground=self.palette["accent_glow"], font=("Consolas", 10, "bold"))
        self.chat_text.tag_config("user_tag", foreground=self.palette["text"], font=("Consolas", 10, "bold"))
        self.chat_text.tag_config("orb_tag", foreground=self.palette["accent"], font=("Consolas", 10, "bold"))

        input_frame = tk.Frame(f, bg=self.palette["bg"], pady=8)
        input_frame.pack(fill=tk.X, pady=(10, 0))

        self.entry = tk.Entry(input_frame, font=("Consolas", 11), bg=self.palette["card"], fg=self.palette["text"], insertbackground=self.palette["text"], bd=1, relief="solid")
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=6)
        self.entry.bind("<Return>", lambda e: self.send_chat())

        send_btn = tk.Button(input_frame, text="Send ➔", font=("Consolas", 10, "bold"), fg=self.palette["btn_text"], bg=self.palette["accent"], bd=0, padx=16, pady=6, command=self.send_chat)
        send_btn.pack(side=tk.RIGHT)

        self._append_chat("System", f"Orbital Workstation Active for {self.username}. Ready.")

    def _append_chat(self, sender, text):
        self.chat_text.config(state="normal")
        tag = "sys_tag" if sender.lower() == "system" else ("user_tag" if sender.lower() in ["you", self.username.lower()] else "orb_tag")
        self.chat_text.insert(tk.END, f"{sender}: ", tag)
        self.chat_text.insert(tk.END, f"{text}\n\n")
        self.chat_text.config(state="disabled")
        self.chat_text.see(tk.END)

    def send_chat(self):
        val = self.entry.get().strip()
        if not val: return
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
        lbl = tk.Label(f, text="📡 Omnipose Wi-Fi CSI Presence & Pose Tracking", font=("Consolas", 12, "bold"), fg=self.palette["accent"], bg=self.palette["bg"])
        lbl.pack(anchor="w", pady=(0, 10))

        scan_btn = tk.Button(f, text="⚡ Run 3D CSI Radar Scan", font=("Consolas", 10, "bold"), fg=self.palette["btn_text"], bg=self.palette["accent"], bd=0, padx=16, pady=8, command=self._run_csi_scan)
        scan_btn.pack(anchor="w", pady=(0, 10))

        self.csi_canvas = tk.Canvas(f, bg=self.palette["card"], bd=1, relief="solid", highlightbackground=self.palette["border"])
        self.csi_canvas.pack(fill=tk.BOTH, expand=True)

    def _run_csi_scan(self):
        messagebox.showinfo("CSI Sensing", "Initiating sub-GHz disruption frequency sweep...")

    def _build_camera_tab(self):
        f = self.frames["camera"]
        lbl = tk.Label(f, text="📷 Web Cameras & Live Optical Stream", font=("Consolas", 12, "bold"), fg=self.palette["accent"], bg=self.palette["bg"])
        lbl.pack(anchor="w", pady=(0, 10))

        btn_frame = tk.Frame(f, bg=self.palette["bg"])
        btn_frame.pack(anchor="w", pady=(0, 10))

        self.cam_btn = tk.Button(btn_frame, text="📹 Start Live Camera Stream", font=("Consolas", 10, "bold"), fg=self.palette["btn_text"], bg=self.palette["accent"], bd=0, padx=16, pady=8, command=self._toggle_cam)
        self.cam_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.cam_display = tk.Label(f, text="[Camera Stream Offline]", font=("Consolas", 12, "bold"), fg=self.palette["muted"], bg=self.palette["card"])
        self.cam_display.pack(fill=tk.BOTH, expand=True)

    def _toggle_cam(self):
        if not self.cam_running:
            self.cam_running = True
            self.cam_btn.config(text="⏹ Stop Camera Stream", bg="#b4182d")
            self.cam_thread = threading.Thread(target=self._cam_loop, daemon=True)
            self.cam_thread.start()
        else:
            self.cam_running = False
            self.cam_btn.config(text="📹 Start Live Camera Stream", bg=self.palette["accent"])
            self.cam_display.config(text="[Camera Stream Offline]", image="")

    def _cam_loop(self):
        try:
            import cv2
            from PIL import Image, ImageTk
            cap = cv2.VideoCapture(0)
            while self.cam_running and cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame)
                    img = img.resize((640, 360))
                    imgtk = ImageTk.PhotoImage(image=img)
                    self.root.after(0, lambda i=imgtk: self.cam_display.config(image=i, text=""))
                    self.cam_display.image = imgtk
                time.sleep(0.03)
            cap.release()
        except Exception as e:
            self.cam_running = False
            self.root.after(0, lambda: messagebox.showerror("Camera Error", f"OpenCV Camera Feed Error: {e}"))

    def _build_image_gen_tab(self):
        f = self.frames["image_gen"]
        lbl = tk.Label(f, text="🎨 Unconstrained Image Generator", font=("Consolas", 12, "bold"), fg=self.palette["accent"], bg=self.palette["bg"])
        lbl.pack(anchor="w", pady=(0, 10))

        self.img_prompt = tk.Entry(f, font=("Consolas", 11), bg=self.palette["card"], fg=self.palette["text"], insertbackground=self.palette["text"], bd=1, relief="solid")
        self.img_prompt.insert(0, "A cybernetic orbital station above earth in dark aesthetic")
        self.img_prompt.pack(fill=tk.X, pady=(0, 10), ipady=6)

        gen_btn = tk.Button(f, text="🎨 Render Image", font=("Consolas", 10, "bold"), fg=self.palette["btn_text"], bg=self.palette["accent"], bd=0, padx=16, pady=8, command=self._gen_img)
        gen_btn.pack(anchor="w")

    def _gen_img(self):
        messagebox.showinfo("Image Generator", f"Rendering image for prompt:\n'{self.img_prompt.get()}'")

    def _build_media_tab(self):
        f = self.frames["media"]
        lbl = tk.Label(f, text="🎵 Connected Media Controller", font=("Consolas", 12, "bold"), fg=self.palette["accent"], bg=self.palette["bg"])
        lbl.pack(anchor="w", pady=(0, 10))

        m_frame = tk.Frame(f, bg=self.palette["card"], padx=20, pady=20, bd=1, relief="solid", highlightbackground=self.palette["border"])
        m_frame.pack(fill=tk.X, pady=(0, 15))

        linked_app = self.db.get("users", {}).get(self.username, {}).get("music_app", "Spotify")
        now_playing = tk.Label(m_frame, text=f"▶ Now Playing on {linked_app}: Orbital Ambient Wave", font=("Consolas", 10, "bold"), fg=self.palette["accent_glow"], bg=self.palette["card"])
        now_playing.pack(anchor="w", pady=(0, 15))

    def _build_inbox_tab(self):
        f = self.frames["inbox"]
        lbl = tk.Label(f, text="📬 Inbox, Direct Messages & Friends", font=("Consolas", 12, "bold"), fg=self.palette["accent"], bg=self.palette["bg"])
        lbl.pack(anchor="w", pady=(0, 10))

        search_frame = tk.Frame(f, bg=self.palette["bg"])
        search_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(search_frame, text="Find User:", font=("Consolas", 9, "bold"), fg=self.palette["text"], bg=self.palette["bg"]).pack(side=tk.LEFT, padx=(0, 5))
        self.friend_search_entry = tk.Entry(search_frame, font=("Consolas", 10), bg=self.palette["card"], fg=self.palette["text"], insertbackground=self.palette["text"], bd=1, relief="solid")
        self.friend_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=4)

        add_btn = tk.Button(search_frame, text="➕ Send Friend Request", font=("Consolas", 9, "bold"), fg=self.palette["btn_text"], bg=self.palette["accent"], bd=0, padx=10, pady=4, command=self._send_friend_req)
        add_btn.pack(side=tk.RIGHT)

        self.msg_box = tk.Text(f, bg=self.palette["card"], fg=self.palette["text"], font=("Consolas", 10), wrap="word", bd=1, relief="solid", highlightbackground=self.palette["border"])
        self.msg_box.pack(fill=tk.BOTH, expand=True)
        self.msg_box.insert(tk.END, f"📬 System Inbox for {self.username}:\n- [SYSTEM]: Welcome to Orbital DMs.\n- [INFO]: Use search bar above to connect with other Orbital profiles.")
        self.msg_box.config(state="disabled")

    def _send_friend_req(self):
        target = self.friend_search_entry.get().strip()
        if not target: return
        self.db = load_db()
        if target not in self.db.get("users", {}):
            messagebox.showerror("User Not Found", f"User '{target}' does not exist.")
            return
        if target == self.username:
            messagebox.showwarning("Invalid", "Cannot add yourself.")
            return

        if target not in self.db["friend_requests"]:
            self.db["friend_requests"][target] = []
        if self.username not in self.db["friend_requests"][target]:
            self.db["friend_requests"][target].append(self.username)
            save_db(self.db)
            messagebox.showinfo("Request Sent", f"Friend request sent to '{target}'!")
        else:
            messagebox.showinfo("Already Sent", f"Friend request to '{target}' is already pending.")

    def _build_transfer_tab(self):
        f = self.frames["transfer"]
        hub = DragDropTransferHub(f, current_user=self.username, palette=self.palette)
        hub.pack(fill=tk.BOTH, expand=True)

if __name__ == "__main__":
    user = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "Operator"
    root = tk.Tk()
    app = OrbitalNavigatorWorkstation(root, username=user)
    root.mainloop()
