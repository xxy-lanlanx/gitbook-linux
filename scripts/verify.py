import os, sys
sys.path.insert(0, 'e:/doc/gitbook/gitbook-linux/scripts')
import fix_encoding_clean as c

ROOT = 'e:/doc/gitbook/gitbook-linux'
ok = True
for f in c.files:
    p = os.path.join(ROOT, f)
    t = open(p, encoding='utf-8').read()
    u = t.count('\ufffd')
    q = t.count('?')
    # check URLs preserved
    has_url = ('index.html?ca' in t) or ('zhihu.com/?target' in t)
    # check balanced backticks (rough markdown sanity)
    bt = t.count('`') % 2
    # double ascii space count
    dbl = t.count('  ')
    print(f'{f}: fffd={u} q={q} url_ok={has_url} backtick_balanced={bt==0} double_spaces={dbl}')
    if u != 0:
        ok = False
        print('  !! FFFD remains')
    if bt != 0:
        print('  !! unbalanced backticks')
print('ALL OK' if ok else 'PROBLEMS FOUND')
