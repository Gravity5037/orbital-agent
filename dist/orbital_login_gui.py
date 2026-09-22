import os
import sys
import json
import datetime
import re
import random
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

DB_PATH = r"C:\Orbital\users_db.json"
ADMIN_USER = "Gravity"
ADMIN_PASS = "Toolongdong!3"

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
                if "users" not in db or not isinstance(db["users"], dict): db["users"] = {}
                if "cooldowns" not in db or not isinstance(db["cooldowns"], dict): db["cooldowns"] = {}
                return db
        except Exception:
            pass
    db = {"users": {}, "cooldowns": {}}
    save_db(db)
    return db

def save_db(db):
    if "users" not in db or not isinstance(db["users"], dict): db["users"] = {}
    if "cooldowns" not in db or not isinstance(db["cooldowns"], dict): db["cooldowns"] = {}
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4)

def validate_password_policy(passcode):
    if len(passcode) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", passcode):
        return False, "Password must contain at least 1 uppercase letter (A-Z)."
    if not re.search(r"[a-z]", passcode):
        return False, "Password must contain at least 1 lowercase letter (a-z)."
    if not re.search(r"[0-9]", passcode):
        return False, "Password must contain at least 1 number (0-9)."
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", passcode):
        return False, "Password must contain at least 1 special character."
    return True, "Valid"

def check_username_available(username, db):
    if username.lower() == ADMIN_USER.lower():
        return False, f"Username '{username}' is reserved for System Administrator."
    if username in db.get("users", {}):
        return False, f"Username '{username}' is already taken."
    if username in db.get("cooldowns", {}):
        deact_date_str = db["cooldowns"][username]
        try:
            deact_date = datetime.datetime.fromisoformat(deact_date_str)
            days_passed = (datetime.datetime.now() - deact_date).days
            if days_passed < 7:
                remaining = 7 - days_passed
                return False, f"Username '{username}' was recently deactivated. Reserved for {remaining} more day(s)."
            else:
                del db["cooldowns"][username]
                save_db(db)
        except Exception:
            pass
    return True, "Available"

