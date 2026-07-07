import re

filepath = r"e:\doc\gitbook\gitbook-linux\SUMMARY.md"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update Linux操作系统基本原理 paths
replacements = [
    (r'\(linux-cao-zuo-xi-tong-ji-ben-yuan-li/05linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li\.md\)', '(linux-cao-zuo-xi-tong-ji-ben-yuan-li/06linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li.md)'),
    (r'\(linux-cao-zuo-xi-tong-ji-ben-yuan-li/06linux-cao-zuo-xi-tong-chu-li-qi-diao-du-ji-ben-zhun-ze-he-shi-xian\.md\)', '(linux-cao-zuo-xi-tong-ji-ben-yuan-li/07linux-cao-zuo-xi-tong-chu-li-qi-diao-du-ji-ben-zhun-ze-he-shi-xian.md)'),
    (r'\(linux-cao-zuo-xi-tong-ji-ben-yuan-li/07linux-nei-he-cao-zuo-xi-tong-yuan-li-yu-gai-shu\.md\)', '(linux-cao-zuo-xi-tong-ji-ben-yuan-li/08linux-nei-he-cao-zuo-xi-tong-yuan-li-yu-gai-shu.md)'),
    (r'\(linux-cao-zuo-xi-tong-ji-ben-yuan-li/11linux-cao-zuo-xi-tong-li-jie-cpu-shang-xia-wen-qie-huan\.md\)', '(linux-cao-zuo-xi-tong-ji-ben-yuan-li/12linux-cao-zuo-xi-tong-li-jie-cpu-shang-xia-wen-qie-huan.md)'),
]

for old, new in replacements:
    content = re.sub(old, new, content)

# 2. Update titles in Linux操作系统基本原理
content = content.replace('* [05-Linux操作系统IO机制原理]', '* [06-Linux操作系统IO机制原理]')
content = content.replace('* [06-Linux操作系统处理器调度基本准则和实现]', '* [07-Linux操作系统处理器调度基本准则和实现]')
content = content.replace('* [07-Linux内核操作系统原理与概述]', '* [08-Linux内核操作系统原理与概述]')
content = content.replace('* [11-Linux操作系统理解CPU上下文切换]', '* [12-Linux操作系统理解CPU上下文切换]')

# 3. Insert new 05 in Linux操作系统基本原理
old_line = '* [04-Linux操作系统学习——内核初始化](linux-cao-zuo-xi-tong-ji-ben-yuan-li/04linux-cao-zuo-xi-tong-xue-xi-nei-he-chu-shi-hua.md)'
new_line = old_line + '\n* [05-Linux内核IO基础知识与概念](linux-cao-zuo-xi-tong-ji-ben-yuan-li/05linux-nei-he-io-ji-chu-zhi-shi-yu-gai-nian.md)'
content = content.replace(old_line, new_line)

# 4. Remove 02 from Linux进程管理
old_process_io = '* [02-Linux内核IO基础知识与概念](linux-jin-cheng-guan-li/02linux-nei-he-io-ji-chu-zhi-shi-yu-gai-nian.md)\n'
content = content.replace(old_process_io, '')

# 5. Renumber Linux进程 management
content = content.replace('* [03-Linux内核六大进程通信机制原理]', '* [02-Linux内核六大进程通信机制原理]')
content = content.replace('* [04-Linux内核Socket通信原理]', '* [03-Linux内核Socket通信原理]')
content = content.replace('* [05-Linux内核进程的管理与调度]', '* [04-Linux内核进程的管理与调度]')
content = content.replace('* [06-Linux内核进程管理并发同步与原子操作]', '* [05-Linux内核进程管理并发同步与原子操作]')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("SUMMARY.md updated")
