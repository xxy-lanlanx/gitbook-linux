# 07-TCP 拥塞控制与内核数据包处理路径

## 一、TCP 拥塞控制概述

TCP 的可靠性不仅体现在重传和确认，更体现在**拥塞控制（Congestion Control）**——一套动态探测网络承载能力、避免拥塞崩溃的算法体系。Linux 内核支持多种拥塞控制算法，通过 `tcp_congestion_ops` 结构注册。

### 1. 拥塞窗口（cwnd）与接收窗口（rwnd）

TCP 发送端实际能发送的数据量受限于：

```
发送窗口 = min(cwnd, rwnd, swnd)
```

- `cwnd`：拥塞窗口，由拥塞控制算法动态调整
- `rwnd`：接收窗口，由接收端通过 ACK 报文通告
- `swnd`：发送缓冲区的可用空间

### 2. Linux 支持的拥塞控制算法

```bash
# 查看当前可用算法
cat /proc/sys/net/ipv4/tcp_available_congestion_control
# 设置默认算法
echo bbr > /proc/sys/net/ipv4/tcp_congestion_control
```

| 算法 | 特点 | 适用场景 |
|------|------|----------|
| Reno | 经典 AIMD，丢包触发减半 | 通用，旧版本默认 |
| CUBIC | 三次函数窗口增长，RTT 公平 | Linux 3.2+ 默认 |
| BBR | 基于带宽和 RTT 估计，不依赖丢包 | 高带宽、高延迟、无线网 |
| Westwood | 带宽估计 + 快速恢复 | 无线网络 |

## 二、CUBIC 算法深入

CUBIC 是 Linux 默认算法，核心思想是**窗口增长与当前窗口和最大窗口的差值成反比**。

```
W(t) = C * (t - K)^3 + W_max
K = cbrt(W_max * (1 - β) / C)
β = 0.7
C = 0.4
```

CUBIC 的 RTT 公平性问题：窗口增长只取决于时间，短 RTT 连接增长更快，长 RTT 连接处于劣势。BBR 正是为解决此问题而生。

## 三、BBR 算法深入

BBR（Bottleneck Bandwidth and RTT）直接测量：

- **BtlBw**：瓶颈带宽
- **RTprop**：传播往返时延

### 1. BBR 核心状态机

| 状态 | 行为 | 触发条件 |
|------|------|----------|
| STARTUP | 指数增长探测带宽 | 初始或重连 |
| DRAIN | 排空队列，降低 inflight | 带宽不再增长 |
| PROBE_BW | 周期探测带宽（98%时间） | 正常传输 |
| PROBE_RTT | 短暂降窗测量最小 RTT | RTprop > 阈值 |

### 2. BBR 内核实现

```c
// net/ipv4/tcp_bbr.c
struct bbr {
    u32 min_rtt_us;      // RTprop
    u32 pacing_rate;     // pacing 发送速率
    u32 cwnd_gain;       // cwnd 增益
    u32 pacing_gain;     // pacing 增益
    u32 full_bw;         // 当前估计的 BtlBw
};

static void bbr_update_model(struct sock *sk, const struct rate_sample *rs)
{
    struct bbr *bbr = inet_csk_ca(sk);
    // 更新最小 RTT
    if (rs->rtt_us >= 0 && bbr->min_rtt_us > rs->rtt_us)
        bbr->min_rtt_us = rs->rtt_us;
    // 更新带宽估计
    bbr->full_bw = max(bbr->full_bw, 
                       rs->delivered * USEC_PER_SEC / rs->interval_us);
}
```

### 3. BBR vs CUBIC 对比

| 维度 | CUBIC | BBR |
|------|-------|-----|
| 拥塞信号 | 丢包 / ECN | 带宽/RTT 测量 |
| 缓冲区要求 | 需要填满 BDP | 主动保持 BDP 的 2 倍 |
| 丢包网络 | 窗口减半，吞吐暴跌 | 不受丢包影响 |
| RTT 公平性 | 差 | 好 |
| 与 Reno 共存 | 公平 | 会占满带宽（侵略性） |

## 四、内核数据包收发路径

### 1. 发送路径（Send Path）

```
用户态 write()
    └─ sock_sendmsg()
        └─ tcp_sendmsg()
            ├─ 将数据拷贝到 sk_buff 链
            ├─ tcp_push()
            │   └─ tcp_write_xmit()
            │       ├─ 检查 cwnd、rwnd、Nagle
            │       └─ tcp_transmit_skb()
            │           ├─ 构造 TCP 头（seq、ack、checksum）
            │           └─ ip_queue_xmit()
            │               ├─ 路由查找
            │               └─ dev_queue_xmit()
            │                   ├─ qdisc（tc）入队
            │                   └─ 网卡驱动 ndo_start_xmit()
            │                       └─ DMA 映射，写入描述符环
            │                           └─ 网卡发送
```

### 2. 接收路径（Receive Path）

```
网卡硬中断
    └─ napi_schedule() / napi_poll()
        └─ 驱动 poll 函数
            ├─ 从 RX 描述符环读取 sk_buff
            ├─ 调用 netif_receive_skb()
            │   └─ 进入 RPS（Receive Packet Steering）
            │       └─ 选择目标 CPU，enqueue 到 backlog
            │           └─ 软中断 NET_RX_SOFTIRQ
            │               └─ process_backlog()
            │                   └─ __netif_receive_skb()
            │                       ├─ 二层处理（ptype_base）
            │                       └─ ip_rcv()
            │                           ├─ 校验 IP 头、分片重组
            │                           └─ tcp_v4_rcv()
            │                               ├-> ESTABLISHED: tcp_rcv_established()
            │                               ├-> LISTEN: tcp_v4_do_rcv()
            │                               └-> 其他: tcp_rcv_state_process()
```

### 3. NAPI 与 RPS 优化

**NAPI（New API）**：传统方式是网卡每收到一个包就触发硬中断，导致中断风暴。NAPI 改为：

1. 硬中断到来时关闭网卡中断，启动 `napi_poll`
2. 在软中断中轮询（poll）批量收包
3. 收完一批后再打开中断

**RPS（Receive Packet Steering）**：将同一流的包哈希到特定 CPU 处理，避免 CPU 争用和缓存失效：

```bash
# 启用 RPS，每个 RX 队列绑定到不同 CPU
echo f > /sys/class/net/eth0/queues/rx-0/rps_cpus
```

## 五、总结

| 技术 | 解决的问题 | 调优命令 |
|------|-----------|----------|
| CUBIC | 现代网络高带宽利用率 | 默认算法 |
| BBR | 高延迟、丢包网络吞吐量 | `echo bbr > tcp_congestion_control` |
| NAPI | 中断风暴 | 自动启用 |
| RPS | 多核收包扩展 | `/sys/class/net/ethX/queues/rx-*/rps_cpus` |
| Pacing | 避免突发丢包 | BBR 自动启用 |

在高性能网络场景中，建议优先测试 BBR + 适当增大 `net.core.rmem_max` / `net.core.wmem_max` 的组合效果。
