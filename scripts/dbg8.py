import sys
sys.path.insert(0, 'e:/doc/gitbook/gitbook-linux/scripts')
import fix_encoding_clean as c

tests = [
    '内存映射射\ufffd?I/O 的数据缓冲区',
    '磁盘到\ufffd?内核缓冲区 用户空间',
    '应用程序调用\ufffd?write',
    '内核代码运行的地方\ufffd?_。',
]
out = []
for s in tests:
    out.append('IN : ' + repr(s))
    out.append('OUT: ' + repr(c.fix_text(s)))
    out.append('')
with open('e:/doc/gitbook/gitbook-linux/scripts/dbg8_out.txt', 'w', encoding='utf-8') as fp:
    fp.write('\n'.join(out))
