import re
out = []
path = 'e:/doc/gitbook/gitbook-linux/linux-cao-zuo-xi-tong-ji-ben-yuan-li/06linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li.md'
text = open(path, encoding='utf-8').read()
# find all 内存映射?I occurrences and print CPS
for m in re.finditer(r'内存映射.?.I/O', text):
    seg = m.group(0)
    cps = ' '.join(f'{ord(c):04x}' for c in seg)
    out.append('SEG: ' + repr(seg))
    out.append('CPS: ' + cps)
    out.append('')
with open('e:/doc/gitbook/gitbook-linux/scripts/dbg7_out.txt', 'w', encoding='utf-8') as fp:
    fp.write('\n'.join(out))
