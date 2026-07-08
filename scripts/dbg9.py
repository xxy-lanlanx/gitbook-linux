import sys
sys.path.insert(0, 'e:/doc/gitbook/gitbook-linux/scripts')
import fix_encoding_clean as c

path = 'e:/doc/gitbook/gitbook-linux/linux-cao-zuo-xi-tong-ji-ben-yuan-li/06linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li.md'
text = open(path, encoding='utf-8').read()
prot, saved = c.protect(text)
# find first 内存映射 in prot and dump cps
i = prot.find('内存映射')
seg = prot[i-2:i+20]
print('PROT seg cps:', ' '.join(f'{ord(ch):04x}' for ch in seg))
print('contains URL_TOKEN:', c.URL_TOKEN in seg)
print('contains QM_TOKEN:', c.QM_TOKEN in seg)
# also list all saved url entries containing I/O or 映射
for kind, val in saved:
    if 'I/O' in val or '映射' in val:
        print('SAVED:', kind, repr(val))
# show how many saved total and how many urls have ?
urls_with_q = [v for k,v in saved if k=='url' and '?' in v]
print('num url saved:', len([v for k,v in saved if k=='url']))
print('num urls with ?:', len(urls_with_q))
for u in urls_with_q[:10]:
    print('  URL?', repr(u))
