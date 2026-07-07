import re

filepath = r"e:\doc\gitbook\gitbook-linux\SUMMARY.md"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 更新 Linux操作系统基本原理 中的路径编号
replacements = [
    # 05 -> 06
    (r'\(linux-cao-zuo-xi-tong-ji-ben-yuan-li/05linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li\.md\)', '(linux-cao-zuo-xi-tong-ji-ben-yuan-li/06linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li.md)'),
    # 06 -> 07
    (r'\(linux-cao-zuo-xi-tong-ji-ben-yuan-li/06linux-cao-zuo-xi-tong-chu-li-qi-diao-du-ji-ben-zhun-ze-he-shi-xian\.md\)', '(linux-cao-zuo-xi-tong-ji-ben-yuan-li/07linux-cao-zuo-xi-tong-chu-li-qi-diao-du-ji-ben-zhun-ze-he-shi-xian.md)'),
    # 07 -> 08
    (r'\(linux-cao-zuo-xi-tong-ji-ben-yuan-li/07linux-nei-he-cao-zuo-xi-tong-yuan-li-yu-gai-shu\.md\)', '(linux-cao-zuo-xi-tong-ji-ben-yuan-li/08linux-nei-he-cao-zuo-xi-tong-yuan-li-yu-gai-shu.md)'),
    # 08 -> 09
    (r'\(linux-cao-zuo-xi-tong-ji-ben-yuan-li/08linux-xi-tong-diao-yong-yuan-li-yu-shi-xian\.md\)', '(linux-cao-zuo-xi-tong-ji-ben-yuan-li/09linux-xi-tong-diao-yong-yuan-li-yu-shi-xian.md)'),
    # 09 -> 10
    (r'\(linux-cao-zuo-xi-tong-ji-ben-yuan-li/09linux-zhong-duan-yu-yi-chang-chu-li-ji-zhi\.md\)', '(linux-cao-zuo-xi-tong-ji-ben-yuan-li/10linux-zhong-duan-yu-yi-chang-chu-li-ji-zhi.md)'),
    # 10 -> 11
    (r'\(linux-cao-zuo-xi-tong-ji-ben-yuan-li/10linux-nei-he-shi-jian-guan-li-yu-ding-shi-qi\.md\)', '(linux-cao-zuo-xi-tong-ji-ben-yuan-li/11linux-nei-he-shi-jian-guan-li-yu-ding-shi-qi.md)'),
    # 11 -> 12
    (r'\(linux-cao-zuo-xi-tong-ji-ben-yuan-li/11linux-cao-zuo-xi-tong-li-jie-cpu-shang-xia-wen-qie-huan\.md\)', '(linux-cao-zuo-xi-tong-ji-ben-yuan-li/12linux-cao-zuo-xi-tong-li-jie-cpu-shang-xia-wen-qie-huan.md)'),
    # 12 -> 13
    (r'\(linux-cao-zuo-xi-tong-ji-ben-yuan-li/12linux-nei-he-diao-shi-yu-xing-neng-fen-xi\.md\)', '(linux-cao-zuo-xi-tong-ji-ben-yuan-li/13linux-nei-he-diao-shi-yu-xing-neng-fen-xi.md)'),
]

for old, new in replacements:
    content = re.sub(old, new, content)

# 2. 在 04 之后插入新的 05
old_line = '* [04-Linux操作系统学习——内核初始化](linux-cao-zuo-xi-tong-ji-ben-yuan-li/04linux-cao-zuo-xi-tong-xue-xi-nei-he-chu-shi-hua.md)'
new_line = old_line + '\n* [05-Linux内核IO基础知识与概念](linux-cao-zuo-xi-tong-ji-ben-yuan-li/05linux-nei-he-io-ji-chu-zhi-shi-yu-gai-nian.md)'
content = content.replace(old_line, new_line)

# 3. 删除 Linux进程管理 中的 02
old_process_io = '* [02-Linux内核IO基础知识与概念](linux-jin-cheng-guan-li/02linux-nei-he-io-ji-chu-zhi-shi-yu-gai-nian.md)\n'
content = content.replace(old_process_io, '')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("SUMMARY.md updated successfully")
