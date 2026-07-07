# 03-Linux 块设备驱动

> 块设备（Block Device）是 Linux 中以"块"（通常 512B ~ 4KB）为单位进行随机访问的设备。硬盘、SSD、U盘、SD 卡等都属于块设备。理解块设备驱动，是理解 Linux IO 子系统的核心。

## 1. 块设备与字符设备的区别

| 特性 | 字符设备（Character Device） | 块设备（Block Device） |
|------|---------------------------|---------------------|
| 访问单位 | 字节流 | 固定大小的块（Block） |
| 访问方式 | 顺序访问（如串口） | 随机访问（可 seek） |
| 缓存策略 | 通常无缓存，直接传递 | 有页缓存（Page Cache），支持预读 |
| 调度 | 无 | 有 IO 调度器（ elevator 算法） |
| 典型设备 | 键盘、串口、传感器 | 硬盘、SSD、U盘、SD 卡 |
| 用户接口 | /dev/ttyS0, /dev/input/event0 | /dev/sda, /dev/nvme0n1 |

块设备的核心抽象是：**把底层存储设备抽象成一个线性数组，每个数组元素是一个块（sector）**。

## 2. 块设备的核心数据结构

### 2.1 gendisk：代表一个磁盘

```c
struct gendisk {
    int major;                  /* 主设备号 */
    int first_minor;            /* 第一个次设备号 */
    int minors;                 /* 次设备号数量（分区数+1） */
    char disk_name[DISK_NAME_LEN]; /* 设备名，如 "sda" */
    struct block_device_operations *fops; /* 操作函数表 */
    struct request_queue *queue; /* IO 请求队列 */
    struct hd_struct **part_tbl; /* 分区表 */
    sector_t capacity;           /* 容量，以扇区为单位 */
    ...
};
```

`gendisk` 代表一个"磁盘"（可以是物理磁盘或虚拟磁盘），通过 `alloc_disk()` 分配，`add_disk()` 注册到内核。

### 2.2 request_queue：IO 请求队列

```c
struct request_queue {
    struct elevator_queue *elevator; /* IO 调度器 */
    request_fn_proc *request_fn;      /* 处理请求的函数 */
    make_request_fn *make_request_fn; /* 制造请求的函数 */
    ...
};
```

所有对块设备的读写请求，先进入 `request_queue`，由 IO 调度器排序、合并后，再交给驱动处理。

### 2.3 request：一个 IO 请求

```c
struct request {
    struct request_queue *q;    /* 所属队列 */
    struct bio *bio;            /* 挂着的 bio 链表 */
    struct bio *biotail;
    sector_t sector;            /* 起始扇区 */
    unsigned int nr_sectors;    /* 扇区数 */
    ...
};
```

一个 `request` 可以包含多个 `bio`（Buffer IO），代表一组连续的扇区操作。

### 2.4 bio：底层 IO 单元

```c
struct bio {
    sector_t bi_sector;         /* 起始扇区 */
    struct bio_vec *bi_io_vec;  /* 页片段数组 */
    unsigned int bi_vcnt;       /* 数组元素数 */
    unsigned int bi_idx;        /* 当前处理到的索引 */
    ...
};

struct bio_vec {
    struct page *bv_page;       /* 指向页 */
    unsigned int bv_len;        /* 长度 */
    unsigned int bv_offset;       /* 在页中的偏移 */
};
```

`bio` 是描述内存页与设备扇区之间映射的最小单元，支持分散/聚合（Scatter/Gather）IO。

## 3. 块设备驱动注册流程

