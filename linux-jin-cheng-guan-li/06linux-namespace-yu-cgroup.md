# 06-Linux Namespace 与 Cgroup

> Namespace 和 Cgroup 是 Linux 容器（Docker/LXC/Kubernetes）的两大基石。Namespace 提供隔离，Cgroup 提供资源限制。理解它们，就理解了现代云原生技术的底层。

## 1. Namespace：资源隔离

Namespace 是 Linux 内核的一项机制，将全局系统资源进行封装，使一个进程只能看到属于自己的资源视图。不同 Namespace 中的进程彼此隔离，互不可见。

### 1.1 六种 Namespace

| Namespace | 宏定义 | 隔离资源 | 引入内核版本 |
|-----------|--------|---------|-------------|
| Mount | CLONE_NEWNS | 文件系统挂载点 | 2.4.19 |
| UTS | CLONE_NEWUTS | 主机名和域名 | 2.6.19 |
| IPC | CLONE_NEWIPC | 进程间通信（信号量、共享内存、消息队列） | 2.6.19 |
| PID | CLONE_NEWPID | 进程号空间 | 2.6.24 |
| Network | CLONE_NEWNET | 网络设备、端口、路由、防火墙 | 2.6.29 |
| User | CLONE_NEWUSER | 用户和用户组 ID | 3.8 |
| Cgroup | CLONE_NEWCGROUP | Cgroup 根目录视图 | 4.6 |

> 现在常说的 "Linux 容器"，本质上就是一组进程运行在一组独立的 Namespace 中。

### 1.2 创建 Namespace

通过 `clone()`、`unshare()` 或 `setns()` 系统调用来创建或加入 Namespace：

```c
/* clone：创建新进程并同时创建新的 Namespace */
pid_t pid = clone(child_fn, child_stack + STACK_SIZE,
                  CLONE_NEWUTS | CLONE_NEWIPC | CLONE_NEWPID | 
                  CLONE_NEWNS | CLONE_NEWNET | CLONE_NEWUSER | SIGCHLD,
                  NULL);
```

```bash
# unshare：当前进程退出某个 Namespace，进入新的 Namespace
sudo unshare --uts --ipc --pid --net --mount --user /bin/bash

# 进入已有 Namespace（setns）
sudo nsenter --target <pid> --all /bin/bash
```

### 1.3 PID Namespace 示例

PID Namespace 是最经典的隔离：

```bash
# 创建一个新的 PID namespace
sudo unshare --pid --fork --mount-proc /bin/bash

# 在新 namespace 中，bash 的 PID 变成了 1
echo $$
# 输出：1

# 查看进程，只能看到自己 namespace 的进程
ps aux
# 输出只有 bash 和 ps 两个进程
```

> 在 PID Namespace 中，PID 1 是一个特殊进程：如果它退出，内核会发送 SIGKILL 给 namespace 中所有其他进程。这就是为什么容器里必须有一个前台进程作为 PID 1。

### 1.4 Network Namespace 示例

Network Namespace 隔离网络设备、IP 地址、路由表、防火墙规则：

```bash
# 创建新的 Network Namespace
sudo ip netns add myns

# 在 namespace 中执行命令
sudo ip netns exec myns ip addr
# 只能看到 loopback 接口

# 创建 veth pair（虚拟以太网对），连接两个 namespace
sudo ip link add veth0 type veth peer name veth1
sudo ip link set veth1 netns myns

# 配置 IP
sudo ip addr add 10.0.0.1/24 dev veth0
sudo ip netns exec myns ip addr add 10.0.0.2/24 dev veth1
sudo ip link set veth0 up
sudo ip netns exec myns ip link set veth1 up

# 测试连通
ping 10.0.0.2
```

## 2. Cgroup：资源限制与统计

Cgroup（Control Group）是 Linux 内核的机制，用于对进程组进行资源限制、优先级控制和统计。

### 2.1 Cgroup v1 vs v2

| 特性 | Cgroup v1 | Cgroup v2 |
|------|-----------|-----------|
| 设计 | 每个子系统（cpu/memory/blkio）独立挂载 | 统一层级，所有控制器在一棵树 |
| 层次结构 | 每个子系统一棵树 | 单棵树，所有控制器共用 |
| 进程归属 | 一个进程可在不同子系统属于不同组 | 一个进程只能在一个组 |
| 根目录 | /sys/fs/cgroup/cpu, /sys/fs/cgroup/memory... | /sys/fs/cgroup |
| 默认系统 | CentOS 7, Ubuntu 16.04 | CentOS 8+, Ubuntu 22.04+ |

现代 Linux 发行版已全面转向 Cgroup v2。

