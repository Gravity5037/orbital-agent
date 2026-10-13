import re
p = r"C:\Orbital\gui\cyber_organic_workstation.html"
with open(p, "r", encoding="utf-8") as f:
    html = f.read()

# Fix the broken iframe source URL
html = re.sub(r'<iframe class="terminal-frame" src="[^"]*"></iframe>', '<iframe class="terminal-frame" src="http://127.0.0.1:7681/"></iframe>', html)

with open(p, "w", encoding="utf-8-sig") as f:
    f.write(html)
print("[✔] Terminal iframe source repaired.")
