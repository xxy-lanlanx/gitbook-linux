import re, os, sys
sys.path.insert(0, 'e:/doc/gitbook/gitbook-linux/scripts')
import test_fix2 as t

# pull exact segments from the real file via codepoint scan
path = 'e:/doc/gitbook/gitbook-linux/linux-cao-zuo-xi-tong-ji-ben-yuan-li/05linux-nei-he-io-ji-chu-zhi-shi-yu-gai-nian.md'
text = open(path, encoding='utf-8').read()
# find a ? between two CJK
m = re.search(r'[\u4e00-\u9fff]\?[\u4e00-\u9fff]', text)
print('found CJK?CJK seg:', repr(m.group(0)) if m else None)
if m:
    seg = m.group(0)
    print('fix_text on seg:', repr(t.fix_text(seg)))
    print('rule6 only:', repr(re.sub(r'([\u4e00-\u9fff])\?([\u4e00-\u9fff])', r'\1\2', seg)))
    print('rule35 only:', repr(re.sub(r'([\u4e00-\u9fff*_])\?', r'\1', seg)))

# also test 内存映射?I/O
seg2 = '内存映射?I/O 的数据'
print('seg2 fix:', repr(t.fix_text(seg2)))
print('seg2 rule35:', repr(re.sub(r'([\u4e00-\u9fff*_])\?', r'\1', seg2)))
