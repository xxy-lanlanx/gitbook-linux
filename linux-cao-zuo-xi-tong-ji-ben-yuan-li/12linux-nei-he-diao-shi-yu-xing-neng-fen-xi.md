# 12-Linux 内核调试与性能分析

> 内核调试比用户程序调试困难得多——没有 printf，可能无法使用 gdb，中断上下文不能睡眠，一个 bug 可能让系统崩溃。掌握内核调试和性能分析工具，是内核开发者的必备技能。

## 1. printk：内核的 "printf"

`printk` 是内核中最基础的日志输出函数，类似用户态的 `printf`，但输出到内核环形缓冲区（kernel ring buffer），可通过 `dmesg` 或 `/proc/kmsg` 查看。

```c
printk(KERN_INFO "Hello from kernel, value=%d\n", value);
```

### 1.1 日志级别

| 级别 | 宏 | 说明 |
|------|-----|------|
| 0 | KERN_EMERG | 系统崩溃，无法使用 |
| 1 | KERN_ALERT | 必须立即处理 |
| 2 | KERN_CRIT | 严重错误 |
| 3 | KERN_ERR | 错误 |
| 4 | KERN_WARNING | 警告 |
| 5 | KERN_NOTICE | 注意 |
| 6 | KERN_INFO | 信息 |
| 7 | KERN_DEBUG | 调试信息 |

```bash
# 查看内核日志
dmesg | tail -50

# 查看日志级别
# 默认控制台级别为 7，只显示 <=7 的信息
cat /proc/sys/kernel/printk
# 输出：7 4 1 7  （当前级别、默认级别、最小级别、boot默认级别）

# 提高日志级别，显示更多调试信息
echo 8 | sudo tee /proc/sys/kernel/printk
```

### 1.2 printk 的注意事项

- 中断上下文可以调用 `printk`，但不要用 `printk` 做轮询调试（日志量过大）。
- 使用 `pr_debug()` 代替 `printk(KERN_DEBUG ...)`，通过 `DEBUG` 宏控制编译时开关。
- `printk` 使用自旋锁保护缓冲区，极端高频场景可能引发性能问题或死锁。

## 2. 动态调试（Dynamic Debug）

Linux 内核支持在运行时动态开启/关闭 `pr_debug()` 和 `dev_dbg()` 输出，无需重新编译。

```bash
# 查看所有可动态调试的日志点
cat /sys/kernel/debug/dynamic_debug/control

# 开启某个文件的所有调试日志
echo 'file mydriver.c +p' > /sys/kernel/debug/dynamic_debug/control

# 开启某个函数内的调试日志
echo 'func my_function +p' > /sys/kernel/debug/dynamic_debug/control

# 按模块名开启
echo 'module mymodule +p' > /sys/kernel/debug/dynamic_debug/control

# 关闭
echo 'file mydriver.c -p' > /sys/kernel/debug/dynamic_debug/control
```

## 3. Oops 与 Panic 分析

当内核遇到严重错误（如空指针解引用、内存越界）时，会打印 **Oops** 信息；如果错误无法恢复，则触发 **Panic**。

### 3.1 Oops 信息解读

```
Unable to handle kernel NULL pointer dereference at virtual address 00000000
pc : my_function+0x24/0x80 [mymodule]
sp : ffff888012345678
Call trace:
 my_function+0x24/0x80
 my_ioctl+0x100/0x200
 do_vfs_ioctl+0x...
```

关键信息：
- **错误类型**：NULL pointer dereference、page fault 等。
- **PC（Program Counter）**：出错的指令地址，如 `my_function+0x24`。
- **Call Trace**：函数调用栈，从出错点到系统调用入口。
- **寄存器状态**：R0-R15、SP、LR 等，用于定位问题。

### 3.2 使用 addr2line 定位源码

```bash
# 根据 Oops 中的地址找到源码行
addr2line -e /path/to/vmlinux -a 0xffffffff8a1b2c3d
addr2line -e /path/to/mymodule.ko -a 0x24

# 或者使用 gdb
gdb /path/to/vmlinux
(gdb) list *(my_function+0x24)
```

### 3.3 使用 Kdump 捕获崩溃信息

Kdump 在系统崩溃时启动第二个内核（捕获内核），将第一个内核的内存转储到磁盘，用于事后分析。

```bash
# 安装 kdump
centos: sudo yum install kexec-tools
debian: sudo apt install linux-crashdump

# 配置
sudo systemctl enable kdump
sudo systemctl start kdump

# 触发崩溃测试（小心！）
echo c | sudo tee /proc/sysrq-trigger

# 分析 vmcore
crash /usr/lib/debug/lib/modules/$(uname -r)/vmlinux /var/crash/xxx/vmcore
```

