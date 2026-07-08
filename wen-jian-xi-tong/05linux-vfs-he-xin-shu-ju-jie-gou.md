# 05-Linux VFS 核心数据结构

> 基于 Linux 3.10.29 内核分析。Linux 同时支持几十种文件系统（ext4、xfs、btrfs、tmpfs、proc…）。用户程序却只用一套 `open/read/write` 接口——其背后是**虚拟文件系统（VFS）** 提供的统一抽象层。本章拆解 VFS 的四个核心对象。

## 1. VFS 的作用

```text
用户程序
   │ open/read/write  (统一 POSIX 接口)
   ▼
┌─────────────┐
│    VFS      │  ← 统一抽象：file/inode/dentry/super_block
└─────────────┘
   │ 通过函数指针调用具体文件系统
   ▼
ext4 / xfs / proc / tmpfs ...  (具体实现)
```

VFS 定义了一组「接口」（结构体里的函数指针），每种文件系统提供自己的实现，从而屏蔽差异。

## 2. 四大核心对象

```text
super_block  ──1:N──> inode  ──1:N──> dentry
   (文件系统超级块)      (文件元数据)    (目录项/路径分量)
                              │
                              └──1:1──> file (进程打开的文件)
```

### 2.1 super_block：已挂载文件系统的超级块

描述一个**已挂载的文件系统实例**：

```c
struct super_block {
    struct list_head s_list;        /* 所有超级块链表 */
    dev_t s_dev;                    /* 设备号 */
    unsigned long s_blocksize;      /* 块大小 */
    struct dentry *s_root;          /* 根目录项 */
    const struct super_operations *s_op;  /* 操作函数 */
    ...
};
```

`super_operations` 定义 inode 分配/销毁、同步等：

```c
struct super_operations {
    struct inode *(*alloc_inode)(struct super_block *);
    void (*destroy_inode)(struct inode *);
    int (*write_inode)(struct inode *, ...);
    void (*put_super)(struct super_block *);
    ...
};
```

### 2.2 inode：文件的元数据

`inode` 是**文件在磁盘/内存中的身份**，一个文件（无论是否被打开）对应一个 inode（不考虑硬链接共享）：

```c
struct inode {
    umode_t i_mode;          /* 文件类型+权限 */
    uid_t i_uid; gid_t i_gid; /* 属主 */
    loff_t i_size;           /* 文件大小 */
    struct inode_operations *i_op;  /* 创建/查找/链接 */
    struct file_operations  *i_fop; /* 默认文件操作 */
    struct address_space *i_mapping;/* 页缓存映射（见 06 章） */
    void *i_private;         /* 文件系统私有数据 */
    ...
};
```

> 注意：inode **不含文件名**。文件名存在于目录项 dentry 中。

### 2.3 dentry：目录项（路径分量）

`dentry` 表示路径中的一个分量（如 `/usr/bin` 中的 `usr`、`bin`），用于**快速路径查找**并建立文件名→inode 的缓存：

```c
struct dentry {
    struct dentry *d_parent;     /* 父目录项 */
    struct inode *d_inode;       /* 指向对应 inode（若为负 dentry 则为 NULL） */
    struct qstr d_name;          /* 分量名（如 "bin"） */
    struct dentry_operations *d_op;
    ...
};
```

- **正 dentry**：有对应 inode；
- **负 dentry**：文件不存在的缓存，避免反复查盘确认「不存在」；
- dentry 由内核**缓存**（dcache），加速 `open()` 路径解析。

### 2.4 file：进程打开的文件

每次 `open()` 成功，内核创建一个 `file`，描述「进程视角的打开实例」：

```c
struct file {
    struct path f_path;          /* 对应 dentry + 挂载点 */
    struct inode *f_inode;
    const struct file_operations *f_op;  /* read/write/open/... */
    loff_t f_pos;                /* 当前读写偏移 */
    atomic_long_t f_count;       /* 引用计数（dup/ fork 共享） */
    unsigned int f_flags;        /* O_RDONLY/O_APPEND... */
    void *private_data;          /* 驱动/文件系统私有 */
};
```

同一文件被多个进程打开 → 多个 `file`，但共享同一个 `inode`。

## 3. 关键操作集

```c
struct inode_operations {            /* 对「文件本身」的操作 */
    struct dentry *(*lookup)(struct inode *, struct dentry *, unsigned int);
    int (*create)(struct inode *, struct dentry *, umode_t, bool);
    int (*link)(struct dentry *, struct inode *, struct dentry *);
    int (*unlink)(struct inode *, struct dentry *);
    ...
};

struct file_operations {            /* 对「打开的文件」的操作 */
    loff_t (*llseek)(struct file *, loff_t, int);
    ssize_t (*read)(struct file *, char __user *, size_t, loff_t *);
    ssize_t (*write)(struct file *, const char __user *, size_t, loff_t *);
    int (*open)(struct inode *, struct file *);
    int (*release)(struct inode *, struct file *);
    ...
};
```

## 4. 路径查找（Path Lookup）简述

`open("/usr/bin/ls", O_RDONLY)` 时，VFS 自根 dentry 起逐级解析：

```text
/ → usr → bin → ls
 dentry  dentry dentry dentry
   │        │      │      └─> 找到 ls 的 inode
   │        │      └─> 在 bin 目录中查找 "ls"
   │        └─> 在 usr 目录中查找 "bin"
   └─> 从 root dentry 开始
```

- 优先查 **dcache（dentry 缓存）**，命中则免磁盘；
- 未命中则调用父目录 inode 的 `lookup()`，由具体文件系统去磁盘找；
- 解析成功后得到 `dentry + inode`，构造 `file` 返回 fd。

## 5. 挂载（mount）如何让多个文件系统连成树

`mount /dev/sda1 /mnt` 时，VFS 把 sda1 的 `super_block` 与 `s_root` 挂到目录树某 dentry 上，形成「挂载点」。路径查找跨过挂载点时，会切换到被挂文件系统的根 dentry——对用户透明，看到的是统一目录树。

## 6. 小结

VFS 用 `super_block`（文件系统）、`inode`（文件身份）、`dentry`（路径缓存）、`file`（打开实例）四个对象，配合 `inode_operations`/`file_operations` 函数指针，把千差万别的文件系统统一成同一套 `open/read/write`。理解这四者是读懂 Linux 文件系统一切行为的钥匙。
