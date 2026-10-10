import os
import sys
import json
import datetime
import math
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

DB_PATH = r"C:\Orbital\users_db.json"

try:
    sys.path.append(r"C:\Orbital\core")
    from cloud_hive_adapter import hive_adapter
except Exception:
    hive_adapter = None

def load_db():
    if hive_adapter:
        return hive_adapter.load_users_db()
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
    if hive_adapter:
        hive_adapter.save_users_db(db)
        return
    if "users" not in db: db["users"] = {}
    if "cooldowns" not in db: db["cooldowns"] = {}
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4)

class AdminCloudApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Orbital Admin Spatial Cloud - Gravity Control Matrix")
        self.root.geometry("960x680")
        self.root.configure(bg="#0a0e1a")

        self.db = load_db()
        self.selected_user = None

        self._build_ui()

    def _build_ui(self):
        top_bar = tk.Frame(self.root, bg="#0a0e1a", pady=10, padx=15)
        top_bar.pack(fill=tk.X)

        lbl = tk.Label(top_bar, text="⚡ ORBITAL ADMIN CLOUD MATRIX // GRAVITY CORE", font=("Consolas", 12, "bold"), fg="#8b5cf6", bg="#0a0e1a")
        lbl.pack(side=tk.LEFT)

        sync_btn = tk.Button(top_bar, text="🔄 Sync GitHub", font=("Consolas", 9, "bold"), fg="#ffffff", bg="#38bdf8", bd=0, padx=12, pady=4, command=self._sync_github)
        sync_btn.pack(side=tk.RIGHT, padx=(10, 0))

        add_inst_btn = tk.Button(top_bar, text="➕ Add User Instance", font=("Consolas", 9, "bold"), fg="#ffffff", bg="#8b5cf6", bd=0, padx=12, pady=4, command=self._add_instance_dialog)
        add_inst_btn.pack(side=tk.RIGHT, padx=(10, 0))

        ws_btn = tk.Button(top_bar, text="🚀 Launch Gravity Workstation", font=("Consolas", 9, "bold"), fg="#03131e", bg="#00f2fe", bd=0, padx=12, pady=4, command=self._launch_gravity_workstation)
        ws_btn.pack(side=tk.RIGHT)

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

    def _launch_gravity_workstation(self):
        app_dir = os.path.dirname(os.path.abspath(__file__))
        target = os.path.join(app_dir, "orbital_navigator_gui.py")
        if not os.path.exists(target):
            target = os.path.join(r"C:\Orbital\gui", "orbital_navigator_gui.py")
        creationflags = 0x08000000 if sys.platform == "win32" else 0
        pyw = sys.executable.replace("python.exe", "pythonw.exe")
        cmd = [pyw if os.path.exists(pyw) else sys.executable, target, "Gravity"]
        subprocess.Popen(cmd, creationflags=creationflags, cwd=r"C:\Orbital")

    def _sync_github(self):
        try:
            res = subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=r"C:\Orbital", capture_output=True, text=True)
            if "Already up to date" in res.stdout:
                messagebox.showinfo("GitHub Sync", "Orbital is fully up-to-date with GitHub!")
            else:
                messagebox.showinfo("GitHub Sync Success", f"Updated from GitHub:\n\n{res.stdout}")
        except Exception as e:
            messagebox.showerror("Sync Error", f"Git sync failed: {e}")

    def _render_cloud(self):
        self.canvas.delete("all")
        self.db = load_db()

        cx, cy = 300, 300
        c_adm = self.canvas.create_oval(cx-30, cy-30, cx+30, cy+30, fill="#8b5cf6", outline="#a78bfa", width=2, tags=("admin_node", "Gravity"))
        t_adm = self.canvas.create_text(cx, cy, text="GRAVITY\n(Admin)", font=("Consolas", 9, "bold"), fill="#ffffff", tags=("admin_node", "Gravity"))
        self.canvas.tag_bind(c_adm, "<Button-1>", lambda e: self._select_user("Gravity"))
        self.canvas.tag_bind(t_adm, "<Button-1>", lambda e: self._select_user("Gravity"))

        users = [u for u in self.db.get("users", {}).keys() if u != "Gravity"]
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
        if username == "Gravity":
            self.user_lbl.config(text="User: Gravity (Master Administrator)\nStatus: ACTIVE (Elevated)\nRole: System Administrator")
            self.btn_block.config(state="disabled")
            self.btn_maint.config(state="disabled")
            self.btn_delete.config(state="disabled")
            return
        self.btn_block.config(state="normal")
        self.btn_maint.config(state="normal")
        self.btn_delete.config(state="normal")
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
            u_dir = os.path.join(r"C:\Orbital\users", u)
            os.makedirs(os.path.join(u_dir, "inbox"), exist_ok=True)
            os.makedirs(os.path.join(u_dir, "transfers"), exist_ok=True)

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
        if not os.path.exists(target):
            target = os.path.join(r"C:\Orbital\gui", "orbital_navigator_gui.py")
        creationflags = 0x08000000 if sys.platform == "win32" else 0
        pyw = sys.executable.replace("python.exe", "pythonw.exe")
        cmd = [pyw if os.path.exists(pyw) else sys.executable, target, self.selected_user]
        subprocess.Popen(cmd, creationflags=creationflags, cwd=r"C:\Orbital")

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
