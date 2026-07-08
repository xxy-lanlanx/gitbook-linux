# 08-Linux 缺页中断与 OOM

> 基于 Linux 3.10.29 内核分析。本章先讲进程访问内存时最常见的「缺页中断（Page Fault）」如何按需建立映射，再讲内存耗尽时内核的「OOM Killer」如何选择并终止进程以保命。

## 1. 缺页中断（Page Fault）概述

进程使用虚拟地址，页表把虚拟页映射到物理页。当 CPU 访问的虚拟页**尚未建立有效映射**时，MMU 触发缺页异常，陷入内核 `do_page_fault()` 处理。

```text
CPU 访问虚拟地址 va
   │ 页表项无效 / 权限不符
   ▼
MMU 触发缺页异常（page fault）
   │
   ▼
do_page_fault() 判定原因 → 处理
   ├── 匿名页缺页（首次访问堆/栈）→ 分配物理页
   ├── 文件页缺页（访问 mmap 文件）→ 从磁盘读入 page cache
   ├── 写时复制缺页（COW，写只读页）→ 复制新页，改为可写
   └── 非法访问（内核/未映射区）→ SIGSEGV 终止进程
```

### 1.1 缺页类型

- **Minor（次要）缺页**：所需页已在内存（如 page cache、COW），无需磁盘 I/O，仅建立映射；
- **Major（主要）缺页**：所需页不在内存，需从磁盘（文件/ swap）读入，开销大；
- **Invalid（非法）缺页**：访问越界或权限错误，内核向进程发 `SIGSEGV`。

### 1.2 写时复制（COW）缺页

`fork()` 后父子共享只读页。任一方写入触发 COW 缺页：`do_wp_page()` 分配新物理页、复制内容、把写者页表项改为可写。这正是 `fork` 高效的原因（详见进程管理 08 章）。

### 1.3 请求调页（Demand Paging）

Linux 采用**按需调页**：`mmap`/`exec` 只建立虚拟区间，不立即读入文件；真正访问时才缺页，从磁盘装入 page cache。这样程序启动快、内存利用率高。

### 1.4 do_page_fault 关键流程（简化）

```c
void do_page_fault(struct mm_struct *mm, unsigned long addr, ...) {
    vma = find_vma(mm, addr);        /* 找到地址所在虚拟内存区 */
    if (!vma || 越界) goto bad_area; /* 非法访问 */
    if (写 && vma 只读) handle_wp_page();   /* COW */
    else if (文件映射) filemap_fault();     /* 文件页 */
    else alloc_zeroed_page();                /* 匿名页 */
}
```

## 2. 内存耗尽与 OOM Killer

当系统**物理内存 + swap 都不足**，且伙伴系统分配失败、回收（page reclaim）也无果时，内核触发 **OOM Killer（Out-Of-Memory）**，选择一个进程杀掉以释放内存，避免整个系统挂死。

### 2.1 触发路径

```text
分配失败 → 内存回收(kswapd/direct reclaim) 仍失败
   → out_of_memory()
        ├── 选择 victim（badness 评分最高）
        └── oom_kill_process() → 发 SIGKILL
```

### 2.2 选择算法：badness 评分

`oom_badness()` 给每个进程打分，分数越高越容易被杀。评分依据：
- 进程占用物理内存越多 → 分越高（杀掉能释放更多内存）；
- `oom_score_adj`（可控权重）影响最终分；
- 特权进程（`CAP_SYS_ADMIN`）会被适当「保护」；
- `init`（pid=1）与内核线程不会被选。

```c
/* 简化思路 */
points = 进程物理内存页数;
points += 已有子进程内存（考虑连带收益）;
points -= oom_score_adj 调整;
```

### 2.3 观察与调优

```bash
# 查看某进程的 OOM 评分（0~1000，越大越危险）
cat /proc/<pid>/oom_score

# 查看可调权重（-1000 ~ 1000；设为 -1000 表示永不被 OOM 杀）
cat /proc/<pid>/oom_score_adj

# 保护关键进程（如数据库）
echo -500 > /proc/<pid>/oom_score_adj

# OOM 行为配置
sysctl vm.panic_on_oom=0   # 0=杀进程(默认)，1=直接 panic
sysctl vm.oom_kill_allocating_task=0
```

### 2.4 内核日志中的 OOM 信息

OOM 触发时，`dmesg` 会打印被杀进程、内存使用、badness 明细：

```text
Out of memory: Kill process 8842 (java) score 612 or sacrifice child
Killed process 8842 (java) total-vm:8192000kB, anon-rss:6100000kB
```

### 2.5 cgroup 中的 OOM

在 进程管理 06 章提到的 cgroup 里，若某组内存超限（`memory.max`），该组内部触发 OOM，**只杀组内进程**，不影响系统其他部分——容器场景中常见。

## 3. 小结

- **缺页中断**是「虚拟内存按需建立映射」的核心机制，区分 minor/major/非法三类，是进程高效使用内存的基础；
- **OOM Killer** 是内核的最后防线：内存彻底耗尽时，按 badness 选最「划算」的进程 `SIGKILL`，并通过 `oom_score_adj` 提供可控保护。

两者一前一后，共同保障了 Linux 内存在「按需分配」与「极端保命」之间的平衡。
