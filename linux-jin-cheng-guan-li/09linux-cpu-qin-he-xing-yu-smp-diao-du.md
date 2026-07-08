# 09-CPU 亲和性与 SMP 调度深入

## 一、为什么需要 CPU 亲和性

在多处理器（SMP）系统中，Linux 内核默认采用完全公平调度器（CFS）来在各个 CPU 之间分配任务。这种自动负载均衡虽然能保证总体吞吐量，但在特定场景下会导致性能回退：

- **缓存失效**：当进程被迁移到另一个 CPU 时，该 CPU 的 L1/L2 缓存中没有该进程的缓存数据，导致大量缓存未命中。
- **NUMA 远程访问**：在 NUMA 架构下，进程被迁移到远端节点会导致内存访问延迟翻倍。
- **实时性抖动**：对延迟敏感的任务（如高频交易、音视频处理）不希望被调度器随意迁移。

CPU 亲和性（Affinity）允许用户或内核指定某个进程/线程“偏好”在哪些 CPU 上运行，从而在吞吐量和延迟之间取得平衡。

## 二、内核调度域与负载均衡

### 1. 调度域（Scheduling Domain）

Linux 内核使用**调度域**这一层次结构来组织 SMP 系统中的 CPU：

- **SMT 域**：同一物理核心上的超线程（逻辑 CPU）
- **MC 域**：同一 CPU 封装/芯片上的所有核心
- **NUMA 域**：同一 NUMA 节点内的所有 CPU
- **ALL 域**：系统中所有 CPU

```
系统调度域层次
├─ Node 0 (NUMA域)
│  ├─ Package 0 (MC域)
│  │  ├─ Core 0 (SMT域)
│  │  │  ├─ CPU 0
│  │  │  └─ CPU 1 (超线程)
│  │  └─ Core 1
│  └─ Package 1
└─ Node 1 (NUMA域)
```

调度器在**每个域**内做负载均衡，优先在更小的域（SMT → MC → NUMA）内进行迁移，以最小化缓存和 NUMA 代价。

### 2. 负载均衡触发时机

| 触发类型 | 时机 | 说明 |
|----------|------|------|
| 周期性均衡 | `scheduler_tick()` | 每 `SCHED_DOMAIN` 层级定期检查 |
| 空闲均衡 | `idle_balance()` | CPU 进入空闲时，从其他 CPU pull 任务 |
| 新唤醒均衡 | `wake_balance()` | 任务唤醒时，选择最优 CPU 运行 |
| 主动均衡 | `nohz_idle_balance()` | `nohz` CPU 的异步均衡 |

```c
// kernel/sched/fair.c
static void rebalance_domains(struct rq *rq, enum cpu_idle_type idle)
{
    for_each_domain(cpu, sd) {
        if (time_after(jiffies, sd->last_balance + sd->balance_interval)) {
            if (load_balance(cpu, rq, sd, idle, &balance))
                break; // 成功迁移则停止向上
        }
    }
}
```

## 三、CPU 亲和性 API

### 1. 用户态接口

Linux 提供了 `sched_setaffinity()` 系统调用来设置进程的 CPU 亲和性掩码：

```c
#include <sched.h>

// 设置进程 PID 的 CPU 亲和性
int sched_setaffinity(pid_t pid, size_t cpusetsize, const cpu_set_t *mask);
// 获取当前 CPU 亲和性
int sched_getaffinity(pid_t pid, size_t cpusetsize, cpu_set_t *mask);
```

**使用示例**：

```c
#include <sched.h>
#include <stdio.h>

int main() {
    cpu_set_t cpuset;
    CPU_ZERO(&cpuset);
    CPU_SET(2, &cpuset);  // 绑定到 CPU 2
    CPU_SET(3, &cpuset);  // 同时绑定到 CPU 3

    if (sched_setaffinity(0, sizeof(cpuset), &cpuset) == -1) {
        perror("sched_setaffinity");
        return 1;
    }

    // 此后进程只会在 CPU 2 或 3 上运行
    while (1) {}
    return 0;
}
```

### 2. 任务调度器视角

在 CFS 中，每个任务 `task_struct` 有两个关键字段：

```c
struct task_struct {
    cpumask_t cpus_mask;      // 允许运行的 CPU 位掩码
    cpumask_t cpus_ptr;       // 实际指向的 cpumask（考虑 cgroup 限制）
    int nr_cpus_allowed;      // 允许的 CPU 数量
    // ...
};
```

当调度器选择下一个运行任务时，`select_task_rq()` 会首先检查 `cpus_mask`：

```c
static int select_task_rq(struct task_struct *p, int cpu, int sd_flags, int wake_flags)
{
    // 如果目标 CPU 不在允许掩码中，则寻找最近允许域
    if (cpumask_test_cpu(cpu, &p->cpus_mask))
        return cpu;

    // 回退：在允许掩码中找负载最低的 CPU
    return cpumask_any_and(&p->cpus_mask, cpu_active_mask);
}
```

### 3. Cgroup v2 的 CPU 亲和性限制

```bash
# 通过 cgroup 限制容器只能使用 CPU 0-3
echo "0-3" > /sys/fs/cgroup/mygroup/cpuset.cpus
echo "0" > /sys/fs/cgroup/mygroup/cpuset.mems
# 将进程加入 cgroup
echo 12345 > /sys/fs/cgroup/mygroup/cgroup.procs
```

