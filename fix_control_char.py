import re

with open('src/identity.rs', 'r', encoding='utf-8') as f:
    code = f.read()

# Strip ASCII control characters (0x00-0x08, 0x0B-0x0C, 0x0E-0x1F)
code = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', code)

# Restore WinLocalSystemSid as first parameter of CreateWellKnownSid
code = re.sub(r'CreateWellKnownSid\s*\(\s*,', 'CreateWellKnownSid(windows_sys::Win32::Security::WinLocalSystemSid,', code)
code = re.sub(r'CreateWellKnownSid\s*\(\s*\)', 'CreateWellKnownSid(windows_sys::Win32::Security::WinLocalSystemSid, std::ptr::null_mut(), system_sid_buf.as_mut_ptr() as _, &mut system_sid_len)', code)

with open('src/identity.rs', 'w', encoding='utf-8') as f:
    f.write(code)

print("Control character stripped and line 254 repaired!")
