# 09-TLB、页表遍历与 NUMA 架构

## 一、TLB 为什么如此重要

在现代处理器中，虚拟地址到物理地址的转换由**内存管理单元（MMU）**通过**页表遍历（Page Table Walk）**完成。但页表通常存放在内存中，如果每次访存都要先读内存查页表，就会变成“为了读内存而读内存”的递归瓶颈。

**TLB（Translation Lookaside Buffer）**是 CPU 内部的高速缓存，专门用于缓存最近用过的虚拟地址→物理地址映射。它的命中延迟通常只有 **1-2 个时钟周期**，而页表遍历（尤其是多级页表）需要 **20-100+ 个时钟周期**。

| 场景 | 延迟 | 影响 |
|------|------|------|
| TLB 命中 | 1-2 cycles | 几乎无感知 |
| L1 缓存命中 | 4-5 cycles | 正常 |
| TLB 未命中 | 20-100+ cycles | 严重性能回退 |
| 跨 NUMA 节点 | 200-300+ cycles | 灾难性 |

## 二、TLB 的组织与类型

### 1. 架构相关 TLB 类型

| 类型 | 描述 | x86 示例 |
|------|------|----------|
| uTLB / dTLB | 指令/数据 TLB 分离 | ITLB4K、DTLB4K |
| STLB | 二级 TLB，容量更大 | STLB (1536 entries) |
| HugeTLB | 大页 TLB | ITLB2M、DTLB2M |

以 Intel Ice Lake 为例：
- L1 DTLB: 64 entries (4K page), 32 entries (2M page)
- L2 STLB: 1536 entries (4K/2M page)
- L1 ITLB: 128 entries (4K page), 8 entries (2M page)

### 2. TLB 条目结构

```c
// 概念性结构（实际由硬件实现）
struct tlb_entry {
    uint64_t vpn;        // 虚拟页号（Tag）
    uint64_t ppn;        // 物理页号（Data）
    uint16_t asid;       // Address Space ID，区分不同进程
    uint8_t  page_size;  // 4K / 2M / 1G
    uint8_t  flags;      // R/W/X, Global, Dirty, Accessed
};
```

**ASID（Address Space ID）**的存在让 TLB 在上下文切换时无需完全刷新——只需切换 ASID 标签即可。Linux 通过 `CONFIG_CPU_HAS_ASID` 启用此优化。

## 三、多级页表与页表遍历

### 1. x86-64 的四级页表

x86-64 使用 **4-level paging**（5-level 已支持）：

```
CR3 → PML4 → PDP → PD → PT → Physical Page
  512    512    512   512   4K

虚拟地址划分：
[47:39] [38:30] [29:21] [20:12] [11:0]
 PML4i   PDPi    PDi     PTi    Offset
```

一次完整的页表遍历需要 **4 次内存读取**（PML4 → PDP → PD → PT），每次读取都可能缓存未命中，代价极高。

### 2. 内核中的页表遍历函数

Linux 内核提供了 `follow_page()` 系列函数用于遍历页表：

```c
// mm/gup.c
struct page *follow_page(struct vm_area_struct *vma,
                         unsigned long address,
                         unsigned int foll_flags)
{
    pgd_t *pgd;
    p4d_t *p4d;
    pud_t *pud;
    pmd_t *pmd;
    pte_t *ptep, pte;

    pgd = pgd_offset(vma->vm_mm, address);
    if (pgd_none(*pgd) || pgd_bad(*pgd))
        return NULL;

    p4d = p4d_offset(pgd, address);
    // ... 逐级向下遍历
    pmd = pmd_offset(pud, address);
    if (pmd_trans_huge(*pmd)) {
        // 透明大页（THP）优化
        return follow_trans_huge_pmd(vma, address, pmd, foll_flags);
    }

    ptep = pte_offset_map(pmd, address);
    pte = *ptep;
    // 提取物理页框
    return pte_page(pte);
}
```

### 3. 页表遍历优化：硬件页遍历器

现代 CPU 内置了 **硬件页表遍历器（Page Table Walker）**，可以自动完成 TLB miss 时的页表遍历，无需操作系统介入。但遍历结果仍需要多次内存访问，因此软件层面的优化（如大页）依然至关重要。

## 四、大页（HugePage）与 TLB 效率

### 1. 为什么大页能提升 TLB 效率

| 页大小 | 覆盖内存 | TLB 256 entries 覆盖 |
|--------|----------|---------------------|
| 4K | 4K × 256 = 1 MB | 很小 |
| 2M | 2M × 256 = 512 MB | 中等 |
| 1G | 1G × 256 = 256 GB | 很大 |

对于 64GB 内存的数据库，如果使用 4K 页，需要覆盖 16M 个页表项；而使用 1G 大页，只需要 64 个页表项。

### 2. Linux 大页机制

| 机制 | 配置方式 | 特点 |
|------|----------|------|
| 静态 HugeTLB | `sysctl vm.nr_hugepages=256` | 启动时预留，必须显式使用 |
| 透明大页 THP | `/sys/kernel/mm/transparent_hugepage/enabled` | 自动合并/拆分，对用户透明 |
| 1G HugePage | `hugetlbfs` + 1G 参数 | 需要内核支持，用于 DPDK/HPC |

**THP 内部实现**：