此时即使进程调用 `sched_setaffinity()` 请求 CPU 4，内核也会以 `cpuset.cpus` 为实际限制，拒绝越界请求。

## 四、SMP 亲和性内核实现

### 1. `sched_setaffinity` 系统调用流程

```
用户态 sched_setaffinity()
    └─ sys_sched_setaffinity()
        └─ set_cpus_allowed_ptr()
            ├─ 如果目标掩码不包含当前 CPU，触发迁移
            └─ 更新 task_struct.cpus_mask
                └─ 如果正在运行，则调用 migrate_task()
```

`migrate_task()` 的核心逻辑：

```c
// kernel/sched/core.c
static int migrate_task(struct task_struct *p, int dest_cpu)
{
    struct rq *rq = task_rq(p);
    struct rq_flags rf;

    rq_lock(rq, &rf);
    // 唤醒目标 CPU 的迁移线程 (migration/%d)
    p->migrate_state = MIGRATE_PENDING;
    // 将任务从源 RQ 解链，推入目标 CPU 的 wake_list
    rq_unlock(rq, &rf);

    // 目标 CPU 的 migration 线程会调用 __migrate_task()
    return 0;
}
```

### 2. 中断亲和性

除了进程，**中断**也可以绑定到特定 CPU：

```bash
# 查看中断分布
cat /proc/interrupts

# 设置中断 123 的亲和性（CPU 0-3）
echo 0f > /proc/irq/123/smp_affinity

# 永久绑定：在 /etc/default/irqbalance 中设置
IRQBALANCE_ARGS="--hintpolicy=exact"
```

内核中，每个 IRQ 描述符 `struct irq_desc` 包含 `irq_common_data.affinity`：

```c
// include/linux/irqdesc.h
struct irq_desc {
    struct irq_common_data  irq_common_data;
    struct irq_data         irq_data;
    // ...
    cpumask_var_t           affinity;          // 允许的 CPU 掩码
    cpumask_var_t           pending_mask;       // 待更新掩码
};
```

当中断发生时，`__handle_irq_event()` 会优先将中断递送给 `affinity` 掩码中当前空闲或负载较低的 CPU。

## 五、硬亲和性与软亲和性

| 类型 | 机制 | 保证程度 | 适用场景 |
|------|------|----------|----------|
| 硬亲和性 | `isolcpus` + `taskset -c` | 强制绑定，调度器不会迁移 | DPDK、实时内核 |
| 软亲和性 | `sched_setaffinity()` | 优先使用指定 CPU，允许回退 | 普通性能优化 |
| 自然亲和性 | NUMA 自动感知 | 内核自动优化 | 数据库、大数据 |

### `isolcpus` 内核参数

```bash
# 在 GRUB 中启动参数
isolcpus=2,3 nohz_full=2,3 rcu_nocbs=2,3
```

- `isolcpus=2,3`：CPU 2、3 被完全隔离，普通任务不会被调度到这些 CPU
- `nohz_full=2,3`：关闭 CPU 2、3 的 tick 中断，减少抖动
- `rcu_nocbs=2,3`：将 RCU 回调 offload 到别的 CPU

这是实现**用户态轮询**（如 DPDK `lcore`）和**硬实时**的关键基础设施。

## 六、性能验证与调试

### 1. 查看当前亲和性

```bash
# 查看进程的 CPU 亲和性
taskset -pc 12345
# 输出：pid 12345's current affinity list: 2-3

# 查看线程的亲和性
ps -eLo pid,tid,comm,psr | grep myapp
```

### 2. `perf` 验证缓存效果

```bash
# 绑定 CPU 前
perf stat -e cache-misses,cache-references ./benchmark
# 绑定 CPU 后
taskset -c 0 ./benchmark
perf stat -e cache-misses,cache-references ./benchmark
# 通常 cache-misses 会下降 20-50%
```

### 3. 内核跟踪点

```bash
# 跟踪任务迁移事件
sudo perf trace -e sched:sched_migrate_task

# 输出示例：
#  sched:sched_migrate_task: pid=12345, comm=worker, prio=120, orig_cpu=2, dest_cpu=5
```

## 七、总结

| 概念 | 要点 |
|------|------|
| 调度域 | SMT → MC → NUMA → ALL 的层次均衡结构 |
| 负载均衡 | 周期性、空闲唤醒、主动三种触发方式 |
| 用户态 API | `sched_setaffinity()` / `taskset` |
| 中断亲和性 | `/proc/irq/N/smp_affinity` |
| 硬隔离 | `isolcpus` + `nohz_full` 实现用户态轮询 |
| 内核限制 | `cpuset` cgroup 可覆盖用户态设置 |

CPU 亲和性不是万能的。过度绑定会减少调度器的灵活性，导致负载不均。最佳实践是：

1. **对延迟敏感任务**：使用 `isolcpus` 做硬绑定，配合 `nohz_full`
2. **对吞吐敏感任务**：使用 `taskset` 做软绑定，保留负载均衡空间
3. **中断密集型服务**：将网卡中断绑定到特定 CPU，避免与其他任务争用