```c
static int __init myblock_init(void)
{
    /* 1. 注册块设备，申请主设备号 */
    register_blkdev(major, "myblock");
    
    /* 2. 分配 gendisk */
    struct gendisk *disk = alloc_disk(16); /* 支持 15 个分区 */
    
    /* 3. 初始化请求队列 */
    struct request_queue *queue = blk_init_queue(my_request_fn, &lock);
    disk->queue = queue;
    
    /* 4. 设置 gendisk 参数 */
    disk->major = major;
    disk->first_minor = 0;
    disk->fops = &myblock_fops;
    disk->capacity = size / 512; /* 扇区数 */
    strcpy(disk->disk_name, "myblock0");
    
    /* 5. 添加磁盘 */
    add_disk(disk);
    return 0;
}
```

## 4. 请求处理函数（request_fn）

```c
static void my_request_fn(struct request_queue *q)
{
    struct request *req;
    
    while ((req = blk_fetch_request(q)) != NULL) {
        /* 判断请求方向 */
        if (req->cmd_type != REQ_TYPE_FS) {
            __blk_end_request_all(req, -EIO);
            continue;
        }
        
        /* 遍历 bio */
        struct bio *bio;
        __rq_for_each_bio(bio, req) {
            struct bio_vec bvec;
            struct bvec_iter iter;
            
            bio_for_each_segment(bvec, bio, iter) {
                /* 获取内存页和偏移 */
                struct page *page = bvec.bv_page;
                unsigned int offset = bvec.bv_offset;
                unsigned int len = bvec.bv_len;
                
                /* 获取内核虚拟地址 */
                char *buffer = page_address(page) + offset;
                
                /* 执行实际读写（这里是伪代码） */
                if (rq_data_dir(req) == READ)
                    memcpy(buffer, device_memory + sector, len);
                else
                    memcpy(device_memory + sector, buffer, len);
            }
        }
        
        /* 完成请求 */
        __blk_end_request_all(req, 0);
    }
}
```

## 5. IO 调度器（Elevator）

块设备驱动不直接处理原始 bio，bio 先经过 **IO 调度器**（也称为电梯算法，Elevator）进行合并和排序，以减少磁盘寻道时间。

### 5.1 调度器类型

| 调度器 | 名称 | 特点 | 适用场景 |
|--------|------|------|---------|
| Noop | 无操作 | 简单的 FIFO，不做排序 | SSD、NVMe（无机械寻道） |
| Deadline | 截止时间 | 保证请求在截止时间内完成 | 通用桌面、数据库 |
| CFQ | 完全公平队列 | 每个进程一个队列，按时间片轮转 | 多用户桌面 |
| BFQ | 预算公平队列 | CFQ 的改进版，更低延迟 | 交互式桌面 |
| Kyber | 快速 | 更简单的标签分发 | NVMe、高性能存储 |

### 5.2 查看和切换调度器

```bash
# 查看当前调度器
cat /sys/block/sda/queue/scheduler
# 输出：noop deadline [cfq]  （中括号表示当前）

# 切换为 deadline
echo deadline | sudo tee /sys/block/sda/queue/scheduler

# 永久生效（写入 /etc/udev/rules.d/）
ACTION=="add|change", KERNEL=="sd[a-z]", ATTR{queue/scheduler}="deadline"
```

> 对于 SSD/NVMe，建议使用 `noop` 或 `kyber`，因为闪存没有机械寻道，调度器排序反而增加延迟。

## 6. 制作一个虚拟块设备（RAM Disk）

下面是一个最简单的虚拟块设备驱动，用内存模拟磁盘（RAM Disk）：

