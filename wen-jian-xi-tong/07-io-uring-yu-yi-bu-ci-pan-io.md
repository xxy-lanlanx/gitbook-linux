# 07-io_uring 与异步磁盘 I/O

## 一、传统 Linux I/O 的瓶颈

在 Linux 中，传统的同步 I/O 通过 `read()`/`write()` 系统调用完成，每次调用都需要经历：

1. 用户态 → 内核态上下文切换
2. 内核页缓存查找/分配
3. 磁盘控制器调度
4. 数据拷贝到用户空间
5. 内核态 → 用户态返回

当并发 I/O 请求增多时，这种**同步、阻塞、多次拷贝**的模式成为性能瓶颈。虽然 `aio`（POSIX AIO）和 `libaio` 提供了异步接口，但存在以下缺陷：

- 需要 `O_DIRECT` 绕过页缓存，限制了使用场景
- 缓冲区必须对齐到扇区边界
- 每个 I/O 仍需一次系统调用
- 对缓冲 I/O（buffered I/O）支持不完善

io_uring 由 Jens Axboe 于 Linux 5.1 引入，旨在统一解决这些问题。

## 二、io_uring 的核心设计

io_uring 引入了**两个无锁环形队列（Ring Buffer）**：

```
用户空间                          内核空间
┌─────────────┐                  ┌─────────────┐
│ 提交队列    │  ────────►       │  提交队列   │
│ (SQ)        │  共享内存        │  (SQ)       │
│ tail (user) │                  │ head (kern) │
└─────────────┘                  └─────────────┘
                                      │
                                      ▼
                                ┌─────────────┐
                                │  内核处理    │
                                │  (异步)      │
                                └─────────────┘
                                      │
                                      ▼
┌─────────────┐                  ┌─────────────┐
│ 完成队列    │  ◄────────        │  完成队列   │
│ (CQ)        │  共享内存        │  (CQ)       │
│ head (user) │                  │ tail (kern) │
└─────────────┘                  └─────────────┘
```

- **SQ（Submission Queue）**：用户程序将 I/O 请求放入，内核消费
- **CQ（Completion Queue）**：内核将完成事件放入，用户程序消费
- **共享内存**：两个队列通过 `mmap` 映射到用户空间，**无需系统调用**即可提交和收割 I/O

### 1. 关键数据结构

```c
// include/uapi/linux/io_uring.h
struct io_uring_sqe {
    __u8    opcode;         // IORING_OP_READV, IORING_OP_WRITEV, ...
    __u8    flags;          // IOSQE_FIXED_FILE, IOSQE_IO_DRAIN
    __u16   ioprio;         // I/O 优先级
    __s32   fd;             // 目标文件描述符
    __u64   off;            // 文件偏移
    __u64   addr;           // 用户缓冲区地址
    __u32   len;            // 长度
    __u64   user_data;      // 用户自定义标识（完成时原样返回）
    // ...
};

struct io_uring_cqe {
    __u64   user_data;      // 对应的 sqe->user_data
    __s32   res;            // 结果（>=0 成功，<0 错误码）
    __u32   flags;          // 标志位
};
```

## 三、io_uring 的三种工作模式

### 1. 默认模式：轮询（Polling）

```c
int io_uring_queue_init(unsigned entries, struct io_uring *ring, unsigned flags);
// flags = 0 时，用户通过 io_uring_submit() 触发系统调用，将 SQ 提交给内核
```

每次提交仍需 `io_uring_enter()` 系统调用，但一次可以批量提交多个 I/O。

### 2. SQPOLL 模式：内核轮询提交队列

```c
io_uring_queue_init(entries, &ring, IORING_SETUP_SQPOLL);
```

- 内核启动一个**专用内核线程**（`io_uring-sq`）轮询 SQ
- 用户提交 I/O 到 SQ 后**无需任何系统调用**，内核线程自动消费
- 只有当 SQ 环满时，才需要 `io_uring_enter()` 唤醒内核线程
- 内核线程可以绑定到特定 CPU，减少调度开销

```bash
ps -e | grep io_uring
# 12345 ? 00:00:01 io_uring-sq
```

### 3. IOPOLL 模式：忙轮询完成事件

```c
io_uring_queue_init(entries, &ring, IORING_SETUP_IOPOLL);
```

- 用户通过 `io_uring_peek_cqe()` 或自定义轮询逻辑直接查看 CQ
- **无需软中断**，延迟最低
- 适合延迟敏感型应用（如 NVMe SSD 上的数据库）

### 4. 组合模式：SQPOLL + IOPOLL

```c
io_uring_queue_init(entries, &ring, IORING_SETUP_SQPOLL | IORING_SETUP_IOPOLL);
```

- 零系统调用提交（SQPOLL）
- 零中断完成收割（IOPOLL）
- 对于 NVMe 存储，可实现 **微秒级** I/O 延迟

## 四、io_uring 支持的 I/O 操作

| opcode | 说明 | 性能优势 |
|--------|------|----------|
| `IORING_OP_READV` | 向量读 | 批量读取 |
| `IORING_OP_WRITEV` | 向量写 | 批量写入 |
| `IORING_OP_READ_FIXED` | 使用预注册缓冲区读 | 省一次拷贝 |
| `IORING_OP_WRITE_FIXED` | 使用预注册缓冲区写 | 省一次拷贝 |
| `IORING_OP_FSYNC` | 同步文件元数据 | 异步 fsync |
| `IORING_OP_POLL_ADD` | 注册 poll 事件 | 替代 epoll |
| `IORING_OP_ACCEPT` | 异步 accept | 替代 accept4 |
| `IORING_OP_CONNECT` | 异步 connect | 替代阻塞 connect |
| `IORING_OP_SEND/RECV` | 异步 socket I/O | 替代 send/recv |
| `IORING_OP_SPLICE` | 管道零拷贝 | 无需用户空间缓冲 |
| `IORING_OP_TIMEOUT` | 超时事件 | 替代 timerfd |