## 4. ftrace：内核函数跟踪器

ftrace 是 Linux 内核内置的**动态跟踪**框架，无需加载任何外部模块，开销极低。

### 4.1 基本使用

```bash
# 挂载 tracefs
sudo mount -t tracefs tracefs /sys/kernel/tracing

# 查看可用的跟踪器
cat /sys/kernel/tracing/available_tracers
# 输出：function_graph function nop blk mmiotrace

# 启用函数跟踪
echo function > /sys/kernel/tracing/current_tracer

# 只跟踪特定函数
echo my_function > /sys/kernel/tracing/set_ftrace_filter

# 开始跟踪
echo 1 > /sys/kernel/tracing/tracing_on

# 运行测试程序...

# 查看结果
cat /sys/kernel/tracing/trace

# 停止
echo 0 > /sys/kernel/tracing/tracing_on
```

### 4.2 function_graph 跟踪器

显示函数调用的进入/返回时间和嵌套关系：

```bash
echo function_graph > /sys/kernel/tracing/current_tracer
echo 1 > /sys/kernel/tracing/tracing_on
# 运行程序...
cat /sys/kernel/tracing/trace

# 输出示例：
# 0)               |  do_sys_open() {
# 0)               |    getname() {
# 0)   0.123 us    |      __getname();
# 0)   1.456 us    |    }
# 0)               |    do_filp_open() {
# ...
```

### 4.3 使用 tracepoint

tracepoint 是内核预定义的静态探测点，比函数跟踪更稳定（不会因函数改名而失效）。

```bash
# 查看可用 tracepoint
cat /sys/kernel/tracing/events/enable
ls /sys/kernel/tracing/events/sched/  # 调度相关
ls /sys/kernel/tracing/events/syscalls/  # 系统调用

# 启用 sched_switch tracepoint
echo 1 > /sys/kernel/tracing/events/sched/sched_switch/enable

# 查看结果
cat /sys/kernel/tracing/trace
```

## 5. perf：Linux 性能分析神器

perf 是 Linux 内核提供的性能分析工具集，基于硬件 PMU（Performance Monitoring Unit）计数器，可以分析 CPU 周期、缓存命中、分支预测、内核热点等。

### 5.1 常用命令

```bash
# 查看系统支持的 perf 事件
perf list

# 统计 CPU 周期热点（CPU 在哪里花时间）
sudo perf top

# 记录某个程序的性能数据
perf record ./my_program
perf report  # 交互式分析

# 分析内核热点
sudo perf record -a -g -- sleep 10
sudo perf report --sort=dso,symbol

# 查看缓存命中率
perf stat -e cache-misses,cache-references ./my_program

# 跟踪系统调用
perf trace ./my_program

# 火焰图生成
perf record -F 99 -a -g -- sleep 30
perf script | ./stackcollapse-perf.pl | ./flamegraph.pl > kernel.svg
```

### 5.2 perf 火焰图

火焰图是可视化性能瓶颈的利器：

```bash
# 1. 记录调用栈
sudo perf record -F 99 -a -g -- sleep 30

# 2. 生成折叠栈
perf script | ./stackcollapse-perf.pl > out.folded

# 3. 生成火焰图
./flamegraph.pl out.folded > kernel.svg
```

火焰图阅读要点：
- **宽度**代表在总采样时间中的占比，越宽越热。
- **纵轴**代表调用栈深度，从下往上是调用关系。
- **颜色**只用于区分不同的函数，不代表温度。

## 6. eBPF 与 BCC：现代内核跟踪

eBPF（Extended Berkeley Packet Filter）是 Linux 3.15+ 引入的革命性技术，允许在用户态编写小程序，安全地运行在内核态。

### 6.1 eBPF 的特点

- **安全**：通过内核验证器（verifier）检查，防止死循环、空指针、无限内存访问。
- **高效**：JIT 编译为本地机器码，执行效率接近原生。
- **灵活**：可以挂载到 kprobe、tracepoint、uprobe、socket 等多个钩子点。

### 6.2 BCC 工具集

BCC（BPF Compiler Collection）是 eBPF 的前端工具集，提供大量开箱即用的工具：

```bash
# 安装 BCC
sudo apt install bpfcc-tools

# 查看 IO 延迟分布
sudo biolatency-bpfcc

# 查看文件系统操作
sudo ext4slower-bpfcc  # 只打印慢于阈值的 ext4 操作

# 查看 TCP 生命周期
sudo tcplife-bpfcc

# 查看 off-CPU 时间
sudo offcputime-bpfcc

# 查看内存分配栈
sudo memleak-bpfcc -a  # 跟踪内存泄漏

# 查看调度延迟
sudo runqlat-bpfcc  # 任务在 runqueue 中等待的时间分布
```