### 2.2 Cgroup v2 的核心控制器

| 控制器 | 文件 | 功能 |
|--------|------|------|
| cpu | `cpu.max` | 限制 CPU 使用率（如 "100000 100000" = 1核） |
| cpuset | `cpuset.cpus` | 限制进程可运行的 CPU 核心 |
| memory | `memory.max` | 限制内存使用上限 |
| memory | `memory.high` | 内存软限制，超过时尽量回收 |
| io | `io.max` | 限制磁盘 IO 带宽 |
| pids | `pids.max` | 限制进程/线程数 |
| rdma | `rdma.max` | 限制 RDMA 资源 |
| perf_event | `perf_event` | 允许 perf 监控 |

### 2.3 手动使用 Cgroup v2

```bash
# 查看 Cgroup v2 挂载
mount | grep cgroup2
# 输出：cgroup2 on /sys/fs/cgroup type cgroup2 (rw,nosuid,nodev,noexec,relatime)

# 创建一个新的控制组
sudo mkdir /sys/fs/cgroup/mygroup

# 限制 CPU 使用率为 50%（每 100ms 可用 50ms）
echo "50000 100000" | sudo tee /sys/fs/cgroup/mygroup/cpu.max

# 限制内存为 100MB
echo 104857600 | sudo tee /sys/fs/cgroup/mygroup/memory.max

# 限制进程数
echo 10 | sudo tee /sys/fs/cgroup/mygroup/pids.max

# 将当前 shell 加入该组
echo $$ | sudo tee /sys/fs/cgroup/mygroup/cgroup.procs

# 运行压力测试，观察限制效果
stress-ng --cpu 4 --timeout 10s
```

### 2.4 Cgroup 与 Docker

Docker 的 `--cpus` / `--memory` 参数底层就是 Cgroup：

```bash
# 限制容器最多使用 1.5 核 CPU 和 512MB 内存
docker run --cpus=1.5 --memory=512m --memory-swap=512m ubuntu

# 底层映射到：
# /sys/fs/cgroup/docker/<container_id>/cpu.max = "150000 100000"
# /sys/fs/cgroup/docker/<container_id>/memory.max = 536870912
```

## 3. Namespace + Cgroup = 容器

一个最小容器 = 一组 Namespace + 一个 Cgroup + rootfs（文件系统）。

```bash
# 手动模拟 Docker 创建容器的过程

# 1. 创建 rootfs（用 busybox）
mkdir -p /tmp/mycontainer/rootfs
cd /tmp/mycontainer/rootfs
wget https://busybox.net/downloads/binaries/1.35.0-x86_64-linux-musl/busybox
chmod +x busybox
mkdir -p bin sbin lib proc sys tmp
ln -s busybox bin/sh
ln -s busybox bin/ls
ln -s busybox bin/ps

# 2. 创建 Cgroup
sudo mkdir /sys/fs/cgroup/mycontainer
# 限制资源...

# 3. 创建 Namespace 并启动 init
sudo unshare --pid --net --ipc --uts --mount --fork \
             --root=/tmp/mycontainer/rootfs \
             /bin/sh -c "mount -t proc proc /proc; mount -t sysfs sysfs /sys; exec /bin/sh"

# 现在你在一个隔离的环境中，PID 1 是 /bin/sh
```

## 4. 在 Kubernetes 中的应用

Kubernetes 的 Pod 在底层就是一组共享某些 Namespace（特别是 Network、IPC、UTS）的容器：

```
Pod = Network Namespace + IPC Namespace + UTS Namespace
    + 多个容器（各自独立的 PID Namespace、Mount Namespace）
    + Cgroup（资源限制）
```

K8s 的 `limits` 和 `requests` 映射到 Cgroup：

```yaml
resources:
  limits:
    cpu: "2"
    memory: "2Gi"
  requests:
    cpu: "500m"
    memory: "512Mi"
```

- `limits` → Cgroup `cpu.max` / `memory.max`（硬限制）
- `requests` → kube-scheduler 调度决策（不直接映射到 Cgroup）

## 5. 小结

| 机制 | 作用 | 类比 |
|------|------|------|
| Namespace | 隔离（Isolation） | 让进程"看不到"其他资源 |
| Cgroup | 限制（Limitation） | 让进程"只能用"这么多资源 |
| UnionFS | 文件层叠（Layering） | 让容器镜像可叠加 |

- Namespace 解决"看见什么"的问题，Cgroup 解决"能用多少"的问题。
- Docker/Kubernetes 在底层就是 Namespace + Cgroup + rootfs 的组合。
- 理解 Namespace 和 Cgroup，是理解容器安全、资源调度、多租户隔离的基础。
