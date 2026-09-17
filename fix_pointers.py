with open('src/identity.rs', 'r', encoding='utf-8') as f:
    lines = f.readlines()

in_snsi = False
zero_count = 0
for i in range(len(lines)):
    if 'SetNamedSecurityInfoW' in lines[i]:
        in_snsi = True
        zero_count = 0
    if in_snsi:
        if lines[i].strip() in ('0,', '0'):
            zero_count += 1
            if zero_count in (1, 2):
                lines[i] = lines[i].replace('0', 'std::ptr::null_mut()')
            elif zero_count >= 3:
                lines[i] = lines[i].replace('0', 'std::ptr::null()')
        if ');' in lines[i]:
            in_snsi = False

with open('src/identity.rs', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Pointers updated!')
