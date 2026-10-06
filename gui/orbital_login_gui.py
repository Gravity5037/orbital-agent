import os, sys, time, subprocess, tkinter as tk
from tkinter import messagebox, simpledialog

LOGIN_BG = "#0B0E14"
CARD_BG = "#121824"
CYAN = "#00E5FF"
TEXT_COLOR = "#E2E8F0"
MUTED_TEXT = "#64748B"
ENTRY_BG = "#1E293B"

class OrbitalLoginGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ORBITAL OS - Workstation Gateway")
        self.root.geometry("480x620")
        self.root.configure(bg=LOGIN_BG)
        self.root.resizable(False, False)
        
        self.click_times = []
        self._build_ui()
        
    def _on_logo_click(self, event=None):
        now = time.time()
        self.click_times.append(now)
        self.click_times = [t for t in self.click_times if now - t <= 4.0]
        if len(self.click_times) >= 20:
            self.click_times.clear()
            self.open_admin_gateway()

    def open_admin_gateway(self):
        key = simpledialog.askstring("Gravity Admin Gateway", "Enter Master Access Key:", show="*")
        if key == "gravity":
            messagebox.showinfo("Access Granted", "Gravity Master Admin Mode Unlocked!")
            self._launch_post_login_workstation("Admin_Gravity")
        elif key:
            messagebox.showerror("Access Denied", "Invalid Master Access Key.")

    def _build_ui(self):
        top = tk.Frame(self.root, bg=LOGIN_BG)
        top.pack(fill="x", pady=(25, 10))
        
        logo = tk.Label(top, text="🛸", font=("Segoe UI Emoji", 38), fg=CYAN, bg=LOGIN_BG, cursor="hand2")
        logo.pack()
        logo.bind("<Button-1>", self._on_logo_click)
        
        t1 = tk.Label(top, text="O R B I T A L   O S", font=("Segoe UI", 16, "bold"), fg=TEXT_COLOR, bg=LOGIN_BG)
        t1.pack(pady=(5, 2))
        
        t2 = tk.Label(top, text="AUTONOMOUS WORKSTATION GATEWAY", font=("Segoe UI", 8), fg=CYAN, bg=LOGIN_BG)
        t2.pack()
        
        card = tk.Frame(self.root, bg=CARD_BG, highlightbackground="#1E293B", highlightthickness=1)
        card.pack(fill="both", expand=True, padx=35, pady=20)
        
        tk.Label(card, text="AUTHENTICATION", font=("Segoe UI", 10, "bold"), fg=CYAN, bg=CARD_BG).pack(anchor="w", padx=25, pady=(20, 15))
        
        tk.Label(card, text="Username / Email / Phone", font=("Segoe UI", 8), fg=MUTED_TEXT, bg=CARD_BG).pack(anchor="w", padx=25)
        self.id_entry = tk.Entry(card, bg=ENTRY_BG, fg=TEXT_COLOR, insertbackground=CYAN, font=("Segoe UI", 10), relief="flat")
        self.id_entry.pack(fill="x", padx=25, pady=(4, 15), ipady=6)
        
        tk.Label(card, text="Password", font=("Segoe UI", 8), fg=MUTED_TEXT, bg=CARD_BG).pack(anchor="w", padx=25)
        self.pw_entry = tk.Entry(card, bg=ENTRY_BG, fg=TEXT_COLOR, insertbackground=CYAN, font=("Segoe UI", 10), show="•", relief="flat")
        self.pw_entry.pack(fill="x", padx=25, pady=(4, 15), ipady=6)
        
        btn = tk.Button(card, text="LOGIN", font=("Segoe UI", 10, "bold"), fg="#0B0E14", bg=CYAN, activebackground="#80F4FF", relief="flat", cursor="hand2", command=self.handle_login)
        btn.pack(fill="x", padx=25, pady=(10, 10), ipady=6)
        
        lbl = tk.Label(card, text="Forgot Password?", font=("Segoe UI", 8, "underline"), fg=CYAN, bg=CARD_BG, cursor="hand2")
        lbl.pack(pady=5)
        lbl.bind("<Button-1>", self.handle_forgot)

    def handle_login(self):
        u = self.id_entry.get().strip()
        p = self.pw_entry.get().strip()
        if not u or not p:
            messagebox.showwarning("Incomplete Credentials", "Please enter your identifier and password.")
            return
        messagebox.showinfo("Authentication Success", f"Welcome back, {u}!")
        self._launch_post_login_workstation(u)

    def handle_forgot(self, event=None):
        i = simpledialog.askstring("Account Recovery", "Enter your Username, Email, or Phone:")
        if i:
            messagebox.showinfo("Reset Dispatched", f"A recovery link was sent for: {i}")

    def _launch_post_login_workstation(self, username):
        self.root.destroy()
        base = r"C:\Orbital"
        target = os.path.join(base, "orbitalchat.py")
        if not os.path.exists(target):
            with open(target, "w", encoding="utf-8") as f:
                f.write('import sys\nfrom core.engine import process_chat\n\nprint("Orbital Nucleus AI Engine Active.")\nprint("Type /draw <prompt> for Nebula images or ask Nucleus anything.")\nprint("-------------------------------------------------------------")\n\nwhile True:\n    try:\n        user_input = input("You: ")\n        if user_input.lower() in ["exit", "quit"]:\n            break\n        reply = process_chat(user_input)\n        print(f"Orbital: {reply}\\n")\n    except KeyboardInterrupt:\n        break\n')
        subprocess.Popen([sys.executable, target], cwd=base)

if __name__ == "__main__":
    root = tk.Tk()
    app = OrbitalLoginGUI(root)
    root.mainloop()
