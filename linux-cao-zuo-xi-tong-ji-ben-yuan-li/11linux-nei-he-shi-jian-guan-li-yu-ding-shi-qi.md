# 10-Linux 内核时间管理与定时器

> 时间管理是操作系统最基础的职责之一。内核需要精确计时、调度进程、管理定时器、提供系统时钟，甚至要支持tickless（无节拍）模式以节省功耗。

## 1. 内核中的时间概念

Linux 内核中有多种时间表示，分别用于不同场景：

| 时间类型 | 名称 | 精度 | 用途 |
|---------|------|------|------|
| jiffies | 全局时钟计数器 | 1/HZ 秒（通常 1~10ms） | 内核调度、定时器、统计 |
| xtime | 墙上时钟（Wall Clock） | 纳秒 | 获取真实时间（如 gettimeofday） |
| ktime | 单调时钟（Monotonic） | 纳秒 | 内核内部计时，不受用户修改影响 |
| clocksource | 时钟源 | 纳秒~微秒 | 底层硬件计数器，提供时间基线 |

## 2. jiffies：内核的"心跳"

`jiffies` 是内核维护的一个全局变量，记录系统启动以来时钟中断的次数：

```c
extern unsigned long volatile jiffies;  /* 32位 */
extern u64 jiffies_64;                  /* 64位，防溢出 */
```

如果内核编译时 `CONFIG_HZ = 1000`（每秒 1000 次时钟中断），那么：

```
1 jiffy = 1 / 1000 = 1 毫秒
jiffies 每增加 1，代表过了 1ms
```

jiffies 常用于判断超时：

```c
unsigned long start = jiffies;
while (time_before(jiffies, start + HZ)) {  /* 等待 1 秒 */
    /* 轮询等待，实际生产中不推荐忙等 */
}
```

> 注意：jiffies 会溢出（32位约 50 天回绕），内核提供了 `time_before()` / `time_after()` 宏来正确处理溢出比较。

## 3. 时钟源（Clocksource）与时钟事件设备（Clock Event Device）

现代 Linux 把时间管理拆分为两个抽象层：

### 3.1 Clocksource（时钟源）

**只读**，提供单调递增的计数。底层通常是 CPU 的 TSC（Time Stamp Counter）或 HPET（High Precision Event Timer）。

```c
struct clocksource {
    u64 (*read)(struct clocksource *cs);  /* 读取当前计数 */
    u64 mask;                              /* 计数器位宽 */
    u32 mult;                              /* 乘数 */
    u32 shift;                             /* 移位 */
    ...
};
```

读取到的原始计数通过 `mult` 和 `shift` 转换为纳秒：

```
nanoseconds = (cycles * mult) >> shift
```

### 3.2 Clock Event Device（时钟事件设备）

**可编程**，用于在指定时间点触发中断。每个 CPU 核心一个，通常是 Local APIC Timer。

```c
struct clock_event_device {
    void (*set_next_event)(unsigned long evt, struct clock_event_device *dev);
    void (*event_handler)(struct clock_event_device *dev);
    ...
};
```

时钟事件设备是 tickless 内核的关键：当系统空闲时，内核计算下一个需要定时器触发的时刻，一次性编程时钟事件设备到那个时间点，中间不再触发时钟中断，从而省电。

## 4. 定时器（Timer）

Linux 内核提供多种定时器机制，适用于不同场景：

### 4.1 内核定时器（struct timer_list）

基于 jiffies 的**软中断上下文**定时器，精度取决于 HZ（通常 1~10ms）。

```c
#include <linux/timer.h>

struct timer_list my_timer;

void my_timer_callback(struct timer_list *t)
{
    printk("Timer fired!\n");
}

timer_setup(&my_timer, my_timer_callback, 0);
my_timer.expires = jiffies + HZ;  /* 1秒后触发 */
add_timer(&my_timer);               /* 启动定时器 */
```

特点：
- 运行在中断上下文（顶半部），**不能睡眠**。
- 不能访问用户空间。
- 精度受 HZ 限制。
- 同一 timer 不能重复添加，需要先 `del_timer_sync()`。

### 4.2 高精度定时器（HRTimer）

Linux 2.6.16 引入的**纳秒级**定时器，基于 ktime 和 clock_event_device，精度可达微秒甚至纳秒级。

```c
#include <linux/hrtimer.h>

struct hrtimer hr_timer;

enum hrtimer_restart hrtimer_callback(struct hrtimer *timer)
{
    ktime_t now = ktime_get();
    printk("HRTimer fired at %lld ns\n", ktime_to_ns(now));
    return HRTIMER_NORESTART;  /* 不重复 */
}

hrtimer_init(&hr_timer, CLOCK_MONOTONIC, HRTIMER_MODE_REL);
hr_timer.function = &hrtimer_callback;
hrtimer_start(&hr_timer, ms_to_ktime(100), HRTIMER_MODE_REL); /* 100ms */
```

HRTimer 模式：

| 模式 | 含义 | 示例 |
|------|------|------|
| `HRTIMER_MODE_REL` | 相对当前时间 | 100ms 后触发 |
| `HRTIMER_MODE_ABS` | 绝对时间点 | 到某个 ktime 触发 |
| `HRTIMER_MODE_PINNED` | 绑定到当前 CPU | 防止迁移带来的延迟 |

