# 11-Linux 容器与虚拟化技术

## 一、容器不是虚拟机

容器和虚拟化常被混淆，但本质不同：

| 维度 | 容器（Container） | 虚拟机（VM） |
|------|------------------|-------------|
| 隔离级别 | 进程级 | 硬件级 |
| 共享内核 | 是（与宿主机共享） | 否（独立内核） |
| 启动速度 | 毫秒级 | 秒级 |
| 资源开销 | 极低（接近原生） | 高（Guest OS 开销） |
| 典型实现 | Docker、containerd、Podman | KVM、Xen、VMware |

容器通过 Linux 内核的 **Namespace** 实现隔离，**Cgroup** 实现资源限制，配合 **UnionFS** 实现镜像分层。

## 二、Namespace 深入

Namespace 将全局资源划分为多个独立视图，每个容器只能看到自己的资源：

| Namespace | 隔离资源 | 系统调用 | 内核版本 |
|-----------|----------|----------|----------|
| PID | 进程 ID | `clone(CLONE_NEWPID)` | 2.6.24 |
| Network | 网络设备、端口、路由 | `clone(CLONE_NEWNET)` | 2.6.24 |
| UTS | 主机名/域名 | `clone(CLONE_NEWUTS)` | 2.6.19 |
| IPC | 信号量、消息队列、共享内存 | `clone(CLONE_NEWIPC)` | 2.6.19 |
| Mount | 挂载点 | `clone(CLONE_NEWNS)` | 2.4.19 |
| User | 用户/组 ID | `clone(CLONE_NEWUSER)` | 3.8 |
| Cgroup | Cgroup 根目录 | `clone(CLONE_NEWCGROUP)` | 4.6 |
| Time | 系统时间 | `clone(CLONE_NEWTIME)` | 5.6 |

### 1. PID Namespace 的父子关系

```
宿主机 PID Namespace
├─ PID 1: systemd
│  ├─ PID 1234: dockerd
│  │  └─ PID 5678: containerd-shim
│  │     └─ 新 PID Namespace（容器视角）
│  │        ├─ PID 1: nginx（容器内看自己是 PID 1）
│  │        └─ PID 10: php-fpm
```

在容器中，`ps` 只能看到 Namespace 内的进程；`kill -9 1` 只能杀掉容器 init 进程，不会影响宿主机。

### 2. User Namespace：root 不是 root

User Namespace 允许容器内的 `root` 映射到宿主机上的一个普通用户（如 UID 100000）：

```bash
# 宿主机查看容器进程的真实 UID
cat /proc/$(pidof nginx)/uid_map
# 0 100000 65536  # 容器 UID 0-65535 映射到宿主机 UID 100000-165535
```

即使容器内进程以 root 运行，在宿主机看来它只有 UID 100000 的权限。这大大提升了安全性。

### 3. Network Namespace 与 veth

```
宿主机 Network Namespace
│  eth0 (10.0.0.1)
│  docker0 (172.17.0.1)
│     │
│     ├─ veth0a  ┄┄┄┄  veth0b ─┐
│     │                          │
│  Container Namespace          │
│     │                          │
│     └─ eth0 (172.17.0.2)  ←──┘
```

`veth pair` 是成对的虚拟网卡，一端在宿主机，一端在容器。数据从一端进入，另一端必然出来。配合 Linux Bridge 或 iptables，实现容器网络通信。

## 三、Cgroup v2 深入

Cgroup v1 按资源类型分不同子系统（`cpu`、`memory`、`blkio`），存在设计缺陷。Cgroup v2 统一了层级结构，支持 delegation 和更严格的资源控制。

### 1. Cgroup v2 统一层级

```
/sys/fs/cgroup/
├─ cgroup.procs          # 当前 cgroup 的进程
├─ cgroup.controllers    # 可用控制器（cpu memory io）
├─ cgroup.subtree_control # 已启用的控制器
├─ system.slice/         # systemd 服务
│  ├─ nginx.service/
│  │  ├─ cpu.max        # CPU 时间限制
│  │  ├─ memory.max     # 内存硬限制
│  │  └─ io.max         # I/O 带宽限制
│  └─ mysql.service/
└─ user.slice/
```

### 2. 关键控制器配置

```bash
# CPU 限制：每 100000μs 最多使用 50000μs（即 0.5 CPU）
echo "50000 100000" > /sys/fs/cgroup/myapp/cpu.max

# 内存限制：硬限制 1GB
echo 1073741824 > /sys/fs/cgroup/myapp/memory.max

# 内存软限制：超过时优先回收
echo 536870912 > /sys/fs/cgroup/myapp/memory.high

# I/O 限制：限制 /dev/sda 读 10MB/s，写 20MB/s
echo "8:0 rbps=10485760 wbps=20971520" > /sys/fs/cgroup/myapp/io.max
```

### 3. Cgroup 与 OOM

当 `memory.max` 被触发时，cgroup 内部会执行 OOM kill（只杀 cgroup 内进程，不影响系统）：

