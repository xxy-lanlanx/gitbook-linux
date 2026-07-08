import sys
sys.path.insert(0, 'e:/doc/gitbook/gitbook-linux/scripts')
import fix_encoding_clean as c
import re

# isolation test
for s in ['磁盘到?内核缓冲区', '内存映射?I/O 的数据', '应用程序调用?write', '内核代码运行的地方?_。']:
    print(repr(s), '->', repr(c.fix_text(s)))

print('==== full file 06 ====')
path = 'e:/doc/gitbook/gitbook-linux/linux-cao-zuo-xi-tong-ji-ben-yuan-li/06linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li.md'
text = open(path, encoding='utf-8').read()
prot, saved = c.protect(text)
print('prot count ?:', prot.count('?'))
print('QM tokens in prot:', prot.count(c.QM_TOKEN))
fx = c.fix_text(prot)
print('fix_text(prot) count ?:', fx.count('?'))
fixed = c.restore(fx, saved)
print('fixed count ?:', fixed.count('?'))
for m in re.finditer(r'.{0,15}\?.{0,15}', fixed):
    seg = m.group(0)
    cps = ' '.join(f'{ord(c):04x}' for c in seg)
    print('  REMAIN:', repr(seg))
    print('     CPS:', cps)
print('count ?:', fixed.count('?'))
# show what happened to first 内存映射?I/O
i = fixed.find('内存映射')
print('ctx:', repr(fixed[i-3:i+25]))
