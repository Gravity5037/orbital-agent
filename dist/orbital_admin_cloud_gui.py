import os
import sys
import json
import datetime
import math
import threading
import time
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

DB_PATH = r"C:\Orbital\users_db.json"

def load_db():
    if not os.path.exists(r"C:\Orbital"):
        os.makedirs(r"C:\Orbital", exist_ok=True)
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                db = json.load(f)
                if "users" not in db: db["users"] = {}
                if "cooldowns" not in db: db["cooldowns"] = {}
                return db
        except Exception:
            pass
    db = {"users": {}, "cooldowns": {}}
    save_db(db)
    return db

def save_db(db):
    if "users" not in db: db["users"] = {}
    if "cooldowns" not in db: db["cooldowns"] = {}
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

class AdminCloudApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Orbital Admin Spatial Cloud - Gravity Control Matrix")
        self.root.geometry("960x680")
        self.root.configure(bg="#0a0e1a")

        self.db = load_db()
        self.selected_user = None

        self._build_ui()
        self._start_background_sync()

    def _start_background_sync(self):
        def _auto_sync_loop():
            while True:
                time.sleep(300)
                st, msg = run_github_sync(auto_push=True)
                if st == "newer_available":
                    self.root.after(0, lambda: self.sync_status_lbl.config(text="⚡ Newer GitHub Version Detected!", fg="#00f2fe"))
                elif st in ["pushed", "up_to_date"]:
                    self.root.after(0, lambda: self.sync_status_lbl.config(text="🟢 GitHub Sync: Active (Every 5m)", fg="#a78bfa"))

        threading.Thread(target=_auto_sync_loop, daemon=True).start()

    def _build_ui(self):
        top_bar = tk.Frame(self.root, bg="#0a0e1a", pady=10, padx=15)
        top_bar.pack(fill=tk.X)

        lbl = tk.Label(top_bar, text="⚡ ORBITAL ADMIN CLOUD MATRIX // GRAVITY CORE", font=("Consolas", 12, "bold"), fg="#8b5cf6", bg="#0a0e1a")
        lbl.pack(side=tk.LEFT)

        self.sync_status_lbl = tk.Label(top_bar, text="🟢 GitHub Sync: Active (Every 5m)", font=("Consolas", 9, "bold"), fg="#a78bfa", bg="#0a0e1a")
        self.sync_status_lbl.pack(side=tk.LEFT, padx=(15, 0))

        sync_btn = tk.Button(top_bar, text="🔄 Sync GitHub", font=("Consolas", 9, "bold"), fg="#ffffff", bg="#00f2fe", bd=0, padx=10, pady=4, command=self._manual_sync)
        sync_btn.pack(side=tk.RIGHT, padx=(10, 0))

        add_inst_btn = tk.Button(top_bar, text="➕ Add User Instance", font=("Consolas", 9, "bold"), fg="#ffffff", bg="#8b5cf6", bd=0, padx=12, pady=4, command=self._add_instance_dialog)
        add_inst_btn.pack(side=tk.RIGHT)

        body = tk.Frame(self.root, bg="#0a0e1a")
        body.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        self.canvas = tk.Canvas(body, bg="#121829", bd=1, relief="solid", highlightbackground="#2a344e")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 15))

        self.inspector = tk.Frame(body, bg="#121829", width=280, bd=1, relief="solid", highlightbackground="#2a344e", padx=15, pady=15)
        self.inspector.pack(side=tk.RIGHT, fill=tk.Y)
        self.inspector.pack_propagate(False)

        tk.Label(self.inspector, text="🔍 USER INSPECTOR", font=("Consolas", 11, "bold"), fg="#8b5cf6", bg="#121829").pack(anchor="w", pady=(0, 10))

        self.user_lbl = tk.Label(self.inspector, text="Select a user node...", font=("Consolas", 10, "bold"), fg="#f3f4f6", bg="#121829")
        self.user_lbl.pack(anchor="w", pady=(0, 10))

        self.btn_block = tk.Button(self.inspector, text="⛔ Block Access", font=("Consolas", 9, "bold"), fg="#ffffff", bg="#b4182d", bd=0, padx=10, pady=6, command=self._toggle_block)
        self.btn_block.pack(fill=tk.X, pady=4)

        self.btn_maint = tk.Button(self.inspector, text="🛠️ Toggle Maintenance", font=("Consolas", 9, "bold"), fg="#ffffff", bg="#0a7075", bd=0, padx=10, pady=6, command=self._toggle_maintenance)
        self.btn_maint.pack(fill=tk.X, pady=4)

        self.btn_launch = tk.Button(self.inspector, text="🚀 Launch Instance", font=("Consolas", 9, "bold"), fg="#03131e", bg="#00f2fe", bd=0, padx=10, pady=6, command=self._launch_instance)
        self.btn_launch.pack(fill=tk.X, pady=4)

        self.btn_delete = tk.Button(self.inspector, text="🗑️ Delete Instance (7d)", font=("Consolas", 9, "bold"), fg="#ffffff", bg="#555555", bd=0, padx=10, pady=6, command=self._delete_instance)
        self.btn_delete.pack(fill=tk.X, pady=(15, 0))

        self._render_cloud()

    def _manual_sync(self):
        st_type, msg = run_github_sync(auto_push=True)
        if st_type == "pushed":
            messagebox.showinfo("GitHub Sync", f"✔ Success: {msg}")
        elif st_type == "newer_available":
            ans = messagebox.askyesno("Newer Version Detected", f"{msg}\n\nWould you like to pull the newest version from GitHub now?")
            if ans:
                subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=r"C:\Orbital", capture_output=True)
                messagebox.showinfo("Updated", "Orbital successfully updated to latest GitHub version!")
        elif st_type == "up_to_date":
            messagebox.showinfo("GitHub Sync", f"✔ Up-to-date: {msg}")
        else:
            messagebox.showwarning("Sync Warning", msg)

    def _render_cloud(self):
        self.canvas.delete("all")
        self.db = load_db()

        cx, cy = 300, 300
        self.canvas.create_oval(cx-30, cy-30, cx+30, cy+30, fill="#8b5cf6", outline="#a78bfa", width=2)
        self.canvas.create_text(cx, cy, text="GRAVITY\n(Admin)", font=("Consolas", 9, "bold"), fill="#ffffff")

        users = list(self.db.get("users", {}).keys())
        radius = 160
        for i, u in enumerate(users):
            angle = (2 * 3.14159 / max(len(users), 1)) * i
            ux = cx + int(radius * math.cos(angle))
            uy = cy + int(radius * math.sin(angle))

            st = self.db["users"][u].get("status", "active")
            col = "#10b981" if st == "active" else ("#0a7075" if st == "maintenance" else "#b4182d")

            self.canvas.create_line(cx, cy, ux, uy, fill="#2a344e", width=1)
            item = self.canvas.create_oval(ux-20, uy-20, ux+20, uy+20, fill=col, outline="#ffffff", width=1, tags=("node", u))
            self.canvas.create_text(ux, uy+30, text=u, font=("Consolas", 9, "bold"), fill="#f3f4f6")

            self.canvas.tag_bind(item, "<Button-1>", lambda e, name=u: self._select_user(name))

    def _select_user(self, username):
        self.selected_user = username
        u_data = self.db["users"].get(username, {})
        st = u_data.get("status", "active")
        self.user_lbl.config(text=f"User: {username}\nStatus: {st.upper()}\nContact: {u_data.get('contact', 'N/A')}")

    def _add_instance_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Add User Instance")
        dlg.geometry("380x240")
        dlg.configure(bg="#0a0e1a")

        tk.Label(dlg, text="➕ Provision New User Instance", font=("Consolas", 11, "bold"), fg="#8b5cf6", bg="#0a0e1a").pack(pady=10)

        tk.Label(dlg, text="Instance Username:", font=("Consolas", 9, "bold"), fg="#9ca3af", bg="#0a0e1a").pack(anchor="w", padx=20)
        u_entry = tk.Entry(dlg, font=("Consolas", 10), bg="#1c233d", fg="#ffffff")
        u_entry.pack(fill=tk.X, padx=20, pady=5)

        tk.Label(dlg, text="Instance Password:", font=("Consolas", 9, "bold"), fg="#9ca3af", bg="#0a0e1a").pack(anchor="w", padx=20)
        p_entry = tk.Entry(dlg, font=("Consolas", 10), bg="#1c233d", fg="#ffffff")
        p_entry.pack(fill=tk.X, padx=20, pady=5)

        def create_inst():
            u = u_entry.get().strip()
            p = p_entry.get().strip()
            if not u or not p: return
            self.db["users"][u] = {"username": u, "password": p, "status": "active", "created": datetime.datetime.now().isoformat()}
            save_db(self.db)
            os.makedirs(os.path.join(r"C:\Orbital\users", u), exist_ok=True)
            messagebox.showinfo("Instance Provisioned", f"User instance '{u}' created!")
            dlg.destroy()
            self._render_cloud()

        tk.Button(dlg, text="Provision Instance", font=("Consolas", 10, "bold"), fg="#ffffff", bg="#8b5cf6", bd=0, padx=12, pady=6, command=create_inst).pack(pady=15)

    def _toggle_block(self):
        if not self.selected_user: return
        st = self.db["users"][self.selected_user].get("status")
        self.db["users"][self.selected_user]["status"] = "active" if st == "blocked" else "blocked"
        save_db(self.db)
        self._select_user(self.selected_user)
        self._render_cloud()

    def _toggle_maintenance(self):
        if not self.selected_user: return
        st = self.db["users"][self.selected_user].get("status")
        self.db["users"][self.selected_user]["status"] = "active" if st == "maintenance" else "maintenance"
        save_db(self.db)
        self._select_user(self.selected_user)
        self._render_cloud()

    def _launch_instance(self):
        if not self.selected_user: return
        app_dir = os.path.dirname(os.path.abspath(__file__))
        target = os.path.join(app_dir, "orbital_navigator_gui.py")
        subprocess.Popen([sys.executable, target, self.selected_user])

    def _delete_instance(self):
        if not self.selected_user: return
        if self.selected_user == "Gravity":
            messagebox.showerror("Protected", "Gravity admin instance cannot be deleted.")
            return
        ans = messagebox.askyesno("Confirm Delete", f"Delete instance '{self.selected_user}' and place username on 7-day cooldown?")
        if ans:
            del self.db["users"][self.selected_user]
            self.db["cooldowns"][self.selected_user] = datetime.datetime.now().isoformat()
            save_db(self.db)
            self.selected_user = None
            self._render_cloud()

if __name__ == "__main__":
    root = tk.Tk()
    app = AdminCloudApp(root)
    root.mainloop()