class WatermarkEntry(tk.Entry):
    def __init__(self, master, placeholder="", is_password=False, palette=None, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.placeholder = placeholder
        self.is_password = is_password
        self.palette = palette or PALETTES["Midnight Dream"]
        self.is_showing_placeholder = False

        self.bind("<FocusIn>", self._clear_placeholder)
        self.bind("<FocusOut>", self._show_placeholder)
        self._show_placeholder()

    def _show_placeholder(self, event=None):
        if not self.get():
            self.is_showing_placeholder = True
            self.config(fg=self.palette["muted"])
            if self.is_password:
                self.config(show="")
            self.delete(0, tk.END)
            self.insert(0, self.placeholder)

    def _clear_placeholder(self, event=None):
        if self.is_showing_placeholder:
            self.is_showing_placeholder = False
            self.delete(0, tk.END)
            self.config(fg=self.palette["text"])
            if self.is_password:
                self.config(show="*")

    def get_real_value(self):
        if self.is_showing_placeholder:
            return ""
        return self.get().strip()

class OrbitalAuthApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Orbital Identity Gateway")
        self.root.geometry("680x600")
        self.root.resizable(False, False)

        self.db = load_db()
        self.theme_name = "Midnight Dream"
        self.palette = PALETTES[self.theme_name]
        self.mode = "login"

        self._build_ui()
        self._animate_bg()

    def _build_ui(self):
        self.root.configure(bg=self.palette["bg"])

        self.canvas = tk.Canvas(self.root, bg=self.palette["bg"], bd=0, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.top_bar = tk.Frame(self.canvas, bg=self.palette["bg"])
        self.top_bar.place(x=20, y=15, width=640, height=35)

        title_top = tk.Label(self.top_bar, text="🛸 ORBITAL OS IDENTITY GATEWAY", font=("Consolas", 11, "bold"), fg=self.palette["accent"], bg=self.palette["bg"])
        title_top.pack(side=tk.LEFT)

        self.theme_btn = tk.Button(self.top_bar, text=f"🎨 Theme: {self.theme_name}", font=("Consolas", 9, "bold"), fg=self.palette["btn_text"], bg=self.palette["accent"], bd=0, padx=10, pady=3, command=self.cycle_theme)
        self.theme_btn.pack(side=tk.RIGHT)

        self.card = tk.Frame(self.canvas, bg=self.palette["card"], bd=1, relief="solid", highlightbackground=self.palette["border"], highlightthickness=1)
        self.card.place(relx=0.5, rely=0.53, width=560, height=480, anchor="center")

        self.form_frame = tk.Frame(self.card, bg=self.palette["card"])
        self.form_frame.place(x=30, y=20, width=500, height=440)

        self.title_lbl = tk.Label(self.form_frame, text="Orbital OS Access", font=("Consolas", 16, "bold"), fg=self.palette["text"], bg=self.palette["card"])
        self.title_lbl.pack(anchor="w", pady=(5, 12))

        tab_frame = tk.Frame(self.form_frame, bg=self.palette["card"])
        tab_frame.pack(anchor="w", pady=(0, 15))

        self.login_tab_btn = tk.Button(tab_frame, text="Sign In", font=("Consolas", 10, "bold"), fg=self.palette["btn_text"], bg=self.palette["accent"], bd=0, padx=16, pady=5, command=lambda: self.switch_mode("login"))
        self.login_tab_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.signup_tab_btn = tk.Button(tab_frame, text="Sign Up", font=("Consolas", 10, "bold"), fg=self.palette["text"], bg=self.palette["entry_bg"], bd=0, padx=16, pady=5, command=lambda: self.switch_mode("signup"))
        self.signup_tab_btn.pack(side=tk.LEFT)

        tk.Label(self.form_frame, text="Username", font=("Consolas", 9, "bold"), fg=self.palette["muted"], bg=self.palette["card"]).pack(anchor="w")
        self.user_entry = WatermarkEntry(self.form_frame, placeholder="Enter Username", palette=self.palette, font=("Consolas", 11), bg=self.palette["entry_bg"], bd=0, highlightthickness=1, highlightbackground=self.palette["border"])
        self.user_entry.pack(fill=tk.X, pady=(2, 10), ipady=6)

        self.contact_label = tk.Label(self.form_frame, text="Email or Phone", font=("Consolas", 9, "bold"), fg=self.palette["muted"], bg=self.palette["card"])
        self.contact_entry = WatermarkEntry(self.form_frame, placeholder="Enter Email or Phone Number", palette=self.palette, font=("Consolas", 11), bg=self.palette["entry_bg"], bd=0, highlightthickness=1, highlightbackground=self.palette["border"])

        tk.Label(self.form_frame, text="Password", font=("Consolas", 9, "bold"), fg=self.palette["muted"], bg=self.palette["card"]).pack(anchor="w")
        self.pass_entry = WatermarkEntry(self.form_frame, placeholder="Enter Password", is_password=True, palette=self.palette, font=("Consolas", 11), bg=self.palette["entry_bg"], bd=0, highlightthickness=1, highlightbackground=self.palette["border"])
        self.pass_entry.pack(fill=tk.X, pady=(2, 12), ipady=6)

        self.terms_var = tk.BooleanVar(value=True)
        self.terms_check = tk.Checkbutton(self.form_frame, text="Agree to Terms & Policy", variable=self.terms_var, font=("Consolas", 9), fg=self.palette["muted"], bg=self.palette["card"], selectcolor=self.palette["card"], activebackground=self.palette["card"])
        self.terms_check.pack(anchor="w", pady=(0, 12))

        btn_frame = tk.Frame(self.form_frame, bg=self.palette["card"])
        btn_frame.pack(fill=tk.X, pady=(5, 0))

        self.submit_btn = tk.Button(btn_frame, text="Sign In ➔", font=("Consolas", 11, "bold"), fg=self.palette["btn_text"], bg=self.palette["accent"], bd=0, padx=20, pady=8, command=self.submit)
        self.submit_btn.pack(side=tk.LEFT)

        self.pass_entry.bind("<Return>", lambda e: self.submit())

        self.stars = []
        for _ in range(25):
            x = random.randint(10, 670)
            y = random.randint(10, 590)
            r = random.randint(1, 3)
            self.stars.append({"x": x, "y": y, "r": r, "dx": random.choice([-1, 1]) * 0.3, "dy": random.choice([-1, 1]) * 0.3})

    def cycle_theme(self):
        names = list(PALETTES.keys())
        idx = (names.index(self.theme_name) + 1) % len(names)
        self.theme_name = names[idx]
        self.palette = PALETTES[self.theme_name]

        self.root.configure(bg=self.palette["bg"])
        self.canvas.configure(bg=self.palette["bg"])
        self.top_bar.configure(bg=self.palette["bg"])
        self.theme_btn.configure(text=f"🎨 Theme: {self.theme_name}", bg=self.palette["accent"], fg=self.palette["btn_text"])
        self.card.configure(bg=self.palette["card"], highlightbackground=self.palette["border"])
        self.form_frame.configure(bg=self.palette["card"])
        self.title_lbl.configure(bg=self.palette["card"], fg=self.palette["text"])
        self.user_entry.config(bg=self.palette["entry_bg"], fg=self.palette["text"], highlightbackground=self.palette["border"])
        self.contact_entry.config(bg=self.palette["entry_bg"], fg=self.palette["text"], highlightbackground=self.palette["border"])
        self.pass_entry.config(bg=self.palette["entry_bg"], fg=self.palette["text"], highlightbackground=self.palette["border"])
        self.terms_check.config(bg=self.palette["card"], fg=self.palette["muted"], selectcolor=self.palette["card"])

        self.switch_mode(self.mode)

    def _animate_bg(self):
        self.canvas.delete("star")
        for s in self.stars:
            s["x"] += s["dx"]
            s["y"] += s["dy"]
            if s["x"] < 0 or s["x"] > 680: s["dx"] *= -1
            if s["y"] < 0 or s["y"] > 600: s["dy"] *= -1
            self.canvas.create_oval(s["x"]-s["r"], s["y"]-s["r"], s["x"]+s["r"], s["y"]+s["r"], fill=self.palette["accent_glow"], outline="", tags="star")
        self.root.after(80, self._animate_bg)

    def switch_mode(self, mode):
        self.mode = mode
        if mode == "login":
            self.title_lbl.config(text="Orbital OS Access")
            self.login_tab_btn.config(bg=self.palette["accent"], fg=self.palette["btn_text"])
            self.signup_tab_btn.config(bg=self.palette["entry_bg"], fg=self.palette["text"])
            self.contact_label.pack_forget()
            self.contact_entry.pack_forget()
            self.submit_btn.config(text="Sign In ➔")
        else:
            self.title_lbl.config(text="Create Account")
            self.login_tab_btn.config(bg=self.palette["entry_bg"], fg=self.palette["text"])
            self.signup_tab_btn.config(bg=self.palette["accent"], fg=self.palette["btn_text"])
            self.contact_label.pack(anchor="w")
            self.contact_entry.pack(fill=tk.X, pady=(2, 10), ipady=6)
            self.submit_btn.config(text="Sign Up ➔")

    def submit(self):
        username = self.user_entry.get_real_value()
        passcode = self.pass_entry.get_real_value()
        contact = self.contact_entry.get_real_value()

        if not username or not passcode:
            messagebox.showwarning("Input Required", "Please enter both username and password.")
            return

        if self.mode == "login":
            if username == ADMIN_USER and passcode == ADMIN_PASS:
                messagebox.showinfo("Admin Authenticated", "Welcome, System Administrator Gravity!")
                self.root.destroy()
                self._launch_admin_cloud()
                return

            if username not in self.db.get("users", {}):
                messagebox.showerror("Auth Error", f"Account '{username}' not found. Please sign up first.")
                return

            user_data = self.db["users"][username]
            if user_data.get("status") == "blocked":
                messagebox.showerror("Access Blocked", f"Account '{username}' has been blocked by Administrator.")
                return

            if user_data.get("status") == "maintenance":
                ans = messagebox.askyesno("Maintenance Mode", f"Account '{username}' is currently in maintenance mode.\n\nDo you want to run system diagnostics and exit maintenance mode now?")
                if ans:
                    user_data["status"] = "active"
                    save_db(self.db)
                    messagebox.showinfo("Restored", f"Account '{username}' restored to Active status!")
                else:
                    return

            if user_data.get("password") == passcode:
                messagebox.showinfo("Login Success", f"Welcome back, {username}!")
                self.root.destroy()
                self._launch_user_navigator(username, is_new=False)
            else:
                messagebox.showerror("Auth Error", "Incorrect password.")

        else:
            if not self.terms_var.get():
                messagebox.showwarning("Policy Terms", "You must agree to the Terms & Policy to register.")
                return

            avail, msg = check_username_available(username, self.db)
            if not avail:
                messagebox.showerror("Username Reserved", msg)
                return

            valid_p, p_msg = validate_password_policy(passcode)
            if not valid_p:
                messagebox.showerror("Security Policy", p_msg)
                return

            self.db["users"][username] = {
                "username": username,
                "password": passcode,
                "contact": contact or "N/A",
                "created": datetime.datetime.now().isoformat(),
                "status": "active",
                "theme": self.theme_name,
                "abilities": ["Nucleus AI", "Vision Camera", "Mesh Gateway", "Spatial CSI"],
                "music_app": "Spotify"
            }
            save_db(self.db)

            user_dir = os.path.join(r"C:\Orbital\users", username)
            os.makedirs(user_dir, exist_ok=True)

            messagebox.showinfo("Account Created", f"Account '{username}' created successfully!\nLaunching Onboarding Wizard...")
            self.root.destroy()
            self._launch_user_navigator(username, is_new=True)

    def _launch_admin_cloud(self):
        app_dir = os.path.dirname(os.path.abspath(__file__))
        target = os.path.join(app_dir, "orbital_admin_cloud_gui.py")
        subprocess.Popen([sys.executable, target])

    def _launch_user_navigator(self, username, is_new=False):
        app_dir = os.path.dirname(os.path.abspath(__file__))
        target = os.path.join(app_dir, "orbital_navigator_gui.py")
        cmd = [sys.executable, target, username]
        if is_new:
            cmd.append("--onboard")
        subprocess.Popen(cmd)

if __name__ == "__main__":
    root = tk.Tk()
    app = OrbitalAuthApp(root)
    root.mainloop()