```c
#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/fs.h>
#include <linux/blkdev.h>
#include <linux/bio.h>
#include <linux/slab.h>

#define MYBLOCK_DEVICENAME "myblock"
#define MYBLOCK_SIZE (4 * 1024 * 1024)  /* 4MB */
#define MYBLOCK_SECTOR_SIZE 512

static int major = 0;
static struct gendisk *disk = NULL;
static struct request_queue *queue = NULL;
static spinlock_t lock;
static u8 *data_buffer;  /* 模拟磁盘数据 */

static void my_request_fn(struct request_queue *q)
{
    struct request *req;
    
    while ((req = blk_fetch_request(q)) != NULL) {
        sector_t sector = blk_rq_pos(req);      /* 起始扇区 */
        unsigned int sectors = blk_rq_sectors(req); /* 扇区数 */
        unsigned int len = sectors * MYBLOCK_SECTOR_SIZE;
        u8 *disk_addr = data_buffer + (sector * MYBLOCK_SECTOR_SIZE);
        
        struct bio_vec bvec;
        struct req_iterator iter;
        
        rq_for_each_segment(bvec, req, iter) {
            unsigned int offset = bvec.bv_offset;
            struct page *page = bvec.bv_page;
            unsigned int bvec_len = bvec.bv_len;
            char *buffer = page_address(page) + offset;
            
            if (rq_data_dir(req) == READ) {
                memcpy(buffer, disk_addr, bvec_len);
            } else {
                memcpy(disk_addr, buffer, bvec_len);
            }
            disk_addr += bvec_len;
        }
        
        __blk_end_request_all(req, 0);
    }
}

static int __init myblock_init(void)
{
    /* 分配内存 */
    data_buffer = kzalloc(MYBLOCK_SIZE, GFP_KERNEL);
    if (!data_buffer)
        return -ENOMEM;
    
    /* 注册块设备 */
    major = register_blkdev(0, MYBLOCK_DEVICENAME);
    if (major < 0)
        goto err_free;
    
    spin_lock_init(&lock);
    
    /* 初始化请求队列 */
    queue = blk_init_queue(my_request_fn, &lock);
    if (!queue)
        goto err_unregister;
    
    /* 分配 gendisk */
    disk = alloc_disk(1);
    if (!disk)
        goto err_cleanup_queue;
    
    disk->major = major;
    disk->first_minor = 0;
    disk->fops = &myblock_fops;  /* 省略 fops 定义 */
    disk->queue = queue;
    disk->capacity = MYBLOCK_SIZE / MYBLOCK_SECTOR_SIZE;
    strcpy(disk->disk_name, "myblock0");
    
    add_disk(disk);
    printk("myblock: init ok, major=%d\n", major);
    return 0;
    
err_cleanup_queue:
    blk_cleanup_queue(queue);
err_unregister:
    unregister_blkdev(major, MYBLOCK_DEVICENAME);
err_free:
    kfree(data_buffer);
    return -ENOMEM;
}

static void __exit myblock_exit(void)
{
    del_gendisk(disk);
    put_disk(disk);
    blk_cleanup_queue(queue);
    unregister_blkdev(major, MYBLOCK_DEVICENAME);
    kfree(data_buffer);
}

module_init(myblock_init);
module_exit(myblock_exit);
MODULE_LICENSE("GPL");
```

## 7. 块设备层整体架构

```
用户空间
    │  read/write / fsync
    ▼
VFS（通用文件系统层）
    │  页缓存（Page Cache）
    ▼
文件系统（ext4/xfs/btrfs）
    │  把文件偏移映射到逻辑块号
    ▼
块设备层（Block Layer）
    │  • 把 bio 放入请求队列
    │  • IO 调度器合并、排序请求
    ▼
设备驱动（Block Device Driver）
    │  request_fn 处理 request
    ▼
硬件（HDD/SSD/NVMe）
```

## 8. 小结

- 块设备以**扇区（sector）**为单位随机访问，有缓存和 IO 调度器。
- 核心结构：`gendisk`（磁盘）、`request_queue`（队列）、`request`（请求）、`bio`（页映射）。
- 驱动需要注册 `request_fn`，从队列中取出请求并处理。
- IO 调度器（elevator）合并排序请求，减少寻道。SSD 推荐 `noop`/`kyber`。
- `bio` 支持 Scatter/Gather，允许一次 IO 操作在多个不连续的内存页和设备扇区之间传输。
- 块设备层是 VFS 和硬件之间的桥梁，理解它是理解 Linux IO 子系统的关键。
