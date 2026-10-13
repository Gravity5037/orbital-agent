p = r"C:\Orbital\engine.py"
with open(p, "r", encoding="utf-8") as f:
    code = f.read()

# Enhance the system prompt so Nucleus answers conversationally and only executes when requested
old_prompt = '"You are Orbital OS, operating offline on local hardware. Keep answers concise. If asked to run a PC command, reply ONLY: RUN_CMD: <powershell command>"'
new_prompt = '''"You are Orbital OS, an autonomous cyber-organic workstation operating locally offline. Answer questions directly and concisely. When a user explicitly asks to run a command, search files, inspect hardware, or perform a system task, provide the answer and prepend 'RUN_CMD: <powershell command>' on its own line."'''

if old_prompt in code:
    code = code.replace(old_prompt, new_prompt)
    with open(p, "w", encoding="utf-8") as f:
        f.write(code)
    print("[✔] Engine prompt updated for smart conversation + execution.")
else:
    print("[i] Engine already configured.")
