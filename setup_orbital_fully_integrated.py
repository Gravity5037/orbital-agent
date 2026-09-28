import os
import sys
import json
import re
import uuid
import tempfile
import shutil
import hashlib

def deploy_v31_authentication_matrix():
    print("=============================================================")
    print("  ORBITAL OS v31: STEALTH ADMIN & MULTI-IDENTIFIER AUTH      ")
    print("=============================================================")

    base_dir = r"C:\Orbital"
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok=True)

    # 1. Update Core Governance & User Validation Controller
    auth_controller_code = r'''import os
import json
import re
import hashlib
import uuid

USERS_DB_PATH = r"C:\Orbital\users\users_db.json"

def load_users_db():
    if not os.path.exists(USERS_DB_PATH):
        os.makedirs(os.path.dirname(USERS_DB_PATH), exist_ok=True)
        default_db = {
            "users": {
                "Gravity": {
                    "role": "admin",
                    "email": "admin@orbital.local",
                    "phone": "+10000000000",
                    "password_hash": hashlib.sha256("gravity_master_key".encode()).hexdigest(),
                    "email_validated": True,
                    "phone_validated": True,
                    "account_status": "active",
                    "permissions": ["all_access", "hive_override", "remote_inspect"],
                    "bound_hive_devices": ["MASTER-NODE-UUID"]
                }
            },
            "trusted_hive_nodes": ["MASTER-NODE-UUID"]
        }
        with open(USERS_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(default_db, f, indent=4)
        return default_db
    with open(USERS_DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users_db(db):
    with open(USERS_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4)

def mask_email(email):
    if "@" not in email:
        return email
    name, domain = email.split("@", 1)
    if len(name) <= 2:
        masked_name = name[0] + "*"
    else:
        masked_name = name[0] + "*" * (len(name) - 2) + name[-1]
    return f"{masked_name}@{domain}"

def mask_phone(phone):
    digits = re.sub(r"\D", "", phone)
    if len(digits) >= 4:
        return f"+* (***) ***-{digits[-4:]}"
    return "+* (***) ***-****"

def register_user(username, email, phone, password):
    db = load_users_db()
    users = db.get("users", {})
    
    # Check uniqueness
    for u, data in users.items():
        if u.lower() == username.lower():
            return False, "Username already registered."
        if data.get("email", "").lower() == email.lower():
            return False, "Email already registered."
        if data.get("phone") == phone:
            return False, "Phone number already registered."

    pass_hash = hashlib.sha256(password.encode()).hexdigest()
    email_token = str(uuid.uuid4())[:8]
    phone_code = str(uuid.uuid4())[:6].upper()

    users[username] = {
        "role": "user",
        "email": email,
        "phone": phone,
        "password_hash": pass_hash,
        "email_validated": False,
        "phone_validated": False,
        "email_token": email_token,
        "phone_code": phone_code,
        "account_status": "pending_verification",
        "permissions": ["isolated_workspace"],
        "bound_hive_devices": []
    }
    db["users"] = users
    save_users_db(db)
    
    print(f"[📡 VALIDATION LINK SENT] Email to {mask_email(email)} | Link Token: {email_token}")
    print(f"[📱 VALIDATION CODE SENT] SMS to {mask_phone(phone)} | Code: {phone_code}")
    return True, f"Validation link sent to {mask_email(email)} and code texted to {mask_phone(phone)}."

def validate_user_account(username_or_email, email_token, phone_code):
    db = load_users_db()
    users = db.get("users", {})
    
    target_user = None
    target_data = None
    for u, data in users.items():
        if u.lower() == username_or_email.lower() or data.get("email", "").lower() == username_or_email.lower():
            target_user = u
            target_data = data
            break

    if not target_user:
        return False, "User account not found."

    if target_data.get("email_token") == email_token:
        target_data["email_validated"] = True
    if target_data.get("phone_code") == phone_code:
        target_data["phone_validated"] = True

    if target_data["email_validated"] and target_data["phone_validated"]:
        target_data["account_status"] = "active"
        save_users_db(db)
        return True, "Account fully validated & activated!"
    
    save_users_db(db)
    return False, "Partial validation complete. Both Email link and SMS code are required."

def authenticate_user(identifier, password):
    db = load_users_db()
    users = db.get("users", {})
    pass_hash = hashlib.sha256(password.encode()).hexdigest()

    for u, data in users.items():
        # Match by Username, Email, OR Phone Number
        if identifier.lower() in [u.lower(), data.get("email", "").lower(), data.get("phone", "")]:
            if data.get("password_hash") == pass_hash:
                if data.get("account_status") == "pending_verification":
                    return False, "Account pending verification. Please validate Email & Phone first.", None
                if data.get("account_status") == "blocked":
                    return False, "Account has been suspended by Admin Governance.", None
                return True, "Authentication Successful", {
                    "username": u,
                    "role": data.get("role"),
                    "data": data
                }
    return False, "Invalid Credentials", None

def handle_forgot_password(identifier):
    db = load_users_db()
    users = db.get("users", {})

    for u, data in users.items():
        if identifier.lower() in [u.lower(), data.get("email", "").lower(), data.get("phone", "")]:
            m_email = mask_email(data.get("email", ""))
            m_phone = mask_phone(data.get("phone", ""))
            print(f"[🔒 PASSWORD RESET LINK DISPATCHED] Link sent to {m_email} and SMS sent to {m_phone}")
            return True, f"An Email was sent to {m_email} and SMS sent to {m_phone}. Check your inbox."

    # Privacy-preserving generic response
    return True, "If an account matches that identifier, password reset instructions have been sent."
'''

    os.makedirs(os.path.join(base_dir, "core"), exist_ok=True)
    with open(os.path.join(base_dir, "core", "auth_controller.py"), "w", encoding="utf-8") as f:
        f.write(auth_controller_code)
    print("  [✔] Auth Controller deployed to C:\Orbital\core\auth_controller.py")

    # 2. Update Stealth Login & Registration GUI
    login_gui_code = r'''import sys
import os
import tkinter as tk
from tkinter import messagebox, ttk

sys.path.append(r"C:\Orbital\core")
try:
    from auth_controller import authenticate_user, register_user, validate_user_account, handle_forgot_password
except ImportError:
    pass

class OrbitalStealthLoginApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Orbital OS Gateway")
        self.root.geometry("460x560")
        self.root.configure(bg="#0B0E14")
        self.root.resizable(False, False)

        self.build_login_screen()

    def clear_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def build_login_screen(self):
        self.clear_screen()

        # Header Title & Stealth Hotkey Listener (Ctrl+Shift+A or Double-Click Logo)
        header_frame = tk.Frame(self.root, bg="#0B0E14")
        header_frame.pack(fill="x", pady=20)

        logo_label = tk.Label(
            header_frame, text="🛸 ORBITAL OS", font=("Consolas", 22, "bold"),
            fg="#00E5FF", bg="#0B0E14", cursor="hand2"
        )
        logo_label.pack()
        logo_label.bind("<Double-Button-1>", self.trigger_stealth_admin_modal)

        # Login Form Frame
        form_frame = tk.Frame(self.root, bg="#151A23", padx=25, pady=25)
        form_frame.pack(fill="both", expand=True, padx=20, pady=10)

        tk.Label(form_frame, text="Identifier (Username / Email / Phone)", font=("Segoe UI", 9, "bold"), fg="#A0AEC0", bg="#151A23").pack(anchor="w", pady=(5,2))
        self.ident_entry = tk.Entry(form_frame, font=("Segoe UI", 11), bg="#0B0E14", fg="#FFFFFF", insertbackground="#00E5FF", bd=1, relief="solid")
        self.ident_entry.pack(fill="x", pady=(0, 15), ipady=4)

        tk.Label(form_frame, text="Password", font=("Segoe UI", 9, "bold"), fg="#A0AEC0", bg="#151A23").pack(anchor="w", pady=(5,2))
        self.pass_entry = tk.Entry(form_frame, show="•", font=("Segoe UI", 11), bg="#0B0E14", fg="#FFFFFF", insertbackground="#00E5FF", bd=1, relief="solid")
        self.pass_entry.pack(fill="x", pady=(0, 15), ipady=4)

        # Hotkey Binding: Ctrl+Shift+A opens Stealth Admin
        self.root.bind("<Control-Shift-A>", lambda e: self.trigger_stealth_admin_modal())
        self.root.bind("<Control-shift-A>", lambda e: self.trigger_stealth_admin_modal())

        # Buttons
        login_btn = tk.Button(
            form_frame, text="LOG IN", font=("Segoe UI", 11, "bold"),
            bg="#00E5FF", fg="#0B0E14", activebackground="#00B8D4", activeforeground="#0B0E14",
            bd=0, cursor="hand2", command=self.handle_login
        )
        login_btn.pack(fill="x", pady=(10, 10), ipady=5)

        forgot_btn = tk.Label(
            form_frame, text="Forgot Password?", font=("Segoe UI", 9, "underline"),
            fg="#00E5FF", bg="#151A23", cursor="hand2"
        )
        forgot_btn.pack(pady=5)
        forgot_btn.bind("<Button-1>", lambda e: self.build_forgot_password_modal())

        # Footer Navigation
        footer_frame = tk.Frame(self.root, bg="#0B0E14")
        footer_frame.pack(fill="x", pady=15)

        tk.Label(footer_frame, text="New to Orbital?", font=("Segoe UI", 9), fg="#7E8B9B", bg="#0B0E14").pack(side="left", padx=(80, 5))
        create_btn = tk.Label(footer_frame, text="Create an Account", font=("Segoe UI", 9, "bold"), fg="#00E5FF", bg="#0B0E14", cursor="hand2")
        create_btn.pack(side="left")
        create_btn.bind("<Button-1>", lambda e: self.build_register_screen())

    def handle_login(self):
        ident = self.ident_entry.get().strip()
        pwd = self.pass_entry.get().strip()

        if not ident or not pwd:
            messagebox.showwarning("Incomplete Form", "Please enter your identifier and password.")
            return

        success, msg, user_obj = authenticate_user(ident, pwd)
        if success:
            role = user_obj["role"]
            uname = user_obj["username"]
            messagebox.showinfo("Access Granted", f"Welcome back to Orbital, {uname}! [{role.upper()} MODE]")
            self.root.destroy()
        else:
            messagebox.showerror("Authentication Failed", msg)

    def trigger_stealth_admin_modal(self, event=None):
        modal = tk.Toplevel(self.root)
        modal.title("Master Governance Authentication")
        modal.geometry("380x260")
        modal.configure(bg="#0B0E14")
        modal.grab_set()

        tk.Label(modal, text="👑 STEALTH ADMIN ACCESS", font=("Consolas", 12, "bold"), fg="#FFD700", bg="#0B0E14").pack(pady=15)
        tk.Label(modal, text="Enter Master Governance Security Key:", font=("Segoe UI", 9), fg="#A0AEC0", bg="#0B0E14").pack(pady=5)

        admin_key_entry = tk.Entry(modal, show="•", font=("Segoe UI", 11), bg="#151A23", fg="#FFD700", insertbackground="#FFD700")
        admin_key_entry.pack(fill="x", padx=30, pady=10, ipady=4)

        def verify_admin_key():
            key = admin_key_entry.get().strip()
            success, msg, user_obj = authenticate_user("Gravity", key)
            if success:
                messagebox.showinfo("Master Admin Override", "Gravity Master Admin Session Unlocked.")
                modal.destroy()
                self.root.destroy()
            else:
                messagebox.showerror("Access Denied", "Invalid Master Administrative Security Key.")

        tk.Button(modal, text="UNLOCK ADMIN HIVE", font=("Segoe UI", 10, "bold"), bg="#FFD700", fg="#0B0E14", bd=0, command=verify_admin_key).pack(fill="x", padx=30, pady=15, ipady=4)

    def build_register_screen(self):
        self.clear_screen()

        tk.Label(self.root, text="🛸 CREATE USER ACCOUNT", font=("Consolas", 16, "bold"), fg="#00E5FF", bg="#0B0E14").pack(pady=15)

        form_frame = tk.Frame(self.root, bg="#151A23", padx=20, pady=20)
        form_frame.pack(fill="both", expand=True, padx=20, pady=5)

        tk.Label(form_frame, text="Username", font=("Segoe UI", 8, "bold"), fg="#A0AEC0", bg="#151A23").pack(anchor="w")
        u_entry = tk.Entry(form_frame, font=("Segoe UI", 10), bg="#0B0E14", fg="#FFF", insertbackground="#00E5FF")
        u_entry.pack(fill="x", pady=(0, 8))

        tk.Label(form_frame, text="Email Address", font=("Segoe UI", 8, "bold"), fg="#A0AEC0", bg="#151A23").pack(anchor="w")
        e_entry = tk.Entry(form_frame, font=("Segoe UI", 10), bg="#0B0E14", fg="#FFF", insertbackground="#00E5FF")
        e_entry.pack(fill="x", pady=(0, 8))

        tk.Label(form_frame, text="Phone Number", font=("Segoe UI", 8, "bold"), fg="#A0AEC0", bg="#151A23").pack(anchor="w")
        p_entry = tk.Entry(form_frame, font=("Segoe UI", 10), bg="#0B0E14", fg="#FFF", insertbackground="#00E5FF")
        p_entry.pack(fill="x", pady=(0, 8))

        tk.Label(form_frame, text="Password", font=("Segoe UI", 8, "bold"), fg="#A0AEC0", bg="#151A23").pack(anchor="w")
        pass_entry = tk.Entry(form_frame, show="•", font=("Segoe UI", 10), bg="#0B0E14", fg="#FFF", insertbackground="#00E5FF")
        pass_entry.pack(fill="x", pady=(0, 15))

        def submit_registration():
            u, e, p, pwd = u_entry.get().strip(), e_entry.get().strip(), p_entry.get().strip(), pass_entry.get().strip()
            if not all([u, e, p, pwd]):
                messagebox.showwarning("Missing Information", "All fields are required to register.")
                return
            ok, msg = register_user(u, e, p, pwd)
            if ok:
                messagebox.showinfo("Verification Sent", msg)
                self.build_validation_modal(u)
            else:
                messagebox.showerror("Registration Error", msg)

        tk.Button(form_frame, text="REGISTER ACCOUNT", font=("Segoe UI", 10, "bold"), bg="#00E5FF", fg="#0B0E14", bd=0, command=submit_registration).pack(fill="x", ipady=4)

        back_btn = tk.Label(self.root, text="← Back to Login", font=("Segoe UI", 9, "underline"), fg="#7E8B9B", bg="#0B0E14", cursor="hand2")
        back_btn.pack(pady=10)
        back_btn.bind("<Button-1>", lambda e: self.build_login_screen())

    def build_validation_modal(self, username):
        modal = tk.Toplevel(self.root)
        modal.title("Account Verification")
        modal.geometry("400x320")
        modal.configure(bg="#0B0E14")
        modal.grab_set()

        tk.Label(modal, text="📩 VALIDATE EMAIL & SMS", font=("Consolas", 12, "bold"), fg="#00E5FF", bg="#0B0E14").pack(pady=10)
        tk.Label(modal, text=f"Account: {username}", font=("Segoe UI", 9), fg="#A0AEC0", bg="#0B0E14").pack()

        tk.Label(modal, text="Email Validation Token (from link):", font=("Segoe UI", 8, "bold"), fg="#A0AEC0", bg="#0B0E14").pack(anchor="w", padx=20, pady=(10,2))
        e_tok = tk.Entry(modal, font=("Segoe UI", 10), bg="#151A23", fg="#FFF", insertbackground="#00E5FF")
        e_tok.pack(fill="x", padx=20, pady=(0, 8))

        tk.Label(modal, text="SMS Verification Code (texted to phone):", font=("Segoe UI", 8, "bold"), fg="#A0AEC0", bg="#0B0E14").pack(anchor="w", padx=20, pady=(5,2))
        p_code = tk.Entry(modal, font=("Segoe UI", 10), bg="#151A23", fg="#FFF", insertbackground="#00E5FF")
        p_code.pack(fill="x", padx=20, pady=(0, 15))

        def verify_tokens():
            ok, msg = validate_user_account(username, e_tok.get().strip(), p_code.get().strip())
            if ok:
                messagebox.showinfo("Account Activated", msg)
                modal.destroy()
                self.build_login_screen()
            else:
                messagebox.showwarning("Validation Pending", msg)

        tk.Button(modal, text="VERIFY & ACTIVATE", font=("Segoe UI", 10, "bold"), bg="#00E5FF", fg="#0B0E14", bd=0, command=verify_tokens).pack(fill="x", padx=20, ipady=4)

    def build_forgot_password_modal(self):
        modal = tk.Toplevel(self.root)
        modal.title("Password Recovery")
        modal.geometry("380x240")
        modal.configure(bg="#0B0E14")
        modal.grab_set()

        tk.Label(modal, text="🔑 FORGOT PASSWORD", font=("Consolas", 12, "bold"), fg="#00E5FF", bg="#0B0E14").pack(pady=15)
        tk.Label(modal, text="Enter your Username, Email, or Phone:", font=("Segoe UI", 9), fg="#A0AEC0", bg="#0B0E14").pack(pady=2)

        id_entry = tk.Entry(modal, font=("Segoe UI", 10), bg="#151A23", fg="#FFF", insertbackground="#00E5FF")
        id_entry.pack(fill="x", padx=25, pady=10, ipady=4)

        def dispatch_reset():
            ident = id_entry.get().strip()
            if not ident:
                messagebox.showwarning("Input Required", "Please enter your account identifier.")
                return
            ok, msg = handle_forgot_password(ident)
            messagebox.showinfo("Instructions Sent", msg)
            modal.destroy()

        tk.Button(modal, text="SEND RESET LINK", font=("Segoe UI", 10, "bold"), bg="#00E5FF", fg="#0B0E14", bd=0, command=dispatch_reset).pack(fill="x", padx=25, pady=10, ipady=4)

if __name__ == "__main__":
    root = tk.Tk()
    app = OrbitalStealthLoginApp(root)
    root.mainloop()
'''

    os.makedirs(os.path.join(base_dir, "gui"), exist_ok=True)
    with open(os.path.join(base_dir, "gui", "orbital_login_gui.py"), "w", encoding="utf-8") as f:
        f.write(login_gui_code)
    print("  [✔] Stealth Login GUI deployed to C:\Orbital\gui\orbital_login_gui.py")

    print("=============================================================")
    print("   [✔] v31 STEALTH AUTHENTICATION DEPLOYMENT COMPLETE!       ")
    print("   - Admin login concealed under Login screen.               ")
    print("   - Multi-identifier login active (Email / Phone / Username)")
    print("   - Privacy-preserving Forgot Password masking deployed.   ")
    print("=============================================================")

if __name__ == "__main__":
    deploy_v31_authentication_matrix()
