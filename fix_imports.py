with open('src/identity.rs', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'PROTECTED_DACL_SECURITY_INFORMATION' in line or 'Win32::Security' in line:
        line = line.replace('PSID,', '').replace(', PSID', '').replace('PSID', '')
        line = line.replace('GENERIC_ALL,', '').replace(', GENERIC_ALL', '').replace('GENERIC_ALL', '')
    new_lines.append(line)

content = "".join(new_lines)
if 'type PSID =' not in content:
    content = "type PSID = *mut std::ffi::c_void;\nconst GENERIC_ALL: u32 = 0x10000000;\n" + content

with open('src/identity.rs', 'w', encoding='utf-8') as f:
    f.write(content)
print("Imports updated!")
