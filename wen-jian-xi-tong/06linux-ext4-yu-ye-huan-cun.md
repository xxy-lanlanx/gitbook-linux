# 06-Linux ext4 与页缓存

> 基于 Linux 3.10.29 内核分析。上一章讲了 VFS 的统一抽象，本章落到「具体文件系统」：以主流的 **ext4** 为例看磁盘布局，并讲清 **页缓存（page cache）** 如何让文件读写飞快。

## 1. ext4 简介

ext4（Fourth Extended Filesystem）是 Linux 上最常用的事务型日志文件系统，相较 ext2/ext3 的关键改进：
- **Extents**（区）：用「起始块+长度」描述连续空间，替代 ext2 的间接块，大文件更高效；
- **日志（Journal）**：先把元数据改动写进日志，崩溃后可快速恢复，避免 fsck 全盘扫描；
- **延迟分配、多块分配**：减少碎片；
- 支持大文件（TB 级）与大卷。

## 2. 磁盘布局

```text
[ 引导块 ][ 块组0 ][ 块组1 ] ... [ 块组N ]
 块组结构：
 ┌─────────────┬──────────┬──────────┬──────────┬─────────┐
 │ superblock  │ GDT      │ block    │ inode    │ data    │
 │ (超级块)    │ (组描述) │ bitmap   │ bitmap   │ blocks  │
 │             │          │ (块位图) │ (inode位图)│ (数据) │
 └─────────────┴──────────┴──────────┴──────────┴─────────┘
```

- **superblock**：文件系统全局信息（总块数、inode 数、块大小、挂载次数）；
- **GDT（组描述符表）**：每个块组的起止信息；
- **block bitmap / inode bitmap**：位图，标记块/inode 是否空闲；
- **inode table**：存放本组所有 inode；
- **data blocks**：真正存放文件内容。

### 2.1 inode 磁盘结构（简化）

```c
struct ext4_inode {
    __le16 i_mode;        /* 类型+权限 */
    __le32 i_size_lo;     /* 文件大小(低32) */
    __le32 i_blocks;      /* 占用的 512B 扇区数 */
    __le32 i_block[EXT4_N_BLOCKS]; /* 数据块指针 */
};
```

`i_block` 前 12 个是**直接块**，之后是**间接/二级/三级块**（ext2 方式）；ext4 默认用 **extent 树**存储于 `i_block`，更紧凑。

## 3. 日志（Journal）与崩溃恢复

写文件时：

```text
1) 先把元数据操作记入 journal 区（write-ahead）
2) 提交事务标记（commit 记录）
3) 再把数据真正写入数据块
崩溃重启 → 检查 journal：
   未提交 → 丢弃
   已提交 → 重放(redo)，保证一致性，无需全盘 fsck
```

```bash
dmesg | grep -i ext4     # 查看 ext4 挂载/恢复信息
tune2fs -l /dev/sda1     # 查看文件系统参数（含 has_journal）
```

## 4. 页缓存（Page Cache）

如果每次 `read()` 都走磁盘，速度不可接受。Linux 用**页缓存**把文件内容缓存在物理内存的页中：

```text
read(fd, buf, n)
   │
   ▼
VFS → 地址空间(address_space) 查找页缓存
   ├─ 命中（page in cache）→ 直接拷贝到用户 buf（快）
   └─ 未命中（page fault）  → 从磁盘读入页缓存，再拷贝
```

### 4.1 address_space 与页

每个 `inode` 关联一个 `address_space`，管理该文件所有缓存页：

```c
struct address_space {
    struct inode *host;          /* 所属 inode */
    struct radix_tree_root page_tree;  /* 页缓存索引（按偏移） */
    const struct address_space_operations *a_ops; /* 读/写页 */
    ...
};

struct page {                    /* 缓存中的一页文件内容 */
    ... 通过 page->index 表示在文件中的偏移
};
```

- `a_ops->readpage`：从磁盘读一页进缓存；
- `a_ops->writepage`：把脏页写回磁盘。

### 4.2 写回（Write-back）

写文件通常**先写到页缓存**（标记为脏），并不立即落盘：

```c
write(fd, buf, n)
   → 拷贝进页缓存，标记 PG_dirty
   → 立即返回（快）
```

脏页由以下时机写回磁盘：
- 周期性：`pdflush`/`flusher` 线程按 `dirty_expire_centisecs` 刷盘；
- 阈值：脏页占比超 `dirty_ratio` 时阻塞写者强制刷盘；
- 显式：`sync` / `fsync(fd)` / `msync`。

```bash
sysctl vm.dirty_ratio          # 脏页占可用内存比例上限（默认 20）
sysctl vm.dirty_expire_centisecs
sync                           # 强制写回所有脏页
```

> 这解释了「`cp` 后立刻断电可能丢数据」——除非 `fsync`。数据库等场景必须用 `fsync`/`O_SYNC`。

### 4.3 页缓存的收益

- **读加速**：重复读同一文件命中缓存；
- **写合并**：多次小写合并成一次大块写盘；
- **共享**：多个进程 `mmap` 同一文件共享同一物理页（参见 内存管理 05 章 mmap）。

## 5. 小结

ext4 用超级块/块组/位图/inode + extent 组织磁盘，并用 journal 保证崩溃一致性；页缓存则在 VFS 与磁盘之间架起内存缓冲，让文件 I/O 兼具速度与一致性。理解「页缓存 + 延迟写回」是排查 I/O 性能与数据安全问题的基础。
