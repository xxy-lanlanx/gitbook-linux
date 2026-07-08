# 07-Linux 信号机制

> 基于 Linux 3.10.29 内核分析。信号（Signal）是 Linux 进程间通信（IPC）中最古老的异步通知机制，用于通知进程发生了某种事件。

## 1. 什么是信号

信号是一个**软中断**，是内核向进程发送的异步事件通知。进程收到信号后，可以：
- **默认处理**：执行内核为该信号定义的默认动作（终止、忽略、暂停等）；
- **忽略**：进程显式忽略该信号（但 `SIGKILL`、`SIGSTOP` 不可忽略）；
- **捕获**：注册信号处理函数，在信号递达时执行自定义逻辑。

信号与硬件中断的区别：中断由硬件触发、陷入内核态处理；信号由内核（或进程）产生，在进程返回用户态时**递送（deliver）**。

## 2. 常见的信号

```text
SIGINT    2   终端中断（Ctrl+C），默认终止进程
SIGTERM   15  优雅终止请求，可被捕获，默认终止
SIGKILL   9   强制杀死，不可捕获、不可忽略
SIGSTOP   19  暂停进程，不可捕获、不可忽略
SIGCONT   18  继续运行（与 SIGSTOP 配对）
SIGSEGV   11  段错误（非法内存访问）
SIGCHLD   17  子进程状态改变（退出/暂停）
SIGALRM   14  alarm() 定时器到期
SIGPIPE   13  向无读端的管道写数据
SIGUSR1   10  用户自定义
SIGUSR2   12  用户自定义
```

查看完整列表：

```bash
kill -l
```

## 3. 信号的来源

信号可由以下途径产生：

1. **硬件异常**：如除零、非法内存访问 → 内核发送 `SIGFPE` / `SIGSEGV`；
2. **终端按键**：Ctrl+C → `SIGINT`，Ctrl+Z → `SIGTSTP`；
3. **系统调用**：`kill()`、`tkill()`、`tgkill()`、`raise()`；
4. **软件条件**：`alarm()` 到期发 `SIGALRM`，子进程退出发 `SIGCHLD`，管道断裂发 `SIGPIPE`。

```c
#include <sys/types.h>
#include <signal.h>
#include <unistd.h>

int main(void) {
    /* 向 PID 1234 发送 SIGTERM */
    kill(1234, SIGTERM);
    /* 向自身发送 SIGUSR1 */
    raise(SIGUSR1);
    return 0;
}
```

## 4. 信号的生命周期：产生 → 未决 → 递送

```text
   产生(kill/alarm/异常)
          │
          ▼
   未决(Pending)：信号已产生但尚未递送
          │  （可能被阻塞 block，停留在 pending 集）
          ▼
   递送(Delivery)：进程从内核返回用户态时处理
          │
          ▼
   处理：默认 / 忽略 / 捕获函数
```

- **未决（Pending）**：信号已产生但未处理，存放在进程的 `pending` 信号集；
- **阻塞（Block）**：进程可屏蔽某些信号，被屏蔽的信号产生后停留在 pending，直到解除屏蔽才递送；
- **递送（Delivery）**：内核在进程即将返回用户态时检查 pending 信号并调用 handler。

> 注意：标准信号（1~31）**不排队**。同一信号在阻塞期间多次产生，解除阻塞后只递送一次；实时信号（SIGRTMIN~SIGRTMAX）才支持排队。

## 5. 注册信号处理：signal 与 sigaction

早期 `signal()` 接口简单但行为在不同 Unix 间不一致，推荐使用 `sigaction()`：

```c
#include <signal.h>
#include <stdio.h>
#include <unistd.h>

void handler(int sig) {
    printf("catch signal %d\n", sig);
}

int main(void) {
    struct sigaction sa;
    sa.sa_handler = handler;
    sigemptyset(&sa.sa_mask);   /* 执行 handler 期间不额外屏蔽信号 */
    sa.sa_flags = 0;
    sigaction(SIGUSR1, &sa, NULL);

    while (1) pause();   /* 等待信号 */
    return 0;
}
```

### 5.1 信号集操作

```c
sigset_t set;
sigemptyset(&set);            /* 清空 */
sigaddset(&set, SIGINT);      /* 加入 SIGINT */
sigprocmask(SIG_BLOCK, &set, NULL);   /* 阻塞 SIGINT */
sigpending(&set);             /* 查看当前未决信号 */
sigprocmask(SIG_UNBLOCK, &set, NULL); /* 解除阻塞 */
```

## 6. 内核中的信号实现概要

信号相关的关键数据结构位于 `task_struct`：

```c
struct task_struct {
    ...
    struct signal_struct *signal;     /* 线程组共享 */
    struct sighand_struct *sighand;  /* 信号处理函数表 */
    sigset_t blocked;                 /* 阻塞信号集 */
    struct sigpending pending;        /* 私有未决信号 */
    ...
};
```

- 信号处理函数表 `sighand->action[64]` 对应 64 种信号；
- 信号产生时，内核调用 `send_signal()` 将信号加入目标任务的 `pending` 或线程组 `shared_pending`；
- 进程被调度回到用户态前，`do_notify_resume()` → `do_signal()` 负责递送；若注册了 handler，则通过 `setup_frame()` 构造用户栈帧，返回用户态执行 handler，结束后再回到原指令。

## 7. 几个易错点

- `SIGKILL` / `SIGSTOP` 既不能被捕获也不能被忽略，管理员也无法拦截；
- 在信号处理函数里应只调用 **async-signal-safe** 函数（如 `write`、`_exit`），避免使用 `printf`、`malloc` 等非可重入函数；
- 使用 `signal()` 注册时，handler 执行后行为在不同系统上可能复位为默认，故优先用 `sigaction`；
- 用 `fork()` 创建的子进程会继承父进程的信号处理方式与阻塞集。

## 8. 小结

信号是轻量、异步的事件通知机制，适合处理异常、终止、计时等场景。理解「产生—未决—阻塞—递送」的生命周期，以及 sigaction 的正确用法，是编写健壮 Linux 程序的基础。
