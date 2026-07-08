# 04-Linux 中断处理与下半部

> 基于 Linux 3.10.29 内核分析。本章建立「中断上下文」概念，并讲解为什么需要把中断工作拆分为「上半部 + 下半部」，以及软中断、tasklet、工作队列三种下半部机制的区别与选择。

## 1. 中断上下文

硬件（网卡、磁盘、定时器…）通过中断线（IRQ）打断 CPU，陷入内核 `do_IRQ()` → 对应 `irq_handler_t`。在中断处理函数执行期间：
- 运行在**中断上下文**（而非进程上下文）；
- **不能睡眠**（没有所属的 `task_struct`，不可被调度）；
- 不能被同一 CPU 上的其他中断（同优先级）抢占（硬中断期间本地中断关闭）；
- 执行应**尽可能快**，否则会阻塞其他中断与系统响应。

## 2. 为什么要下半部（Bottom Half）

中断处理函数（上半部）若做耗时工作（如拷贝网络包、解析协议），会长时间关中断，导致系统卡顿、丢中断。因此把工作一分为二：

```text
上半部（Top Half / Hard IRQ）
  ├─ 原则：快、只做必需
  ├─ 例：应答硬件、读状态寄存器、把数据放到队列
  └─ 然后「调度」下半部，立即返回（开中断）

下半部（Bottom Half）
  ├─ 在较安全上下文执行耗时处理
  ├─ 例：协议解析、数据拷贝、通知上层
  └─ 允许被中断、可睡眠（仅 workqueue 类）
```

## 3. 三种下半部机制

### 3.1 软中断（Softirq）

- 静态定义（内核编译期确定，如 `NET_TX_SOFTIRQ`、`NET_RX_SOFTIRQ`、`TIMER_SOFTIRQ`、`SCHED_SOFTIRQ`）；
- 在 `do_softirq()` 中执行，运行在**中断上下文**（不可睡眠）；
- 同一软中断可在多个 CPU 上并发，要求处理函数是**可重入**的；
- 性能高，但编程复杂，**驱动一般不直接用**，主要用于网络、调度、定时器子系统。

```c
enum {
    HI_SOFTIRQ = 0, TIMER_SOFTIRQ, NET_TX_SOFTIRQ,
    NET_RX_SOFTIRQ, BLOCK_SOFTIRQ, TASKLET_SOFTIRQ, ...
};
```

### 3.2 tasklet

- 建立在软中断之上（`TASKLET_SOFTIRQ`），**同一 tasklet 不会在两个 CPU 同时运行**，简化了并发；
- 仍运行在**中断上下文（不可睡眠）**；
- 适合驱动的下半部：简单、快、不能睡眠。

```c
#include <linux/interrupt.h>

void my_tasklet_func(unsigned long data) {
    /* 下半部工作：不可睡眠 */
}

DECLARE_TASKLET(my_tasklet, my_tasklet_func, 0);  /* 静态声明 */

/* 在中断上半部调度 */
irqreturn_t drv_isr(int irq, void *dev) {
    tasklet_schedule(&my_tasklet);   /* 触发下半部 */
    return IRQ_HANDLED;
}
```

### 3.3 工作队列（Workqueue）

- 在**进程上下文**执行（由内核线程 `kworker` 运行），**可以睡眠、可以调度**；
- 适合需要阻塞/耗时的下半部（如需要 `mutex`、可能 `kmalloc(GFP_KERNEL)`）；
- 写法更接近普通函数。

```c
#include <linux/workqueue.h>

struct work_struct my_work;
void my_work_func(struct work_struct *w) {
    /* 可睡眠的下半部工作 */
}

INIT_WORK(&my_work, my_work_func);

/* 在中断上半部调度 */
irqreturn_t drv_isr(int irq, void *dev) {
    schedule_work(&my_work);   /* 交给 kworker 线程 */
    return IRQ_HANDLED;
}
```

### 3.4 三者对比与选择

| 机制 | 上下文 | 可否睡眠 | 并发性 | 适用 |
|------|--------|---------|--------|------|
| 软中断 | 中断 | 否 | 高（需可重入） | 网络/调度等核心子系统 |
| tasklet | 中断 | 否 | 同 tasklet 串行 | 驱动简单下半部 |
| 工作队列 | 进程 | 是 | 由线程调度 | 需睡眠/阻塞的下半部 |

> 经验法则：不能睡眠且很快 → tasklet；需要睡眠/拿 mutex → workqueue；极致性能内核子系统 → softirq。

## 4. 线程化中断（threaded IRQ）

3.x 内核支持把整个 handler 放到内核线程里跑（进程上下文，可睡眠），用 `request_threaded_irq()`：

```c
/* 上半部 hard_func 尽量快，下半部 thread_func 可睡眠 */
request_threaded_irq(irq, hard_func, thread_func, IRQF_SHARED, "drv", dev);
```

这把「中断下半部」进一步统一进线程模型，简化了驱动编写。

## 5. 小结

中断处理的核心是「快进快出」：上半部应答硬件并调度下半部，下半部用 tasklet（不可睡）或 workqueue（可睡）完成重活。理解软中断/tasklet/工作队列的上下文差异，是写出稳定驱动的关键。
