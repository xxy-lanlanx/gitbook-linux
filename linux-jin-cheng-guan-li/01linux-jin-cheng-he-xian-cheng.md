# 01-Linux进程和线程

事实在 Linux 上，进程和线程的相同点要远远大于不同点。在 Linux 下的线程甚至都被称为了轻量级进程。

内核中表示线程的数据结构。Linux 中，无论进程还是线程，都是抽象成了 task 任务，在源码里都是用 task\_struct 结构来实现的。

<figure><img src="../.gitbook/assets/image.png" alt=""><figcaption></figcaption></figure>

对于线程来讲，所有的字段都是和进程一样的（本来就是一个结构体来表示的）。包括状态、pid、task 树关系、地址空间、文件系统信息、打开的文件信息等等字段，线程也都有。

进程和线程的相同点要远远大于不同点，本质上是同一个东西，都是一个 task\_struct ！正因为进程线程如此之相像，所以在 Linux 下的线程还有另外一个名字，叫轻量级进程 。

在 Linux 中，每一个 task\_struct 都需要被唯一的标识，它的 pid 就是唯一标识号。

对于进程来说，这个 pid 就是我们平时常说的进程 pid。

对于线程来说，我们假如一个进程下创建了多个线程出来。那么每个线程的 pid 都是不同的。但是我们一般又需要记录线程是属于哪个进程的。这时候，tgid 就派上用场了，通过 tgid 字段来表示自己所归属的进程 ID。

<figure><img src="../.gitbook/assets/image (1).png" alt=""><figcaption></figcaption></figure>

## 进程与线程的创建

Linux 中创建进程的核心系统调用是 `fork()`，创建线程的核心系统调用是 `clone()`。两者底层都通过 `do_fork()` 实现，区别仅在于 `clone()` 会共享更多资源（地址空间、文件描述符表、信号处理等）。

| 特性 | 进程（fork） | 线程（clone CLONE_VM） |
|------|------------|----------------------|
| 地址空间 | 独立（COW 写时复制） | 共享 |
| 文件描述符 | 独立（复制父进程） | 共享 |
| PID | 新 PID | 新 PID，但 tgid = 父进程 PID |
| 栈 | 独立 | 共享（或指定新栈） |

`clone()` 的参数标志决定了哪些资源被共享，这是理解"线程即轻量级进程"的关键：

```c
#include <sched.h>
#include <stdio.h>
#include <unistd.h>

int thread_fn(void *arg) {
    printf("线程 PID=%d, tgid=%d\n", getpid(), getppid());
    return 0;
}

int main(void) {
    char stack[4096];
    /* CLONE_VM 共享地址空间 = 线程语义 */
    clone(thread_fn, stack + 4096, CLONE_VM | CLONE_FS | CLONE_FILES, NULL);
    sleep(1);
    return 0;
}
```

## 进程状态与调度

task_struct 中的 `state` 字段描述进程当前状态：

- **TASK_RUNNING**：可运行（在运行队列中）
- **TASK_INTERRUPTIBLE**：可中断睡眠（等信号或资源）
- **TASK_UNINTERRUPTIBLE**：不可中断睡眠（等磁盘 IO，不响应信号）
- **TASK_STOPPED**：被信号停止
- **EXIT_ZOMBIE**：进程已退出，等待父进程收尸

状态转换图：

```
    fork()          调度器选中
[创建] -----> [TASK_RUNNING] ---------> [运行中]
                  ^    | 时间片用完/被抢占
                  |    v
                  | [TASK_RUNNING] 可运行队列
                  |    |
                  |    | 等待资源
                  |    v
                  | [TASK_INTERRUPTIBLE] <---- 信号唤醒
                  |    | 等待磁盘
                  |    v
                  +-- [TASK_UNINTERRUPTIBLE]
```

## 进程树与关系

每个进程都有父进程（`real_parent`），所有进程最终追溯到 init（PID 1）。`children` 和 `sibling` 链表把进程组织成树：

```c
struct task_struct {
    struct task_struct *real_parent;  /* 真正的父进程 */
    struct task_struct *parent;       /* 调试/信号用的父进程 */
    struct list_head children;      /* 子进程链表 */
    struct list_head sibling;       /* 兄弟进程链表节点 */
    ...
};
```

用 `pstree` 命令可以直观看到进程树：`pstree -p` 显示 PID，`-a` 显示参数。

