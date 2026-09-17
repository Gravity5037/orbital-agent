with open('src/identity.rs', 'r', encoding='utf-8') as f:
    lines = f.readlines()

clean_lines = [l for l in lines if 'type PSID =' not in l and 'const GENERIC_ALL:' not in l]

for i in range(len(clean_lines)):
    if 'use ' in clean_lines[i]:
        clean_lines[i] = clean_lines[i].replace('PSID,', '').replace(', PSID', '').replace('PSID', '')
        clean_lines[i] = clean_lines[i].replace('GENERIC_ALL,', '').replace(', GENERIC_ALL', '').replace('GENERIC_ALL', '')

last_use = 0
for i, l in enumerate(clean_lines):
    if l.strip().startswith('use ') or l.strip().startswith('pub use '):
        last_use = i

definitions = ['
type PSID = *mut std::ffi::c_void;
const GENERIC_ALL: u32 = 0x10000000;
']
final_lines = clean_lines[:last_use+1] + definitions + clean_lines[last_use+1:]

with open('src/identity.rs', 'w', encoding='utf-8') as f:
    f.writelines(final_lines)
print('Module scope definitions applied successfully!')