### 6.3 写一个 eBPF 程序（Python 前端）

```python
#!/usr/bin/env python3
from bcc import BPF

# C 代码会在内核态执行
prog = """
#include <uapi/linux/ptrace.h>

BPF_HASH(start, u32);

int trace_entry(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid();
    u64 ts = bpf_ktime_get_ns();
    start.update(&pid, &ts);
    return 0;
}

int trace_return(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid();
    u64 *tsp = start.lookup(&pid);
    if (tsp != 0) {
        u64 delta = bpf_ktime_get_ns() - *tsp;
        bpf_trace_printk("elapsed %llu ns\\n", delta);
        start.delete(&pid);
    }
    return 0;
}
"""

b = BPF(text=prog)
b.attach_kprobe(event="do_sys_open", fn_name="trace_entry")
b.attach_kretprobe(event="do_sys_open", fn_name="trace_return")

print("Tracing... Hit Ctrl-C to exit.")
while True:
    try:
        (task, pid, cpu, flags, ts, msg) = b.trace_fields()
        print(f"{task}({pid}): {msg}")
    except KeyboardInterrupt:
        break
```

## 7. SysRq：紧急调试键

当系统僵死（无法响应任何输入）时，可以通过 SysRq 键（Alt + PrintScreen + 命令键）触发内核的紧急操作：

```bash
# 开启 SysRq
echo 1 | sudo tee /proc/sys/kernel/sysrq

# 常用 SysRq 命令（通过 /proc/sysrq-trigger 模拟）
echo m | sudo tee /proc/sysrq-trigger  # 打印内存信息
echo t | sudo tee /proc/sysrq-trigger  # 打印所有任务栈
echo p | sudo tee /proc/sysrq-trigger  # 打印当前 CPU 寄存器
echo c | sudo tee /proc/sysrq-trigger  # 故意触发 panic（测试 kdump）
echo s | sudo tee /proc/sysrq-trigger  # 同步所有文件系统
echo b | sudo tee /proc/sysrq-trigger  # 立即重启（不卸载文件系统！）
```

> 在键盘上直接按：Alt + PrintScreen + m（需要内核开启 CONFIG_MAGIC_SYSRQ）

## 8. KGDB：用 GDB 调试内核

KGDB 允许通过串口或网络用 GDB 远程调试运行中的内核，类似于用 GDB 调试嵌入式程序。

```bash
# 内核启动参数加入：
kgdboc=ttyS0,115200 kgdbwait

# 在另一台机器上：
gdb ./vmlinux
(gdb) target remote /dev/ttyS0

# 现在可以设置断点、单步、查看变量
(gdb) break start_kernel
(gdb) continue
(gdb) next
(gdb) print jiffies
```

## 9. 内核调试策略总结

| 场景 | 推荐工具 | 说明 |
|------|---------|------|
| 简单的日志输出 | `printk` / `pr_debug` | 最基础，但会影响性能 |
| 大量的动态日志 | `dynamic_debug` | 运行时开关，无需重编译 |
| 内核崩溃分析 | `dmesg` + `addr2line` | 根据 Oops 地址定位源码 |
| 系统崩溃后分析 | `kdump` + `crash` | 捕获崩溃时的内存镜像 |
| 函数级热点分析 | `ftrace` | 低开销，适合长期跟踪 |
| 全系统性能分析 | `perf` | 基于硬件 PMU，精确高效 |
| 可视化性能瓶颈 | `perf` + `火焰图` | 一眼看出哪里最慢 |
| 自定义内核探测 | `eBPF` / `BCC` | 现代、安全、功能强大 |
| 系统僵死 | `SysRq` | 最后的救命稻草 |
| 源码级调试 | `KGDB` | 类似嵌入式 GDB 调试 |

## 10. 小结

- **printk** 是内核调试的起点，但应避免过度使用。
- **Oops/Panic** 信息是内核崩溃的"黑匣子"，要学会解读。
- **ftrace** 是低开销的函数跟踪利器，适合排查调用流程问题。
- **perf** 是性能分析的瑞士军刀，结合火焰图能直观定位瓶颈。
- **eBPF/BCC** 是现代内核跟踪的趋势，安全、高效、灵活。
- **SysRq** 是系统僵死时的最后手段。

内核调试没有银弹，需要结合场景选择工具。从 `printk` 到 `ftrace` 到 `perf` 到 `eBPF`，是内核开发者从入门到精通的工具升级路径。
