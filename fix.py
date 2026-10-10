with open(r"C:\Orbital\orbital_navigator_gui.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'f"Image generated and saved to:' in line:
        new_lines.append('                self.root.after(0, lambda: messagebox.showinfo("Nebula Render Complete", "Image generated: " + str(out_path)))\n')
    elif '{out_path}"))' in line:
        continue
    else:
        new_lines.append(line)

with open(r"C:\Orbital\orbital_navigator_gui.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("[?] Successfully repaired line 798!")
