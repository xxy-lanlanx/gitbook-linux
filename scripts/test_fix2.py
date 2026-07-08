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
    # 1. Remove all U+FFFD unconditionally
    text = text.replace('\ufffd', '')
    
    # 2. ?? -> （
    text = re.sub(r'\?\?', '（', text)
    
    # 3. ? between Chinese and English/number -> （
    text = re.sub(r'([\u4e00-\u9fff])\?([a-zA-Z0-9])', r'\1（\2', text)
    text = re.sub(r'([a-zA-Z0-9])\?([\u4e00-\u9fff])', r'\1）\2', text)
    
    # 4. ? between English and ** markers -> space
    text = re.sub(r'([a-zA-Z0-9])\?\*\*', r'\1 **', text)
    text = re.sub(r'\*\*\?([a-zA-Z0-9])', r'** \1', text)
    
    # 5. ? between English/number and English/number (including punctuation like /, -, +, .)
    text = re.sub(r'([a-zA-Z0-9%])\?([a-zA-Z0-9])', r'\1 \2', text)
    
    # 6. ? between Chinese and Chinese -> remove
    text = re.sub(r'([\u4e00-\u9fff])\?([\u4e00-\u9fff])', r'\1\2', text)
    
    # 7. ? after Chinese punctuation and before Chinese or newline -> remove
    text = re.sub(r'([\u3002\uff0c\uff01\uff1b\uff1a\u3001])\?([\u4e00-\u9fff])', r'\1\2', text)
    text = re.sub(r'([\u3002\uff0c\uff01\uff1b\uff1a\u3001])\?\n', r'\1\n', text)
    
    # 8. ? after ) and before Chinese or markdown -> remove
    text = re.sub(r'\)\?([\u4e00-\u9fff*_])', r')\1', text)
    
    # 9. ? before markdown structures -> remove
    text = re.sub(r'\?\n\n(\* )', r'\n\n\1', text)
    text = re.sub(r'\?\n\n(\d+\. )', r'\n\n\1', text)
    text = re.sub(r'\?\n\n(#{1,6} )', r'\n\n\1', text)
    text = re.sub(r'\?\n\n(```)', r'\n\n\1', text)
    text = re.sub(r'\?\n\n(!\[)', r'\n\n\1', text)
    
    # 10. ? before double newline -> remove
    text = re.sub(r'\?\n\n', r'\n\n', text)
    
    # 11. ? around escaped star and bold markers -> space/remove
    text = re.sub(r'\?\\\*', r' *', text)
    text = re.sub(r'\*\*\?\*', r'** *', text)
    
    # 12. ? before single newline (line end) -> remove
    text = re.sub(r'\?\n', r'\n', text)
    
    # 13. ? around markdown _ markers -> remove
    text = re.sub(r'\?_', '_', text)
    text = re.sub(r'_\?', '_', text)
    
    # 14. ? around ** markers -> remove
    text = re.sub(r'\?\*\*', r'**', text)
    text = re.sub(r'\*\*\?', r'**', text)
    
    # 15. ? after numbers like 2?? -> remove
    text = re.sub(r'(\d)\?\?', r'\1', text)
    text = re.sub(r'(\d)\?', r'\1', text)
    
    # 16. ? after Chinese and before markdown special chars -> remove
    text = re.sub(r'([\u4e00-\u9fff])\?([*_])', r'\1\2', text)
    
    # 17. ? before/after Chinese parentheses -> remove/replace
    text = re.sub(r'\?\uff08', '\uff08', text)
    text = re.sub(r'\uff09\?', '\uff09', text)
    
    # 18. ? with spaces around Chinese -> remove
    text = re.sub(r'([\u4e00-\u9fff])\? +', r'\1 ', text)
    text = re.sub(r' \?([\u4e00-\u9fff])', r' \1', text)
    
    # 19. ? before backtick -> remove
    text = re.sub(r'\?`', '`', text)
    
    # 20. ? before/after pipe | -> remove
    text = re.sub(r'\?\|', '|', text)
    text = re.sub(r'\|\?', '|', text)
    
    # 21. ? between [ ] and english -> space
    text = re.sub(r'(\])\?([a-zA-Z])', r'\1 \2', text)
    text = re.sub(r'([a-zA-Z])\?(\[)', r'\1 \2', text)
    
    # 22. ? around Chinese quotation marks -> remove
    text = re.sub(r'\?\u201c', '\u201c', text)
    text = re.sub(r'\u201c\?', '\u201c', text)
    text = re.sub(r'\u201d\?', '\u201d', text)
    text = re.sub(r'\?\u201d', '\u201d', text)
    
    # 23. ? after English before Chinese punctuation -> remove
    text = re.sub(r'([a-zA-Z])\?([\u3002\uff0c\u3001])', r'\1\2', text)
    
    # 24. ? before Chinese open parenthesis -> remove
    text = re.sub(r'\?\uff08', '\uff08', text)
    
    # 25. ? after Chinese before number -> remove
    text = re.sub(r'([\u4e00-\u9fff])\?\s*([0-9])', r'\1\2', text)
    
    # 26. ? after punctuation before English/number -> remove
    text = re.sub(r'([\u3002\uff0c\uff1b])\?([a-zA-Z0-9])', r'\1\2', text)
    
    # 27. ? after open parenthesis before English/number -> remove
    text = re.sub(r'\(\?([a-zA-Z0-9])', r'(\1', text)
    
    # 28. ? after newline before English/number -> remove
    text = re.sub(r'\n\?([a-zA-Z0-9])', r'\n\1', text)
    
    # 29. ? between English and underscore -> space
    text = re.sub(r'([a-zA-Z])\?_', r'\1 _', text)
    
    # 30. ? between number and English -> space
    text = re.sub(r'(\d)\?([a-zA-Z])', r'\1 \2', text)
    
    # 31. ? after Chinese question mark and before English -> remove
    text = re.sub(r'\uff1f\?([a-zA-Z])', '？\\1', text)
    
    # 32. ? after ) before english -> remove
    text = re.sub(r'\)\?([a-zA-Z])', r')\1', text)
    
    # 33. ? after bold end and before newline -> remove
    text = re.sub(r'\*\*\?\n', r'**\n', text)
    
    # 34. targeted specific words (spaces already handled in rule 5, but handle specific ones with leading spaces)
    for word in ['Kernel', 'CPU', 'Socket', 'kernel', 'Linux', 'C', 'C++', 'IN', 'OUT', 'I/O', 'USB', 'IBM', 'OS', 'Runqueue', 'SCHED', 'counter', 'bonus', 'ECC', 'sendfile', 'MTU', 'connect', '10', '20']:
        text = re.sub(rf' \?{re.escape(word)}', f' {word}', text)
    
    # 35. remaining ? that are not in English sentence contexts -> remove
    text = re.sub(r'\?([\u4e00-\u9fff*_])', r'\1', text)
    text = re.sub(r'([\u4e00-\u9fff*_])\?', r'\1', text)
    text = re.sub(r'\?\n', r'\n', text)
    text = re.sub(r'\?\*', r'*', text)
    text = re.sub(r'\*\?', r'*', text)

    # 36. corrupted ? preceded by a SPACE -> drop the ? (keep one space)
    text = re.sub(r' \? ', ' ', text)
    text = re.sub(r' \?', ' ', text)
    text = re.sub(r'\? ', ' ', text)

    # 37. corrupted ? right after a full-width parenthesis -> drop
    text = re.sub(r'([\uff08\uff09])\?', r'\1', text)

    # 38. corrupted ? right after Chinese punctuation -> drop
    text = re.sub(r'([\u3002\uff0c\uff01\uff1b\uff1a\u3001])\?', r'\1', text)

    return text

