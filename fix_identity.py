import re

with open('src/identity.rs', 'r', encoding='utf-8') as f:
    code = f.read()

code = re.sub(r'let\s+mut\s+new_dacl:[^=]+=\s*0;', 'let mut new_dacl: *mut std::ffi::c_void = std::ptr::null_mut();', code)
code = re.sub(r'CreateWellKnownSid\s*\(\s*([^,]+)\s*,\s*0\s*,', r'CreateWellKnownSid(, std::ptr::null_mut(),', code)

with open('src/identity.rs', 'w', encoding='utf-8') as f:
    f.write(code)

print("identity.rs updated.")
