# 05-Linux Netfilter 与 iptables

> 基于 Linux 3.10.29 内核分析。Netfilter 是内核网络栈中的包处理框架，iptables 是它最常用的用户态配置工具。防火墙、NAT、端口映射都建立在它之上。

## 1. Netfilter 的 5 个钩子点

Netfilter 在网络栈的关键路径上预埋了**钩子（hook）**，包经过时被回调：

```text
                ┌─────────────── 路由判断 ───────────────┐
                │                                        │
  入包 ──PREROUTING──> [路由: 本机?] ──是──> INPUT ──> 本机进程
                       │                                  │
                       否                                  │
                       ▼                                  │
                   FORWARD ──POSTROUTING──> 出包 ──────────┘
                       ▲
                       │ (转发)
                  OUTPUT <── 本机进程发出的包
```

五个钩子：
- **PREROUTING**：路由前（刚进网络层，常用于 DNAT）；
- **INPUT**：发往本机的包；
- **FORWARD**：转发的包；
- **OUTPUT**：本机发出的包；
- **POSTROUTING**：路由后、出网卡前（常用于 SNAT）。

## 2. iptables 的表与链

iptables 把规则组织为「表（table）」与「链（chain）」：

| 表 | 用途 | 主要链 |
|----|------|--------|
| filter | 过滤（默认） | INPUT / FORWARD / OUTPUT |
| nat | 地址转换 | PREROUTING / POSTROUTING / OUTPUT |
| mangle | 修改包头（TOS/TTL/标记） | 全部 |
| raw | 跳过连接跟踪 | PREROUTING / OUTPUT |

包经过某链时，按规则**顺序匹配**，命中后执行「目标（target）」：`ACCEPT`（放行）、`DROP`（丢弃）、`REJECT`（拒绝并回包）、`DNAT`/`SNAT`（改地址）、`LOG`（记录）等。

### 2.1 过滤示例

```bash
# 放行本机已建立/相关连接，丢弃其他入站
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -p tcp --dport 22 -j ACCEPT     # 允许 SSH
iptables -A INPUT -j DROP                          # 其余丢弃

# 查看规则
iptables -L -n -v
```

### 2.2 NAT 示例（家庭路由器/容器）

```bash
# 出口做 SNAT（内网共享公网 IP）
iptables -t nat -A POSTROUTING -s 192.168.1.0/24 -o eth0 -j MASQUERADE

# 端口映射 DNAT：把公网 :8080 转到内网 192.168.1.10:80
iptables -t nat -A PREROUTING -p tcp --dport 8080 \
         -j DNAT --to-destination 192.168.1.10:80
```

### 2.3 记录与标记

```bash
iptables -A INPUT -p tcp --dport 80 -j LOG --log-prefix "HTTP-IN: "
iptables -t mangle -A PREROUTING -p tcp --dport 80 -j MARK --set-mark 1
```

## 3. 连接跟踪（conntrack）

`state`/`MASQUERADE` 背后是 **连接跟踪子系统（nf_conntrack）**，它记录每个连接的五元组与状态（NEW/ESTABLISHED/RELATED），是 NAT 与状态防火墙的基础。

```bash
cat /proc/net/nf_conntrack        # 查看当前连接表
sysctl net.netfilter.nf_conntrack_max   # 连接表容量上限
```

> 高并发网关场景 `nf_conntrack_max` 过小会丢包，需要调大；若不需要状态跟踪可用 `raw` 表 `NOTRACK` 关闭。

## 4. 内核实现要点

- 各表用 `iptables`/`nf_tables` 规则，**编译成字节码**挂在钩子上；
- 包处理函数 `ipt_do_table()` 遍历匹配，命中目标执行回调；
- 新内核推荐 `nftables`（统一框架），但 3.10 仍以 iptables/Netfilter 为主流。

## 5. 小结

Netfilter 用 5 个钩子点切入网络栈，iptables 按「表-链-规则-目标」组织策略，实现过滤、NAT 与标记。理解包在 PREROUTING/INPUT/FORWARD/OUTPUT/POSTROUTING 间的流向，是配置任何 Linux 防火墙的前提。