import urllib.parse

URL_TOKEN = '\x00URL\x00'

def protect_urls(text):
    urls = []
    def _capture(m):
        urls.append(m.group(0))
        return URL_TOKEN
    # capture http/https absolute URLs
    text = re.sub(r'https?://[^\s\)\]\u4e00-\u9fff]+', _capture, text)
    # capture relative URLs that contain a query string (e.g. path?key=val)
    text = re.sub(r'[\w./%:+-]+\?[\w=&%/.:+-]+', _capture, text)
    return text, urls

def restore_urls(text, urls):
    for u in urls:
        text = text.replace(URL_TOKEN, u, 1)
    return text

# report
report_lines = []
for f in files:
    path = os.path.join('e:/doc/gitbook/gitbook-linux', f)
    with open(path, 'r', encoding='utf-8') as fp:
        text = fp.read()
    before_q = text.count('?')
    before_u = text.count('\ufffd')
    # protect URLs before fixing
    protected, urls = protect_urls(text)
    fixed = fix_text(protected)
    fixed = restore_urls(fixed, urls)
    after_q = fixed.count('?')
    after_u = fixed.count('\ufffd')
    report_lines.append(f'FILE: {f}')
    report_lines.append(f'BEFORE: q={before_q} u={before_u}')
    report_lines.append(f'AFTER: q={after_q} u={after_u}')
    # collect remaining ? contexts
    if after_q > 0:
        contexts = []
        for m in re.finditer(r'.{0,20}\?.{0,20}', fixed):
            contexts.append(m.group(0))
        report_lines.append('REMAINING ? CONTEXTS:')
        for c in contexts:
            report_lines.append('  ' + repr(c))
    report_lines.append('---')

with open('e:/doc/gitbook/gitbook-linux/scripts/fix_report3.txt', 'w', encoding='utf-8') as fp:
    fp.write('\n'.join(report_lines))
print('Done fix report 3 -> scripts/fix_report3.txt')
