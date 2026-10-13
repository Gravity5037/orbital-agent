p = r"C:\Orbital\gui\cyber_organic_workstation.html"
with open(p, "r", encoding="utf-8") as f:
    html = f.read()

# Fix body overflow so embedded elements are visible and scrollable
html = html.replace("height: 100vh;\n            overflow: hidden;", "min-height: 100vh;\n            overflow-y: auto;")
html = html.replace("height: 100vh; overflow: hidden;", "min-height: 100vh; overflow-y: auto;")

# Ensure the main container does not clamp height
html = html.replace("flex: 1;\n            display: flex;\n            flex-direction: column;", "flex: 1;\n            display: flex;\n            flex-direction: column;\n            min-height: 100vh;")

with open(p, "w", encoding="utf-8") as f:
    f.write(html)

print("[OK] Layout patched for terminal visibility.")