```c
// mm/oom_kill.c
bool out_of_memory(struct oom_control *oc, gfp_t gfp)
{
    // 如果处于 memcg 限制，先尝试 memcg OOM
    if (mem_cgroup_oom(oc->memcg, gfp, ORDER(0))) {
        mem_cgroup_select_victim(oc->memcg);  // 只选本 cgroup 的进程
        oom_kill_process(oc->chosen, ...);
        return true;
    }
}
```

## 四、容器镜像与 UnionFS

### 1. OverlayFS 分层结构

```
Docker 镜像层
├─ Layer 3: app code (读写层，容器启动后)
├─ Layer 2: pip install
├─ Layer 1: apt install python
└─ Layer 0: ubuntu base (只读)

OverlayFS 挂载：
  lowerdir = Layer 0:Layer 1:Layer 2
  upperdir = Layer 3
  merged   = 容器视角的统一视图
  workdir  = 内核工作目录
```

容器内修改文件时，OverlayFS 执行 **copy-up**：将只读层的文件复制到 upperdir（读写层），然后修改副本。原只读层不受影响，因此多个容器可以共享同一基础镜像层。

### 2. 文件系统性能陷阱

| 场景 | 问题 | 解决 |
|------|------|------|
| 大量小文件写入 | copy-up 频繁，性能差 | 使用 volume 挂载到宿主机 ext4/xfs |
| 数据库日志 | 双层写放大 | 使用 `--tmpfs` 或独立 volume |
| 编译构建 | OverlayFS 元数据操作慢 | 使用 BuildKit 缓存或宿主机目录 |

## 五、虚拟化：KVM

### 1. KVM 基本原理

KVM（Kernel-based Virtual Machine）将 Linux 内核变为 Type-1 Hypervisor：

```
用户态
  ├─ QEMU（设备模拟、VM 管理）
  │  └─ 调用 /dev/kvm ioctl
  └─ libvirt（管理工具）

内核态
  └─ KVM 模块
     ├─ CPU 虚拟化：VMX（Intel）/ SVM（AMD）
     │  └─ Guest 代码直接运行在 CPU 非根模式
     ├─ 内存虚拟化：EPT（Intel）/ NPT（AMD）
     │  └─ Guest 物理地址 → 宿主机物理地址的二级页表
     └─ I/O 虚拟化：virtio（半虚拟化）或设备直通（PCIe VFIO）
```

### 2. CPU 虚拟化：VMX 根/非根模式

| 模式 | 特权 | 运行代码 |
|------|------|----------|
| VMX Root Operation | Ring 0 | Host 内核（KVM） |
| VMX Non-Root Operation | Ring 0-3 | Guest 内核/用户态 |

敏感指令（如 `cr3` 修改、I/O 指令）触发 **VM Exit**，CPU 切换回 Root 模式，由 KVM 处理。普通指令直接在硬件执行，无开销。

### 3. 内存虚拟化：EPT

```
Guest 虚拟地址 (GVA)
       │
       ▼
Guest 页表 (GVA → GPA)
       │
       ▼
Guest 物理地址 (GPA)
       │
       ▼
EPT 页表 (GPA → HPA)  ← 由 KVM 维护
       │
       ▼
Host 物理地址 (HPA)
```

EPT 减少了 shadow page table 的开销。但 TLB miss 时需要**遍历两层页表**（Guest 页表 + EPT），成本更高。Intel 的 **VPID**（Virtual Processor ID）和 **EPT** 的 tagged TLB 可缓解此问题。

### 4. I/O 虚拟化方案对比

| 方案 | 性能 | 安全性 | 适用场景 |
|------|------|--------|----------|
| 设备模拟（QEMU） | 极低 | 高 | 兼容性测试 |
| Virtio（半虚拟化） | 高 | 中 | 通用生产环境 |
| VFIO 直通 | 接近原生 | 依赖 IOMMU | 高性能网卡、GPU |
| SR-IOV | 接近原生 | 依赖 IOMMU | 云计算多租户 |

## 六、容器安全最佳实践

| 实践 | 说明 |
|------|------|
| 非 root 运行 | `USER 1000` in Dockerfile |
| 只读根文件系统 | `--read-only` |
| 禁用特权 | 绝不使用 `--privileged` |
| 最小权限 | 只挂载需要的 volume，限制 capabilities |
| Seccomp | 限制可用系统调用（Docker 默认启用） |
| AppArmor/SELinux | 强制访问控制 |
| User Namespace | 映射 root 到非特权 UID |

```bash
# 最小权限容器示例
docker run \
  --read-only \
  --user 1000:1000 \
  --cap-drop=ALL \
  --cap-add=NET_BIND_SERVICE \
  --security-opt seccomp=default.json \
  -v /tmp/data:/data:rw \
  myapp
```

## 七、总结

| 技术 | 要点 |
|------|------|
| Namespace | 隔离进程视图，8 种类型 |
| Cgroup v2 | 统一资源控制，CPU/内存/IO 硬限制 |
| OverlayFS | 分层镜像，copy-on-write |
| KVM | 硬件辅助虚拟化，VMX/EPT/Virtio |
| 安全 | 纵深防御：User Namespace + Seccomp + Capabilities + MAC |

容器技术是现代云原生的基石。理解 Namespace 和 Cgroup 的底层机制，是排查容器性能问题、设计安全沙箱的必备知识。
