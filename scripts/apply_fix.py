import os, sys
sys.path.insert(0, 'e:/doc/gitbook/gitbook-linux/scripts')
import fix_encoding_clean as c

ROOT = 'e:/doc/gitbook/gitbook-linux'

for f in c.files:
    path = os.path.join(ROOT, f)
    with open(path, 'r', encoding='utf-8') as fp:
        text = fp.read()
    prot, saved = c.protect(text)
    fixed = c.restore(c.fix_text(prot), saved)
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(fixed)
    print(f'wrote {f}: q={fixed.count("?")} u={fixed.count(chr(0xfffd))}')
print('All files updated.')
