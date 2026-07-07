import os, re

ROOT = 'e:/doc/gitbook/gitbook-linux'

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

URL_TOKEN = '\x00URL\x00'
QM_TOKEN = '\x00QM\x00'

# ---- protect legitimate content so corruption rules don't touch it ----
def protect(text):
    saved = []  # list of ('url', url) or ('qm', 'X?Y')
    def _cap(m):
        saved.append(('url', m.group(0)))
        return URL_TOKEN
    # absolute URLs
    text = re.sub(r'https?://[^\s\)\]\u4e00-\u9fff]+', _cap, text)
    # relative URLs containing a query string (ASCII only; \w would match CJK!)
    text = re.sub(r'[A-Za-z0-9./%:+-]+\?[A-Za-z0-9=&%/.:+-]+', _cap, text)
    # legitimate Chinese question marks:  ? preceded by a question particle + CJK,
    # or ? preceded by CJK and followed by a continuation/paren/punctuation word
    q_particles = '么吗呢吧啊呀哪啥怎为何谁几多怎么什么为何是否'
    q_follow = '有是还不没就也才该能会让把被给在的了吗呢吧啊呀，。、）！'
    def _qm1(m):
        saved.append(('qm', m.group(1) + '?' + m.group(2)))
        return QM_TOKEN
    text = re.sub(r'([' + q_particles + r'])\?([\u4e00-\u9fff])', _qm1, text)
    def _qm2(m):
        saved.append(('qm', m.group(1) + '?' + m.group(2)))
        return QM_TOKEN
    text = re.sub(r'([\u4e00-\u9fff])\?([' + q_follow + r'])', _qm2, text)
    return text, saved

def restore(text, saved):
    for kind, val in saved:
        if kind == 'url':
            text = text.replace(URL_TOKEN, val, 1)
        else:  # qm
            text = text.replace(QM_TOKEN, val, 1)
    text = text.replace(URL_TOKEN, '')
    text = text.replace(QM_TOKEN, '?')
    return text

def fix_text(text):
    # 0. remove U+FFFD unconditionally
    text = text.replace('\ufffd', '')

    # 1. ? adjacent to whitespace -> drop the ?, collapse to single space
    text = re.sub(r' ?\? ?', ' ', text)
    text = re.sub(r' +\?', ' ', text)
    text = re.sub(r'\? +', ' ', text)

    # 2. ? right after / before full-width parens or Chinese punctuation -> drop
    text = re.sub(r'([\uff08\uff09\u3002\uff0c\uff01\uff1b\uff1a\u3001])\?', r'\1', text)
    text = re.sub(r'\?([\uff08\uff09])', r'\1', text)

    # 3. ? before / after ascii parens -> drop
    text = re.sub(r'\)\?', ')', text)
    text = re.sub(r'\?\)', ')', text)
    text = re.sub(r'\(\?', '(', text)
    text = re.sub(r'\?\(', '(', text)

    # 4. ? between CJK and Latin/Digit, or Latin/Digit and CJK -> single space (readability)
    text = re.sub(r'([\u4e00-\u9fff])\?([a-zA-Z0-9])', r'\1 \2', text)
    text = re.sub(r'([a-zA-Z0-9])\?([\u4e00-\u9fff])', r'\1 \2', text)

    # 5. ? between Latin/Digit and Latin/Digit -> single space
    text = re.sub(r'([a-zA-Z0-9])\?([a-zA-Z0-9])', r'\1 \2', text)

    # 6. ? adjacent to markdown markers -> drop
    text = re.sub(r'\?([`*_|\[\]])', r'\1', text)
    text = re.sub(r'([`*_|\[\]])\?', r'\1', text)

    # 7. ? before Chinese punctuation -> drop
    text = re.sub(r'\?([\u3002\uff0c\uff01\uff1b\uff1a\u3001])', r'\1', text)

    # 8. ? between two CJK (corruption) -> drop
    text = re.sub(r'([\u4e00-\u9fff])\?([\u4e00-\u9fff])', r'\1\2', text)

    # 9. ? at end of line / before newline -> drop
    text = re.sub(r'\?\n', '\n', text)

    # 10. any other stray ? -> drop
    text = re.sub(r'\?', '', text)
    return text

if __name__ == '__main__':
    report = []
    for f in files:
        path = os.path.join(ROOT, f)
        with open(path, 'r', encoding='utf-8') as fp:
            text = fp.read()
        before_q = text.count('?')
        before_u = text.count('\ufffd')
        prot, saved = protect(text)
        fixed = restore(fix_text(prot), saved)
        after_q = fixed.count('?')
        after_u = fixed.count('\ufffd')
        report.append(f'FILE: {f}')
        report.append(f'BEFORE: q={before_q} u={before_u}')
        report.append(f'AFTER: q={after_q} u={after_u}')
        if after_q > 0:
            ctx = []
            for m in re.finditer(r'.{0,15}\?.{0,15}', fixed):
                ctx.append('  ' + repr(m.group(0)))
            report.append('REMAINING ?:')
            report.append('\n'.join(ctx))
        report.append('---')
    with open(os.path.join(ROOT, 'scripts', 'clean_report.txt'), 'w', encoding='utf-8') as fp:
        fp.write('\n'.join(report))
    print('Done -> scripts/clean_report.txt')
