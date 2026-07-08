# 08-Linux 进程生命周期：fork / exec / exit

> 基于 Linux 3.10.29 内核分析。本章剖析进程从「创建」到「退出」的完整生命周期，重点理解 fork 的写时复制、exec 的地址空间替换，以及僵尸/孤儿进程的产生与回收。

## 1. 进程与 task_struct

Linux 中进程（含线程）在内核中统一用 `task_struct` 描述，也称「任务」。进程的创建本质是复制/构造一个新的 `task_struct` 并加入调度。

```c
struct task_struct {
    volatile long state;        /* 进程状态 */
    pid_t pid;                  /* 进程号 */
    pid_t tgid;                 /* 线程组号（线程共享） */
    struct mm_struct *mm;       /* 内存描述符 */
    struct files_struct *files; /* 打开文件表 */
    ...
};
```

## 2. 进程创建：fork / vfork / clone

三者最终都调用内核的 `do_fork()`，区别仅在于传入的**标志（clone flags）**不同。

```text
fork()    → do_fork(SIGCHLD, ...)            父子拥有独立地址空间（写时复制）
vfork()   → do_fork(CLONE_VFORK|CLONE_VM|...) 父子共享地址空间，父阻塞直到子 exec/exit
clone()   → do_fork(user_flags, ...)         可精细控制共享哪些资源（线程/Namespace 的基础）
```

### 2.1 fork 与写时复制（COW）

`fork()` 创建的子进程最初**并不复制父进程的物理内存**，而是与父共享页表，并将页标记为只读。只有当父子任一方写入某页时，才触发**缺页异常**复制该页：

```c
#include <unistd.h>
#include <stdio.h>

int main(void) {
    int x = 10;
    pid_t pid = fork();
    if (pid == 0) {           /* 子进程 */
        x = 20;
        printf("child x=%d\n", x);
    } else {                  /* 父进程 */
        printf("parent x=%d, child pid=%d\n", x, pid);
    }
    return 0;
}
```

- 优点：fork 极快，避免无谓的全量拷贝；
- 若 fork 后立刻 exec，则几乎不触发 COW，效率很高。

### 2.2 vfork

`vfork()` 让父子**共享同一地址空间**，且父进程被挂起，直到子进程调用 `exec()` 或 `_exit()`。现代程序中已基本被 `fork()+exec()`（配合 COW）取代，仅在对性能极度敏感的嵌入式场景使用。

### 2.3 clone 与线程

`clone()` 通过 `CLONE_VM`（共享内存）、`CLONE_FILES`（共享文件表）、`CLONE_THREAD`（同一线程组）等标志，实现了**线程**。glibc 的 `pthread_create()` 底层即调用 `clone()`。

## 3. exec：替换地址空间

`exec` 族函数（`execl`、`execv`、`execve`…）会用新程序**替换**当前进程的地址空间（代码段、数据段、堆、栈），但**进程号（pid）保持不变**，打开的文件描述符（除非标记 `FD_CLOEXEC`）也保留。

```c
#include <unistd.h>

int main(void) {
    pid_t pid = fork();
    if (pid == 0) {
        /* 子进程执行 /bin/ls */
        execl("/bin/ls", "ls", "-l", (char *)NULL);
        _exit(127);   /* exec 失败才会执行到这里 */
    }
    return 0;
}
```

典型流程：**shell 先 fork 出子进程，再在子进程中 exec 目标程序**。

## 4. 进程退出与回收

### 4.1 退出路径

- 正常退出：`return` from `main`、`exit()`、`_exit()`；
- 异常退出：收到 `SIGKILL`/`SIGSEGV` 等终止信号；调用 `abort()`。

进程退出时内核释放其大部分资源，但保留 `task_struct` 的极小部分（pid、退出码、状态）形成**僵尸进程（Zombie）**，等待父进程回收。

### 4.2 僵尸进程与孤儿进程

- **僵尸进程**：子进程已退出，但父进程未调用 `wait()`/`waitpid()` 回收。僵尸进程不占内存，但占用 pid，大量僵尸会耗尽 pid 资源。
- **孤儿进程**：父进程先退出，子进程被 `init`（pid=1）接管，`init` 会自动 `wait()` 回收它们，因此孤儿进程不会变僵尸。

```c
#include <sys/wait.h>
#include <unistd.h>

int main(void) {
    pid_t pid = fork();
    if (pid == 0) _exit(0);

    /* 父进程回收子进程，避免僵尸 */
    int status;
    waitpid(pid, &status, 0);
    if (WIFEXITED(status)) printf("child exit code=%d\n", WEXITSTATUS(status));
    return 0;
}
```

### 4.3 通过 SIGCHLD 异步回收

```c
void on_child(int sig) {
    int status;
    /* 循环回收，避免同时多个子进程退出只收到一个信号 */
    while (waitpid(-1, &status, WNOHANG) > 0) { /* 回收 */ }
}
/* 注册：sigaction(SIGCHLD, &sa, NULL); */
```

## 5. 内核视角：do_fork 与退出

- 创建：`do_fork()` → `copy_process()` 复制 `task_struct`、文件表、内存描述符（COW），最后 `wake_up_new_task()` 入队调度；
- 退出：`do_exit()` 释放资源、置状态为 `EXIT_ZOMBIE`、向父发 `SIGCHLD`；父进程 `wait()` 时调用 `release_task()` 彻底释放 `task_struct`。

## 6. 小结

理解 `fork`（COW 复制）→ `exec`（替换镜像）→ `exit`（进入僵尸）→ `wait`（父回收）这条主线，是掌握 Linux 进程模型的钥匙。僵尸进程靠父进程及时 `wait` 避免，孤儿进程由 `init` 兜底，二者都不会造成资源泄漏。
