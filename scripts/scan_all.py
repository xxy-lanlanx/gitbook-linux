import os, re

ROOT = 'e:/doc/gitbook/gitbook-linux'
out = []
for root, _, fs in os.walk(ROOT):
    if 'scripts' in root or '.git' in root:
        continue
    for fn in fs:
        if not fn.endswith('.md'):
            continue
        p = os.path.join(root, fn)
        t = open(p, encoding='utf-8').read()
        q = t.count('?')
        u = t.count('\ufffd')
        if q > 0 or u > 0:
            rel = os.path.relpath(p, ROOT)
            out.append(f'{rel}  q={q} u={u}')
            # show a few contexts
            for m in list(re.finditer(r'.{0,12}\?.{0,12}', t))[:3]:
                out.append('    ' + repr(m.group(0)))
with open(os.path.join(ROOT, 'scripts', 'scan_all.txt'), 'w', encoding='utf-8') as fp:
    fp.write('\n'.join(out))
print('done; files with ? or fffd:', len(out)//4)