**注册文件和缓冲区（Fixed File/Buffer）**：

```c
// 预注册文件描述符，避免每次 I/O 重复查找 file 结构
io_uring_register_files(&ring, fds, nr_fds);

// 预注册用户缓冲区，实现零拷贝
io_uring_register_buffers(&ring, iovecs, nr_iovecs);

// 此后使用 IORING_OP_READ_FIXED，addr 直接指向预注册缓冲区索引
sqe->opcode = IORING_OP_READ_FIXED;
sqe->buf_index = 0;  // 使用 iovecs[0]
```

## 五、使用示例

```c
#include <liburing.h>
#include <fcntl.h>
#include <stdio.h>

#define ENTRIES 64
#define BUFSIZE 4096

int main() {
    struct io_uring ring;
    struct io_uring_sqe *sqe;
    struct io_uring_cqe *cqe;
    char buf[BUFSIZE];

    // 初始化 io_uring，使用 SQPOLL 模式
    int ret = io_uring_queue_init(ENTRIES, &ring, IORING_SETUP_SQPOLL);
    if (ret < 0) {
        perror("io_uring_queue_init");
        return 1;
    }

    int fd = open("/tmp/testfile", O_RDONLY);
    if (fd < 0) { perror("open"); return 1; }

    // 获取 SQ 条目
    sqe = io_uring_get_sqe(&ring);
    io_uring_prep_read(sqe, fd, buf, BUFSIZE, 0);
    sqe->user_data = 1;  // 自定义标识

    // 提交 I/O（SQPOLL 模式下通常无需实际 syscall）
    io_uring_submit(&ring);

    // 等待完成事件
    ret = io_uring_wait_cqe(&ring, &cqe);
    if (ret < 0) { perror("io_uring_wait_cqe"); return 1; }

    if (cqe->res >= 0)
        printf("Read %d bytes: %.20s...\n", cqe->res, buf);
    else
        printf("Read error: %d\n", cqe->res);

    io_uring_cqe_seen(&ring, cqe);
    io_uring_queue_exit(&ring);
    close(fd);
    return 0;
}
```

编译：`gcc -o test test.c -luring`

## 六、性能对比

| 方案 | 1 线程 IOPS | 延迟 | 系统调用次数 |
|------|------------|------|-------------|
| sync read/write | ~50K | 高 | 每 I/O 2 次 |
| libaio (O_DIRECT) | ~150K | 中 | 每 I/O 1 次 |
| io_uring (默认) | ~300K | 低 | 批量提交 |
| io_uring (SQPOLL) | ~500K+ | 极低 | 接近 0 |
| io_uring (SQPOLL+IOPOLL) | ~1M+ | 微秒级 | 接近 0 |

> 测试环境：Intel Xeon + NVMe SSD, 4K 随机读

## 七、内核实现要点

### 1. io_uring 核心文件

| 文件 | 功能 |
|------|------|
| `fs/io_uring.c` | 主实现，包含 ring 初始化、sqe 处理、cqe 投递 |
| `include/uapi/linux/io_uring.h` | 用户态 API 头文件 |
| `include/linux/io_uring_types.h` | 内核态数据结构 |

### 2. 提交处理流程

```c
// fs/io_uring.c
static int io_submit_sqes(struct io_ring_ctx *ctx, unsigned int nr)
{
    struct io_kiocb *req;
    
    for (i = 0; i < nr; i++) {
        sqe = io_get_sqe(ctx);
        req = io_alloc_req(ctx);  // 分配请求结构
        
        switch (sqe->opcode) {
        case IORING_OP_READV:
            ret = io_read(req, true);  // 异步读取
            break;
        case IORING_OP_WRITEV:
            ret = io_write(req, true); // 异步写入
            break;
        // ... 其他 opcode
        }
        
        // 如果支持异步，将 req 挂接到工作队列
        if (ret == -EIOCBQUEUED)
            io_queue_async_work(req);
    }
}
```

### 3. 与 epoll 的对比

| 特性 | epoll | io_uring |
|------|-------|----------|
| 设计目标 | 多路复用网络 I/O | 统一异步 I/O（文件+网络） |
| 系统调用 | `epoll_ctl` + `epoll_wait` | 共享内存零拷贝 |
| 文件 I/O | 不支持（文件总是就绪） | 完全支持 |
| 批量操作 | 不支持 | 原生支持批量 sqe/cqe |
| 零拷贝 | 需 `splice` | 原生 `IORING_OP_SPLICE` |

io_uring 不是 epoll 的替代品，而是**超集**——它可以做所有 epoll 能做的事，还能做文件 I/O、异步 fsync、超时等。

## 八、总结

| 特性 | 说明 |
|------|------|
| 设计哲学 | 批量提交 + 批量收割 + 共享内存 |
| 最佳模式 | SQPOLL + IOPOLL（NVMe 场景） |
| 关键优化 | 注册文件/缓冲区（Fixed） |
| 适用场景 | 数据库、KV 存储、CDN、网络代理 |
| 发展趋势 | 逐步替代 libaio，成为 Linux 异步 I/O 标准 |

对于现代高性能存储应用（如 RocksDB、Nginx 的 `io_uring` 补丁），将 I/O 模型迁移到 io_uring 通常能带来 **2-5 倍** 的吞吐量提升和显著延迟降低。
