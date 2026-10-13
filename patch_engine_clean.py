p = r"C:\Orbital\engine.py"
with open(p, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "orbital_vision.py" in line and "subprocess.Popen" in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(f'{indent}subprocess.Popen(["pythonw.exe", r"C:\\Orbital\\orbital_vision.py"], creationflags=0x08000000)\n')
    else:
        new_lines.append(line)

with open(p, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("[✔] Engine successfully updated to launch Liquid Glass vision.")
