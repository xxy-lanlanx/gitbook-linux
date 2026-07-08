import re, os, sys
sys.path.insert(0, 'e:/doc/gitbook/gitbook-linux/scripts')
import test_fix2 as t

path = 'e:/doc/gitbook/gitbook-linux/linux-cao-zuo-xi-tong-ji-ben-yuan-li/06linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li.md'
text = open(path, encoding='utf-8').read()
protected, urls = t.protect_urls(text)
fixed = t.restore_urls(t.fix_text(protected), urls)
# find remaining ? with context
for m in re.finditer(r'.{0,12}\?.{0,12}', fixed):
    print(repr(m.group(0)))
print('=== count ? in fixed:', fixed.count('?'))
# Show what happened to 内存映射?I/O
idx = fixed.find('内存映射')
print('around 内存映射 in FIXED:', repr(fixed[idx-2:idx+20]))
