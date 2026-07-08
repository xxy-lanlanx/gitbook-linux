# 06-Linux 路由与邻居子系统（ARP）

> 基于 Linux 3.10.29 内核分析。IP 层收到包后需要回答两个问题：「去往哪个出口（路由）？」「下一跳的 MAC 地址是什么（邻居/ARP）？」本章讲解内核的路由子系统与邻居子系统。

## 1. 路由子系统（FIB）

路由子系统的职责：根据目的 IP 决定**从哪个网卡发出、下一跳是谁**。决策依据是**路由表（FIB，Forwarding Information Base）**。

### 1.1 路由查找流程

```text
IP 层要发送目的 IP = D 的包
   │
   ▼
fib_lookup(D)
   ├─ 匹配 主机路由（/32）
   ├─ 匹配 子网路由
   ├─ 匹配 默认路由（0.0.0.0/0）
   └─ 得到：出接口(oif) + 下一跳(gw)
```

路由按**最长前缀匹配（LPM）**：越精确的条目优先。

### 1.2 查看与配置

```bash
ip route show                    # 查看路由表
# default via 192.168.1.1 dev eth0  proto static
# 192.168.1.0/24 dev eth0  scope link

ip route add 10.0.0.0/8 via 192.168.1.254 dev eth0   # 加静态路由
ip route del default                                   # 删默认路由
ip route add default via 192.168.1.1                  # 设默认网关
```

### 1.3 策略路由（多表）

除主表（main），还可按源地址、防火墙标记等用多张表（`ip rule`）选择路由，满足多出口、VPN 分流等需求：

```bash
ip rule add from 192.168.2.0/24 table 100
ip route add default via 10.0.0.1 table 100
```

## 2. 邻居子系统与 ARP

IP 包确定了下一跳 IP（如网关 192.168.1.1），但以太网帧需要**MAC 地址**。邻居子系统负责「IP → MAC」的解析与缓存，在 IPv4 上即 **ARP（Address Resolution Protocol）**。

### 2.1 ARP 过程

```text
本机要发往 192.168.1.1，但不知其 MAC
   │
   ▼
广播 ARP 请求：Who has 192.168.1.1? Tell 本机MAC
   │
   ▼
192.168.1.1 单播回应：192.168.1.1 is at <MAC>
   │
   ▼
本机写入邻居表（ARP 缓存），封装以太网帧发送
```

### 2.2 邻居表（neigh_table）

内核用 `neigh_table` 维护「IP→MAC」缓存，每项状态机：

```text
NONE → INCOMPLETE(已发请求, 等待) → REACHABLE(可达, 已学到)
                                   → STALE(可能过期, 用前验证)
                                   → DELAY / PROBE(探测)
                                   → FAILED
```

相关结构：

```c
struct neighbour {
    struct net_device *dev;     /* 所属网卡 */
    __u8 nud_state;             /* 状态机 */
    unsigned char ha[ALEN];     /* 解析到的 MAC */
    ...;
};
```

### 2.3 查看与操作 ARP

```bash
ip neigh show                    # 查看 ARP/邻居缓存
# 192.168.1.1 dev eth0 lladdr 00:11:22:33:44:55 router STALE

ip neigh flush dev eth0          # 清空某网卡邻居表
arping -I eth0 192.168.1.1       # 手动发 ARP 探测
```

### 2.4 代理 ARP 与免费 ARP

- **代理 ARP**：路由器代为回答本网段外 IP 的 ARP，让主机以为同网段（早期透明子网）；
- **免费 ARP（Gratuitous ARP）**：主机主动广播「我的 IP 是 X，MAC 是 Y」，用于 IP 冲突检测与故障切换（如 VIP 漂移时通知交换机更新）。

## 3. 发送路径的协作

```text
TCP/UDP 交包给 IP 层
   → 路由查找(fib_lookup)：确定 oif + 下一跳 gw
   → 邻居解析(arp_bind_neighbour)：确保有 gw 的 MAC
   → 封装以太网头(dst mac = 邻居 MAC)
   → dev_hard_start_xmit → 网卡驱动发送（见设备驱动 05 章）
```

## 4. 小结

路由子系统（FIB）回答「走哪个口、下一跳谁」，邻居子系统（ARP）回答「下一跳的 MAC 是什么」。二者是 IP 包离开发送主机前的最后两步，与网络驱动、Netfilter 紧密协作，构成完整的数据包发送链路。
