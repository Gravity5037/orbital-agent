import re

p = r"C:\Orbital\gui\cyber_organic_workstation.html"
with open(p, "r", encoding="utf-8") as f:
    c = f.read()

# Strip any broken iframe injection
c = re.sub(r'<div style=[\'"]padding:12px;.*', '', c, flags=re.DOTALL)

# Clean embed pointing directly to ttyd
iframe = '<div style="padding:12px; background:rgba(11,14,20,0.95); border-top:1px solid #00E5FF;"><div style="color:#00E5FF; font-size:0.8rem; font-weight:bold; margin-bottom:6px;">⚡ LIVE INTERACTIVE CONSOLE</div><iframe src="http://127.0.0.1:7681/" style="width:100%; height:260px; border:1px solid rgba(0,229,255,0.3); border-radius:8px;"></iframe></div>'

if "</body>" in c:
    c = c.replace("</body>", iframe + "</body>")
else:
    c += iframe

with open(p, "w", encoding="utf-8") as f:
    f.write(c)

print("[OK] Successfully fixed iframe URL")
