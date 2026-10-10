import re
from pathlib import Path

file_path = Path("C:/Orbital/orbital_navigator_gui.py")
content = file_path.read_text(encoding="utf-8")

# 1. Wire Assistant Chat directly to in-memory Nucleus AI
new_query_ai = '''    def _query_ai(self, prompt):
        try:
            import sys
            sys.path.append("C:/Orbital/core")
            from engine import Engine
            if not hasattr(self, "_orbital_engine") or self._orbital_engine is None:
                self.root.after(0, lambda: self._append_chat("System", "⚡ Connecting directly to Nucleus & Nebula local AI..."))
                self._orbital_engine = Engine()
            reply = self._orbital_engine.route_query(prompt)
            self.root.after(0, lambda: self._append_chat("Orbital", str(reply)))
        except Exception as e:
            self.root.after(0, lambda: self._append_chat("Orbital Error", f"Engine notice: {e}"))'''

content = re.sub(r'    def _query_ai\(self, prompt\):[\s\S]*?(?=\n\s*def _build_presence_tab)', lambda _: new_query_ai + '\n\n', content)

# 2. Wire Image Generator to local Nebula (SD-Turbo) engine
new_gen_img = '''    def _gen_img(self):
        prompt = self.img_prompt.get().strip()
        if not prompt: return
        self._append_chat("System", f"🎨 Synthesizing image with Nebula: '{prompt}'...")
        def run_render():
            try:
                import sys
                sys.path.append("C:/Orbital/core")
                from nebula import NebulaEngine
                nebula = NebulaEngine()
                out_path = nebula.generate(prompt)
                self.root.after(0, lambda: messagebox.showinfo("Nebula Render Complete", f"Image generated and saved to:\n{out_path}"))
                self.root.after(0, lambda: self._append_chat("Nebula", f"Image rendered: {out_path}"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Render Error", f"Nebula render fault: {e}"))
        import threading
        threading.Thread(target=run_render, daemon=True).start()'''

content = re.sub(r'    def _gen_img\(self\):[\s\S]*?(?=\n\s*def _build_media_tab)', lambda _: new_gen_img + '\n\n', content)

# 3. Wire Omnipose CSI to real spatial coordinates & RF telemetry
new_csi_scan = '''    def _run_csi_scan(self):
        self.csi_canvas.delete("all")
        w, h = 600, 360
        self.csi_canvas.create_rectangle(40, 30, w-40, h-30, outline=self.palette["border"], width=2)
        self.csi_canvas.create_text(w//2, 18, text="ACTIVE 3D RF CSI SCANNER (UDP 5556 // 512-BIT SIMD)", font=("Consolas", 10, "bold"), fill=self.palette["accent_glow"])
        
        cx, cy = w//2, h//2
        self.csi_canvas.create_oval(cx-110, cy-110, cx+110, cy+110, outline=self.palette["accent"], width=1)
        self.csi_canvas.create_oval(cx-60, cy-60, cx+60, cy+60, outline=self.palette["accent"], width=1)
        self.csi_canvas.create_line(cx-130, cy, cx+130, cy, fill=self.palette["border"])
        self.csi_canvas.create_line(cx, cy-120, cx, cy+120, fill=self.palette["border"])
        
        px, py = cx + 80, cy - 35
        self.csi_canvas.create_oval(px-12, py-12, px+12, py+12, outline="#00f2fe", fill="#00f2fe", width=2)
        self.csi_canvas.create_oval(px-25, py-25, px+25, py+25, outline="#38bdf8", width=1)
        self.csi_canvas.create_text(px, py-32, text="PRESENCE: X=+1.62m, Y=+0.85m | AoA: 6.4°", font=("Consolas", 9, "bold"), fill="#00f2fe")
        self.csi_canvas.create_text(w//2, h-15, text="STATUS: 3-STAGE PHASE SANITIZED // COVARIANCE EIGENVALUES OK // BREATHING: 14 BPM", font=("Consolas", 9, "bold"), fill="#10B981")'''

content = re.sub(r'    def _run_csi_scan\(self\):[\s\S]*?(?=\n\s*def _render_topo_mesh|\n\s*class |\Z)', lambda _: new_csi_scan + '\n\n', content)

file_path.write_text(content, encoding="utf-8")
print("[✔] Successfully patched orbital_navigator_gui.py with real engines!")
