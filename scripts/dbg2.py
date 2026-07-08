import re
s = '0 ?64K'
print('repr s:', repr(s))
print('slice 0:3:', repr(s[0:3]))
print('search [0-9]\\?:', re.search(r'[0-9]\?', s))
print('search literal q:', re.search(r'\?', s))
print('sub \\?->X:', re.sub(r'\?', 'X', s))
print('sub 0\\?6->Y:', re.sub(r'0\?6', 'Y', s))
print('sub group:', re.sub(r'([0-9])\?([0-9])', r'\1-\2', s))
print('codepoints:', [hex(ord(c)) for c in s])
