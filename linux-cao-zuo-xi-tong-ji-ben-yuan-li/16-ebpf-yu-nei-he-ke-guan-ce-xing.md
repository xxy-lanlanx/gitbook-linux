# 16-eBPF 与内核可观测性

## 一、eBPF 是什么

eBPF（extended Berkeley Packet Filter）是 Linux 内核的一项革命性技术，允许用户在内核中安全地执行自定义字节码，无需修改内核源码或加载内核模块。

从最初的网络包过滤（BPF）发展到今天的 eBPF，它已经覆盖：

- **网络**：数据包过滤、负载均衡、流量控制（XDP、tc、socket filter）
- **可观测性**：性能分析、动态跟踪、系统调用监控（kprobe、uprobe、tracepoint）
- **安全**：系统调用审计、沙箱策略（LSM BPF）
- **存储**：文件系统过滤、设备 I/O 监控

## 二、eBPF 的执行模型

### 1. 加载与验证

```
用户空间（C/BCC/libbpf）
    │
    │ 编译为 eBPF 字节码（LLVM/Clang）
    ▼
  bpf() 系统调用
    │
    ▼
内核空间
  ├─ eBPF 验证器（Verifier）
  │   ├─ 检查无循环（有界循环）
  │   ├─ 检查无空指针解引用
  │   ├─ 检查无越界访问
  │   └─ 检查程序复杂度（指令数限制）
  │
  ├─ JIT 编译器（x86/ARM64）
  │   └─ 字节码 → 本地机器码
  │
  └─ 挂载到事件点（Hook）
      ├─ kprobe（内核函数入口/返回）
      ├─ tracepoint（内核静态跟踪点）
      ├─ XDP（网卡驱动层）
      ├─ tc（流量控制）
      └─ LSM（安全模块）
```

### 2. 关键限制

| 限制 | 说明 | 配置 |
|------|------|------|
| 指令数 | 最大 1M 指令（内核 5.2+） | `BPF_MAXINSNS` |
| 栈大小 | 512 字节 | 固定 |
| 辅助函数 | 只能从白名单调用 | `bpf_helps[]` |
| 循环 | 必须编译时可确定上界 | 内核 5.3+ 支持有限循环 |
| Map 类型 | 预定义的内核与用户共享结构 | `BPF_MAP_TYPE_*` |

## 三、eBPF 程序类型与使用场景

| 程序类型 | 挂载点 | 典型用途 |
|----------|--------|----------|
| `BPF_PROG_TYPE_KPROBE` | 任意内核函数 | 动态跟踪内核函数调用 |
| `BPF_PROG_TYPE_TRACEPOINT` | 内核静态跟踪点 | 低开销系统调用跟踪 |
| `BPF_PROG_TYPE_XDP` | 网卡驱动层 | 高速包过滤（DDoS 防护） |
| `BPF_PROG_TYPE_SCHED_CLS/ACT` | tc 流量控制 | 高级路由、QoS |
| `BPF_PROG_TYPE_SOCKET_FILTER` | 套接字层 | 网络监控 |
| `BPF_PROG_TYPE_LSM` | 安全钩子 | 自定义安全策略 |
| `BPF_PROG_TYPE_SYSCALL` | 直接调用 | 用户态直接执行内核态逻辑 |

## 四、Map：内核与用户空间的桥梁

eBPF Map 是内核中键值对存储，供 eBPF 程序和用户态程序共享数据：

| Map 类型 | 特性 | 用途 |
|----------|------|------|
| `BPF_MAP_TYPE_HASH` | 通用哈希表 | 进程 PID → 统计信息 |
| `BPF_MAP_TYPE_ARRAY` | 固定大小数组 | 全局计数器 |
| `BPF_MAP_TYPE_PERCPU_HASH` | 每 CPU 独立哈希 | 避免缓存竞争 |
| `BPF_MAP_TYPE_LRU_HASH` | 自动淘汰最近最少使用 | 连接跟踪 |
| `BPF_MAP_TYPE_RINGBUF` | 环形缓冲区 | 内核 → 用户态事件流 |
| `BPF_MAP_TYPE_STACK_TRACE` | 存储栈跟踪 | 性能分析 |

```c
// 内核态 eBPF 程序
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 1024);
    __type(key, u32);      // PID
    __type(value, u64);    // 计数
} counter_map SEC(".maps");

SEC("kprobe/__x64_sys_write")
int trace_write(struct pt_regs *ctx)
{
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u64 *count = bpf_map_lookup_elem(&counter_map, &pid);
    if (count) {
        __sync_fetch_and_add(count, 1);
    }
    return 0;
}
```

```python
# 用户态（Python + BCC）
from bcc import BPF

bpf = BPF(src_file="trace_write.c")
map = bpf["counter_map"]

for k, v in map.items():
    print(f"PID {k.value}: {v.value} writes")
```

## 五、XDP：内核最快的包处理

XDP（eXpress Data Path）在网卡驱动层直接处理数据包，**甚至早于内核网络栈**：

```
数据包到达
    │
    ▼
网卡 DMA
    │
    ▼
┌──────────┐
│  XDP 钩子 │  ← 最早的 eBPF 挂载点（驱动层）
│  直接返回：│     XDP_DROP / XDP_PASS / XDP_TX / XDP_REDIRECT
└──────────┘
    │
    ▼（如果 PASS）
内核网络栈（skb 分配）
    │
    ▼
tc ingress（eBPF 可挂载）
    │
    ▼
ip_rcv() → tcp_v4_rcv()
```

