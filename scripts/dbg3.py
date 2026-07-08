import re, os, sys
sys.path.insert(0, 'e:/doc/gitbook/gitbook-linux/scripts')
import test_fix2 as t

files = [
    'linux-cao-zuo-xi-tong-ji-ben-yuan-li/05linux-nei-he-io-ji-chu-zhi-shi-yu-gai-nian.md',
    'linux-cao-zuo-xi-tong-ji-ben-yuan-li/06linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li.md',
    'linux-cao-zuo-xi-tong-ji-ben-yuan-li/07linux-cao-zuo-xi-tong-chu-li-qi-diao-du-ji-ben-zhun-ze-he-shi-xian.md',
    'linux-cao-zuo-xi-tong-ji-ben-yuan-li/08linux-nei-he-cao-zuo-xi-tong-yuan-li-yu-gai-shu.md',
    'linux-cao-zuo-xi-tong-ji-ben-yuan-li/12linux-cao-zuo-xi-tong-li-jie-cpu-shang-xia-wen-qie-huan.md',
    'linux-jin-cheng-guan-li/02linux-nei-he-liu-da-jin-cheng-tong-xin-ji-zhi-yuan-li.md',
    'linux-jin-cheng-guan-li/03linux-nei-he-socket-tong-xin-yuan-li.md',
    'linux-jin-cheng-guan-li/04linux-nei-he-jin-cheng-de-guan-li-yu-diao-du.md',
    'linux-jin-cheng-guan-li/05linux-nei-he-jin-cheng-guan-li-bing-fa-tong-bu-yu-yuan-zi-cao-zuo.md',
]

out = []
for f in files:
    path = os.path.join('e:/doc/gitbook/gitbook-linux', f)
    with open(path, 'r', encoding='utf-8') as fp:
        text = fp.read()
    protected, urls = t.protect_urls(text)
    fixed = t.restore_urls(t.fix_text(protected), urls)
    if '?' not in fixed:
        continue
    out.append('==== ' + f)
    for m in re.finditer(r'.{0,10}\?.{0,10}', fixed):
        seg = m.group(0)
        cps = ' '.join(f'{ord(c):04x}' for c in seg)
        out.append('  SEG: ' + repr(seg))
        out.append('  CPS: ' + cps)
    out.append('')

with open('e:/doc/gitbook/gitbook-linux/scripts/dbg3_out.txt', 'w', encoding='utf-8') as fp:
    fp.write('\n'.join(out))