```c
// mm/huge_memory.c
int hugepage_vma_check(struct vm_area_struct *vma,
                       unsigned long vm_flags)
{
    // 检查 VMA 是否适合 THP
    if (vma->vm_flags & VM_NOHUGEPAGE)
        return 0;  // 显式禁用

    // 匿名映射 + 可写 + 足够大，自动使用 THP
    if (!vma_is_anonymous(vma) || !(vm_flags & VM_WRITE))
        return 0;

    return 1;  // 启用 THP
}
```

**THP 的缺点**：THP 合并需要内存整理（compaction），可能造成短暂延迟。对于延迟敏感场景，可以关闭 THP：

```bash
echo never > /sys/kernel/mm/transparent_hugepage/enabled
```

## 五、NUMA 架构与内存局部性

### 1. NUMA 的物理拓扑

在 NUMA（Non-Uniform Memory Access）系统中，每个 CPU 插槽（Socket）拥有本地内存控制器和本地内存：

```
Socket 0          Socket 1          Socket 2
┌────────┐        ┌────────┐        ┌────────┐
│ Core 0 │        │ Core 4 │        │ Core 8 │
│ Core 1 │        │ Core 5 │        │ Core 9 │
│  ...   │        │  ...   │        │  ...   │
│ Memory0│        │ Memory1│        │ Memory2│
└────────┘        └────────┘        └────────┘
    │                  │                  │
    └────── QPI/UPI ──┴────── QPI/UPI ──┘

本地访问延迟：~80ns
跨 Socket 访问延迟：~200-300ns
```

### 2. Linux 的 NUMA 内存策略

| 策略 | 含义 | API |
|------|------|-----|
| `MPOL_DEFAULT` | 本地优先分配 | 默认 |
| `MPOL_BIND` | 强制绑定到指定节点 | `mbind()` + `MPOL_BIND` |
| `MPOL_INTERLEAVE` | 轮询分配到所有节点 | `mbind()` + `MPOL_INTERLEAVE` |
| `MPOL_PREFERRED` | 优先指定节点，允许回退 | `mbind()` + `MPOL_PREFERRED` |

```c
#include <numa.h>

// 将当前进程的内存绑定到 NUMA 节点 0
void *addr = mmap(NULL, size, PROT_READ|PROT_WRITE,
                  MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
unsigned long nodemask = 1UL << 0;  // node 0
mbind(addr, size, MPOL_BIND, &nodemask, 8, 0);
```

### 3. NUMA 平衡机制

Linux 内核在 `mm/mempolicy.c` 和 `mm/numa.c` 中实现了 NUMA 自动平衡：

```c
// mm/numa.c
void task_numa_work(struct callback_head *work)
{
    struct task_struct *p = current;
    struct mm_struct *mm = p->mm;

    // 采样页面访问，统计本地/远程访问比例
    for (vma = mm->mmap; vma; vma = vma->vm_next) {
        if (vma->vm_start > mm->numa_next_scan)
            continue;

        // 如果页面被远程节点频繁访问，触发页面迁移
        migrate_misplaced_page(page, nid);
    }
}
```

**自动 NUMA 平衡** (`numa_balancing`) 会在运行时监测页面访问模式，将页面从远程节点迁移到本地节点，但迁移本身有开销。

```bash
# 查看 NUMA 状态
numactl --hardware
numastat -m

# 查看进程 NUMA 分布
cat /proc/12345/numa_maps
```

## 六、实际调优案例

### 场景：MySQL 数据库在 2-Socket NUMA 服务器上性能异常

**症状**：单实例 MySQL 的 QPS 波动大，延迟 99th percentile 高达 50ms。

**诊断**：

```bash
numactl --hardware
# 显示 2 个 NUMA 节点，Node 0 和 Node 1

numastat -m
# 显示 Node 1 的 `other_node` 极高，说明大量跨节点访问

perf stat -e uncore_imc/clockticks/ -a sleep 10
# 内存控制器频率波动，说明远端访问
```

**根因**：MySQL 进程被调度器在 Node 0 和 Node 1 之间迁移，导致内存频繁跨节点访问。

**解决方案**：

```bash
# 1. 将 MySQL 绑定到 NUMA Node 0 的 CPU
numactl --cpunodebind=0 --membind=0 mysqld &

# 2. 或者使用 interleave 策略均匀分布内存
numactl --interleave=all mysqld &

# 3. 在 MySQL 配置中启用大页
innodb_large_prefix = 1
innodb_buffer_pool_size = 48G  # 配合 2M HugePage
```

**结果**：P99 延迟从 50ms 降到 5ms，QPS 提升 40%。

## 七、总结

| 技术 | 解决的问题 | 关键参数/工具 |
|------|-----------|-------------|
| TLB | 地址转换加速 | `perf stat -e dTLB-loads-misses` |
| 大页 | TLB 覆盖范围 | `nr_hugepages`, THP, `hugetlbfs` |
| ASID | 上下文切换 TLB 刷新 | `CONFIG_CPU_HAS_ASID` |
| NUMA 绑定 | 内存局部性 | `numactl`, `mbind()`, `cpunodebind` |
| NUMA 平衡 | 自动页面迁移 | `numa_balancing` sysctl |

内存性能优化的核心口诀：**“查 TLB、用大页、绑 NUMA”**。在延迟敏感和大数据量场景中，这三项往往决定了系统的整体表现。
