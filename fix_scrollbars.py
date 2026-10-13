p = r"C:\Orbital\gui\cyber_organic_workstation.html"
with open(p, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Lock the outer page to 100vh so the main window never scrolls
html = html.replace("min-height: 100vh;\n            overflow-y: auto;", "height: 100vh;\n            overflow: hidden;")
html = html.replace("min-height: 100vh; overflow-y: auto;", "height: 100vh; overflow: hidden;")

# 2. Ensure chat container has independent scroll & auto-scrolls to bottom
if ".chat-container {" in html:
    html = html.replace(".chat-container {", ".chat-container {\n            max-height: calc(100vh - 140px);\n            overflow-y: auto;\n            scrollbar-gutter: stable;")

# 3. Add custom cyan/dark scrollbars
style_patch = """
    <style>
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #080B10; }
        ::-webkit-scrollbar-thumb { background: rgba(0, 229, 255, 0.3); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #00E5FF; }
        .chat-container {
            flex: 1;
            overflow-y: auto !important;
            padding: 20px 30px;
        }
    </style>
</head>"""

html = html.replace("</head>", style_patch)

with open(p, "w", encoding="utf-8") as f:
    f.write(html)

print("[OK] Independent scrollbars configured.")