### 4.3 低精度 vs 高精度定时器对比

| 特性 | 传统 timer_list | HRTimer |
|------|-----------------|---------|
| 精度 | 1~10 ms（取决于 HZ） | 微秒~纳秒级 |
| 上下文 | 软中断 | 软中断或硬中断 |
| 时间单位 | jiffies（unsigned long） | ktime_t（s64 纳秒） |
| 适用场景 | 超时、心跳、轮询 | 实时调度、多媒体、精确计时 |
| 开销 | 较小 | 较大（红黑树管理） |

## 5. Tickless（NO_HZ）模式

传统 Linux 中，即使 CPU 空闲，时钟中断也会以固定频率（如 1000Hz）不断触发，造成不必要的功耗。Tickless 内核允许在空闲时**关闭时钟中断**。

### 5.1 实现原理

```
CPU 空闲时
    │
    ▼
计算下一个定时器到期时间（如 500ms 后）
    │
    ▼
编程 Local APIC Timer 在 500ms 后触发一次中断
    │
    ▼
CPU 进入深度睡眠（C-States）
    │
    ▼
500ms 后，时钟中断唤醒 CPU
    │
    ▼
处理到期的定时器，然后继续判断是否可以再次 idle
```

### 5.2 配置选项

```
CONFIG_NO_HZ=y          /* 启用 tickless */
CONFIG_NO_HZ_IDLE=y     /* 仅空闲时 tickless */
CONFIG_NO_HZ_FULL=y     /* 全 tickless（包括 busy CPU，用于实时） */
```

Tickless 对以下场景特别有益：
- **服务器**：空闲 CPU 降低功耗，减少散热。
- **笔记本/嵌入式**：延长电池续航。
- **实时系统**：减少时钟中断抖动，提高调度确定性。

## 6. 内核中的延迟与睡眠

### 6.1 忙等待（Busy Waiting）

```c
/* 忙等 10 微秒，期间 CPU 空转 */
udelay(10);

/* 忙等 1 毫秒 */
mdelay(1);
```

> 注意：`mdelay()` 在循环中执行空操作，会占用 CPU，应尽量避免使用。

### 6.2 睡眠等待（Sleeping）

```c
/* 进程睡眠 100 毫秒， relinquish CPU */
msleep(100);

/* 可中断睡眠（可被信号唤醒） */
msleep_interruptible(100);

/* 高精度睡眠 */
usleep_range(1000, 2000);  /* 睡眠 1~2 毫秒 */
```

| 函数 | 上下文 | 精度 | 特点 |
|------|--------|------|------|
| `udelay()` | 原子/中断 | 微秒 | 忙等，占用 CPU |
| `mdelay()` | 原子/中断 | 毫秒 | 忙等，不推荐 |
| `msleep()` | 进程 | 毫秒 | 释放 CPU |
| `usleep_range()` | 进程 | 微秒 | 释放 CPU，可指定范围减少唤醒次数 |
| `schedule_timeout()` | 进程 | jiffies | 基于定时器的睡眠 |

### 6.3 选择策略

- **中断上下文**：只能用 `udelay()`（忙等），不能睡眠。
- **进程上下文、需要精确短时延迟**：`usleep_range()`（推荐，避免 busy-wait）。
- **进程上下文、长延迟**：`msleep()` 或 `schedule_timeout()`。
- **需要纳秒级精确触发**：使用 HRTimer。

## 7. 时间管理相关系统调用

| 系统调用 | 功能 | 时钟类型 |
|---------|------|---------|
| `gettimeofday()` | 获取墙上时间 | REALTIME |
| `clock_gettime(CLOCK_MONOTONIC)` | 获取单调时间（不受 NTP 调整） | MONOTONIC |
| `clock_gettime(CLOCK_PROCESS_CPUTIME_ID)` | 获取进程 CPU 时间 | PROCESS |
| `nanosleep()` | 高精度睡眠 | MONOTONIC |
| `timer_create()` / `timer_settime()` | POSIX 定时器 | 可配置 |

```c
/* 获取高精度单调时间 */
struct timespec ts;
clock_gettime(CLOCK_MONOTONIC, &ts);
printf("Monotonic: %ld.%09ld\n", ts.tv_sec, ts.tv_nsec);
```

## 8. 小结

| 概念 | 要点 |
|------|------|
| jiffies | 内核全局时钟计数，精度 1/HZ，用于超时判断 |
| clocksource | 只读硬件计数器，提供时间基线（TSC/HPET） |
| clock_event | 可编程中断源，触发定时器和 tick |
| timer_list | 传统低精度定时器，基于 jiffies，软中断上下文 |
| HRTimer | 高精度定时器，纳秒级，红黑树管理 |
| tickless | 空闲时关闭时钟中断，降低功耗 |
| udelay / msleep | 忙等 vs 睡眠，根据上下文选择 |

时间管理是内核最基础也最精密的子系统之一，它贯穿调度、定时器、统计、功耗管理的方方面面。理解时钟源、事件设备和定时器的关系，是深入内核的必经之路。
