p = r"C:\Orbital\gui\cyber_organic_workstation.html"
with open(p, "r", encoding="utf-8") as f:
    html = f.read()

console_markup = """
    <div style="background:#080b10; border-top:1px solid rgba(0,229,255,0.25); padding:10px 20px;">
        <div style="font-size:0.75rem; color:#00E5FF; font-weight:700; letter-spacing:1px; margin-bottom:6px;">
            ⚡ LIVE INTERACTIVE CONSOLE (PORT 7681)
        </div>
        <iframe src="http://127.0.0.1:7681/" style="width:100%; height:220px; border:1px solid rgba(0,229,255,0.2); border-radius:6px; background:#000;"></iframe>
    </div>
</body>"""

if "LIVE INTERACTIVE CONSOLE" not in html:
    html = html.replace("</body>", console_markup)
    with open(p, "w", encoding="utf-8") as f:
        f.write(html)
    print("[✔] Live console panel injected successfully.")
else:
    print("[!] Console panel already present.")
