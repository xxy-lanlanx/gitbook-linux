# 07-Linux 伙伴系统与 slab 分配器

> 基于 Linux 3.10.29 内核分析。内核管理物理内存分两层：底层用**伙伴系统（Buddy System）**分配以「页」为单位的连续物理内存，上层用 **slab 分配器**在页内切割小块对象，满足内核高频的小对象分配需求。

## 1. 物理页与页帧

物理内存按 **页（page frame）** 管理，典型页大小 4 KiB（由 `PAGE_SIZE` 决定）。内核用 `struct page` 描述每一页：

```c
struct page {
    unsigned long flags;     /* 页状态：空闲/脏/锁等 */
    atomic_t _count;         /* 引用计数 */
    struct list_head lru;    /* 用于伙伴系统空闲链表 */
    ...
};
```

所有 `page` 组成全局数组 `mem_map[]`，由 `pfn_to_page()` / `page_to_pfn()` 在页帧号（PFN）与 `page` 间转换。

## 2. 伙伴系统（Buddy System）

### 2.1 设计目标

解决**外部碎片**：频繁分配/释放不同大小的连续内存，会让空闲内存变得零散，导致无法满足大块连续请求。伙伴系统以 **2 的幂次（order）** 块为单位管理空闲页。

- 每个 order `k` 对应大小为 `2^k` 个连续页；
- 内核为每类（按迁移类型 `MIGRATE_TYPES`）维护 11 个 order 的空闲链表（`free_area[0..10]`）。

### 2.2 分配与释放

分配 `2^k` 页时：
1. 若 `free_area[k]` 非空，摘下一块返回；
2. 否则从更大的 `k+1` 块中**分裂**为两个「伙伴」，一块返回，另一块挂入 `free_area[k]`；
3. 若更大块也没有，继续向上分裂，直到 `MAX_ORDER` 失败则返回 `NULL`。

释放时：检查「伙伴」是否也空闲，若是则**合并**成 `2^(k+1)` 块，递归向上合并。

```c
/* 分配 1 页（order 0） */
struct page *p = alloc_page(GFP_KERNEL);
/* 分配 2^order 页 */
struct page *p = alloc_pages(GFP_KERNEL, order);
/* 转成虚拟地址 */
void *vaddr = page_address(p);
/* 释放 */
__free_pages(p, order);
```

### 2.3 GFP 分配标志

```c
GFP_KERNEL      /* 普通内核分配，可睡眠（阻塞） */
GFP_ATOMIC      /* 原子上下文（中断/软中断）使用，不睡眠 */
GFP_USER        /* 为用户空间分配 */
__GFP_DMA       /* 限定 DMA 区（<16MB） */
__GFP_HIGHMEM   /* 允许高端内存 */
```

### 2.4 分区页框分配器（Per-CPU / Per-Zone）

为减少锁竞争与提升热缓存命中，伙伴系统上层有：
- **Per-CPU 页框高速缓存**：小额分配直接从 CPU 本地缓存取，避免频繁加锁；
- **Zone（区）**：`ZONE_DMA` / `ZONE_NORMAL` / `ZONE_HIGHMEM`，按物理地址范围划分。

## 3. slab 分配器

伙伴系统的最小粒度是一页，但内核大量需要几十/几百字节的小对象（如 `inode`、`task_struct`、`skbuff`）。若每次都取整页会极浪费，slab 分配器在页内**对象缓存**解决此问题。

### 3.1 三级结构

```text
slab 分配器
  └── kmem_cache（一类对象的缓存，如 "inode_cache"）
        └── slab（由一个或多个物理页组成）
              └── object（被缓存的对象，已构造/待分配）
```

### 3.2 接口

```c
#include <linux/slab.h>

/* 1) 创建专用缓存 */
struct kmem_cache *my_cache =
    kmem_cache_create("my_obj", sizeof(struct my_obj), 0, 0, NULL);

/* 2) 从缓存分配对象 */
struct my_obj *o = kmem_cache_alloc(my_cache, GFP_KERNEL);

/* 3) 释放回缓存（不立即还给伙伴系统） */
kmem_cache_free(my_cache, o);

/* 4) 销毁缓存 */
kmem_cache_destroy(my_cache);
```

### 3.3 通用分配：kmalloc / kfree

最常见的小块分配用 `kmalloc()`，底层依据大小选择对应的通用 `kmalloc` 缓存（如 8/16/32/…/8192 字节）：

```c
void *buf = kmalloc(256, GFP_KERNEL);   /* 分配 256 字节，物理连续 */
memcpy(buf, src, 256);
kfree(buf);                              /* 释放 */
```

> `kmalloc` 返回的内存**物理连续**，适合 DMA；若不需物理连续，可用 `vmalloc()`（仅虚拟连续）。

### 3.4 slab、slub、slob

- **slab**：经典实现，对象缓冲+着色减少缓存冲突；
- **slub**（默认）：更简洁高效，开销小，3.10 默认启用；
- **slob**：为极度受限的嵌入式/小内存设备设计。

### 3.5 着色（Coloring）

slab 给不同 slab 中的对象加上不同**偏移（着色）**，使对象在 CPU 缓存中的行分布错开，减少**缓存行冲突（cache thrashing）**，提升缓存命中率。

## 4. 总结：两级内存分配的分工

```text
用户/内核模块
     │ kmalloc / kmem_cache_alloc（小块，对象级）
     ▼
 slab 分配器（页内切割，对象缓存）
     │ 需要新页时
     ▼
 伙伴系统（页级，2^order 连续块，处理外部碎片）
     │
     ▼
 物理页框（page）
```

理解伙伴系统解决「页级连续分配与碎片」，slab 解决「小对象高频分配效率」，才能读懂内核内存分配的全貌。