**XDP 三种模式**：

| 模式 | 挂载位置 | 延迟 | 要求 |
|------|----------|------|------|
| Offload | 网卡硬件 | < 1μs | 智能网卡支持 |
| Driver | 网卡驱动 | 1-2μs | 驱动支持 XDP |
| Generic | 内核 skb 层 | 5-10μs | 通用，无需驱动支持 |

```c
// XDP 程序示例：丢弃所有 UDP 包
SEC("xdp")
int xdp_drop_udp(struct xdp_md *ctx)
{
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;
    struct ethhdr *eth = data;

    if (eth + 1 > data_end)
        return XDP_PASS;

    if (eth->h_proto == __constant_htons(ETH_P_IP)) {
        struct iphdr *ip = data + sizeof(*eth);
        if (ip + 1 > data_end)
            return XDP_PASS;
        if (ip->protocol == IPPROTO_UDP)
            return XDP_DROP;  // 丢弃 UDP
    }
    return XDP_PASS;
}
```

## 六、CO-RE：一次编译，到处运行

传统 eBPF 程序依赖内核数据结构布局，换内核版本需要重新编译。CO-RE（Compile Once - Run Everywhere）通过 BTF（BPF Type Format）解决：

```c
// 使用 BPF_CORE_READ 宏，自动处理内核结构偏移差异
struct task_struct *task = (struct task_struct *)bpf_get_current_task();

// 旧方式：直接访问，不同内核版本可能偏移不同
// u32 pid = task->pid;

// CO-RE 方式：安全读取
u32 pid = BPF_CORE_READ(task, pid);
```

BTF 是内核数据结构的 DWARF 子集，包含类型和偏移信息。加载时 eBPF 加载器根据运行内核的 BTF 自动重定位字段访问。

## 七、libbpf 与 BPF Skeleton

现代 eBPF 开发推荐使用 `libbpf` + BPF Skeleton（BPF 骨架）：

```c
// 自动生成 skeleton：bpftool gen skeleton myprog.bpf.o > myprog.skel.h
#include "myprog.skel.h"

int main()
{
    struct myprog_bpf *skel;
    int err;

    // 自动加载、验证、创建 Map、附加到事件
    skel = myprog_bpf__open_and_load();
    if (!skel) return 1;

    err = myprog_bpf__attach(skel);
    if (err) return 1;

    // 读取 Map
    while (1) {
        sleep(1);
        // 访问 skel->maps.counter_map
    }

    myprog_bpf__destroy(skel);
    return 0;
}
```

## 八、实战：跟踪文件打开延迟

```c
// file_open.bpf.c
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 10240);
    __type(key, u32);
    __type(value, u64);
} start_ns SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 256 * 1024);
} events SEC(".maps");

struct event {
    u32 pid;
    u64 delta_ns;
    char comm[16];
    char fname[256];
};

SEC("kprobe/do_filp_open")
int BPF_KPROBE(entry, int dfd, struct filename *name)
{
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u64 ts = bpf_ktime_get_ns();
    bpf_map_update_elem(&start_ns, &pid, &ts, BPF_ANY);
    return 0;
}

SEC("kretprobe/do_filp_open")
int BPF_KRETPROBE(exit)
{
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u64 *start = bpf_map_lookup_elem(&start_ns, &pid);
    if (!start) return 0;

    u64 delta = bpf_ktime_get_ns() - *start;
    bpf_map_delete_elem(&start_ns, &pid);

    struct event *e = bpf_ringbuf_reserve(&events, sizeof(*e), 0);
    if (!e) return 0;

    e->pid = pid;
    e->delta_ns = delta;
    bpf_get_current_comm(&e->comm, sizeof(e->comm));
    bpf_ringbuf_submit(e, 0);
    return 0;
}

char _license[] SEC("license") = "GPL";
```

## 九、调试与工具链

| 工具 | 用途 |
|------|------|
| `bpftool` | 加载、查看、导出 eBPF 程序、Map、BTF |
| `bpftrace` | 高级声明式跟踪语言，一行命令完成分析 |
| `BCC` | Python/C++ 框架，快速编写 eBPF 工具 |
| `libbpf` | C 库，生产环境推荐 |
| `perf` | 与 eBPF 结合进行热点分析 |

```bash
# 查看系统已加载的 eBPF 程序
bpftool prog list

# 查看 Map 内容
bpftool map dump id 123

# 导出内核 BTF
bpftool btf dump file /sys/kernel/btf/vmlinux format c

# bpftrace 一行命令：跟踪每个 execve 的参数
bpftrace -e 'tracepoint:sysclls:syscll_execve { printf("exec: %s\n", args->filename); }'
```

## 十、总结

| 概念 | 要点 |
|------|------|
| eBPF | 内核安全执行环境，字节码 + 验证器 + JIT |
| 核心优势 | 无需改内核、零开销（JIT 后）、动态加载 |
| XDP | 最内层的网络包处理，可替代 DPDK 部分场景 |
| Map | 内核态与用户态的数据交换通道 |
| CO-RE | 通过 BTF 实现跨内核版本兼容 |
| 工具链 | libbpf（生产）、bpftrace（快速调试）、BCC（原型） |

eBPF 正在重塑 Linux 系统的可观测性和网络处理方式。从云原生监控（Falco、Pixie、Cilium）到高性能网络（Cloudflare DDoS 防护），eBPF 已成为现代基础设施的核心技术之一。
