with open('src/identity.rs', 'r', encoding='utf-8') as f:
    lines = f.readlines()

clean = [l for l in lines if 'type PSID =' not in l and 'const GENERIC_ALL:' not in l]

target_idx = 0
for i, l in enumerate(clean):
    if 'windows_sys' in l or 'Win32::Security' in l:
        target_idx = i
        break

defs = [
    "type PSID = *mut std::ffi::c_void;\n",
    "const GENERIC_ALL: u32 = 0x10000000;\n"
]

final_lines = clean[:target_idx] + defs + clean[target_idx:]
content = "".join(final_lines)
content = content.replace('PSID,', '').replace(', PSID', '').replace('GENERIC_ALL,', '').replace(', GENERIC_ALL', '')

with open('src/identity.rs', 'w', encoding='utf-8') as f:
    f.write(content)
print("PSID and GENERIC_ALL scope fix applied!")
