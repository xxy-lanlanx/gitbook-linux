import re, sys
sys.path.insert(0, 'e:/doc/gitbook/gitbook-linux/scripts')
import test_fix2 as t

cases = [
    '0 ?64K',
    '除（0 ?64K - 1 I/O 端口之外（40',
    '传送方向（?I/O 设备读或写到 I/O 设备）',
    '队列（?1 \\~ (i-1)中的任何一个',
    '只能识（0 ?1 这样的机器代码',
    '如 Read ?Write 命令',
    'fd2\\[0] ?fd2\\[1]）；',
    '给 PID ?1111 的进程发',
    'fair\\_clock ?wait\\_runtime',
    'CFS组调度（?2.6.24 内核中引入',
    'bitmap ?queue）',
    '（10 ?RT 进程同时',
    'BFS 103 ?bitmap 来表示',
    '（bitmap ?queue 的复杂结构',
    '（SCHED\\_NORMAL ?bit 被置位',
    '?\\_\\_down\\_common() 函',
]
for s in cases:
    print('IN :', repr(s))
    print('OUT:', repr(t.fix_text(s)))
    print('ord of ? in s:', [ord(c) for c in s if c == '?'])
    print()

# direct rule 5 test
print('rule5 direct:', repr(re.sub(r'([a-zA-Z0-9%])\?([a-zA-Z0-9])', r'\1 \2', '0 ?64K')))
