import os, re

files = [
    'linux-cao-zuo-xi-tong-ji-ben-yuan-li/05linux-nei-he-io-ji-chu-zhi-shi-yu-gai-nian.md',
    'linux-cao-zuo-xi-tong-ji-ben-yuan-li/06linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li.md',
    'linux-cao-zuo-xi-tong-ji-ben-yuan-li/07linux-cao-zuo-xi-tong-chu-li-qi-diao-du-ji-ben-zhun-ze-he-shi-xian.md',
    'linux-cao-zuo-xi-tong-ji-ben-yuan-li/08linux-nei-he-cao-zuo-xi-tong-yuan-li-yu-gai-shu.md',
    'linux-cao-zuo-xi-tong-ji-ben-yuan-li/12linux-cao-zuo-xi-tong-li-jie-cpu-shang-xia-wen-qie-huan.md',
    'linux-jin-cheng-guan-li/02linux-nei-he-liu-da-jin-cheng-tong-xin-ji-zhi-yuan-li.md',
    'linux-jin-cheng-guan-li/03linux-nei-he-socket-tong-xin-yuan-li.md',
    'linux-jin-cheng-guan-li/04linux-nei-he-jin-cheng-de-guan-li-yu-diao-du.md',
    'linux-jin-cheng-guan-li/05linux-nei-he-jin-cheng-guan-li-bing-fa-tong-bu-yu-yuan-zi-cao-zuo.md'
]

def fix_text(text):
    text = text.replace('\ufffd', '')
    text = re.sub(r'\?\?', '（', text)
    text = re.sub(r'([\u4e00-\u9fff])\?([a-zA-Z0-9])', r'\1（\2', text)
    text = re.sub(r'([a-zA-Z0-9])\?([\u4e00-\u9fff])', r'\1）\2', text)
    text = re.sub(r'([a-zA-Z0-9])\?\*\*', r'\1 **', text)
    text = re.sub(r'\*\*\?([a-zA-Z0-9])', r'** \1', text)
    text = re.sub(r'([a-zA-Z0-9])\?([a-zA-Z0-9])', r'\1 \2', text)
    text = re.sub(r'([\u4e00-\u9fff])\?([\u4e00-\u9fff])', r'\1\2', text)
    text = re.sub(r'([\u3002\uff0c\uff01\uff1b\uff1a\u3001])\?([\u4e00-\u9fff])', r'\1\2', text)
    text = re.sub(r'([\u3002\uff0c\uff01\uff1b\uff1a\u3001])\?\n', r'\1\n', text)
    text = re.sub(r'\)\?([\u4e00-\u9fff*_])', r')\1', text)
    text = re.sub(r'\?\n\n(\* )', r'\n\n\1', text)
    text = re.sub(r'\?\n\n(\d+\. )', r'\n\n\1', text)
    text = re.sub(r'\?\n\n(#{1,6} )', r'\n\n\1', text)
    text = re.sub(r'\?\n\n(```)', r'\n\n\1', text)
    text = re.sub(r'\?\n\n(!\[)', r'\n\n\1', text)
    text = re.sub(r'\?\n\n', r'\n\n', text)
    text = re.sub(r'\?\\\*', r' *', text)
    text = re.sub(r'\*\*\?\*', r'** *', text)
    text = re.sub(r'\?\n', r'\n', text)
    text = re.sub(r'\?_', '_', text)
    text = re.sub(r'_\?', '_', text)
    text = re.sub(r'\?\*\*', r'**', text)
    text = re.sub(r'\*\*\?', r'**', text)
    text = re.sub(r'(\d)\?\?', r'\1', text)
    text = re.sub(r'(\d)\?', r'\1', text)
    text = re.sub(r'([\u4e00-\u9fff])\?([*_])', r'\1\2', text)
    text = re.sub(r'\?\uff08', r'（', text)
    text = re.sub(r'\uff09\?', r'）', text)
    text = re.sub(r'([\u4e00-\u9fff])\? +', r'\1 ', text)
    text = re.sub(r' \?([\u4e00-\u9fff])', r' \1', text)
    return text

with open('e:/doc/gitbook/gitbook-linux/scripts/fix_report.txt', 'w', encoding='utf-8') as out:
    for f in files:
        path = os.path.join('e:/doc/gitbook/gitbook-linux', f)
        with open(path, 'r', encoding='utf-8') as fp:
            text = fp.read()
        before_q = text.count('?')
        before_u = text.count('\ufffd')
        fixed = fix_text(text)
        after_q = fixed.count('?')
        after_u = fixed.count('\ufffd')
        out.write(f'=== {f} ===\n')
        out.write(f'Before: ?={before_q} U+FFFD={before_u}\n')
        out.write(f'After:  ?={after_q} U+FFFD={after_u}\n')
        for i, ch in enumerate(fixed):
            if ch == '?':
                start = max(0, i-15)
                end = min(len(fixed), i+15)
                out.write(f'  {repr(fixed[start:end])}\n')
        out.write('\n')

print('Done fix report')
