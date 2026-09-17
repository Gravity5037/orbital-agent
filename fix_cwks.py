import re

with open('src/identity.rs', 'r', encoding='utf-8') as f:
    code = f.read()

pattern = r'if\s+CreateWellKnownSid\s*\([\s\S]*?\)\s*==\s*0'
replacement = 'if CreateWellKnownSid(windows_sys::Win32::Security::WinLocalSystemSid, std::ptr::null_mut(), system_sid_buf.as_mut_ptr() as *mut std::ffi::c_void, &mut system_sid_len) == 0'

code = re.sub(pattern, replacement, code)

with open('src/identity.rs', 'w', encoding='utf-8') as f:
    f.write(code)

print("CreateWellKnownSid 4-argument call restored!")
