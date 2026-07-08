# 17-Linux 安全机制

## 一、Linux 安全模型层次

Linux 安全不是单一机制，而是**多层纵深防御**：

```
┌──────────────────────────────┐
│ 应用层：安全编码、最小权限原则    │
├──────────────────────────────┤
│ 容器/沙箱：Namespace、Seccomp    │
├──────────────────────────────┤
│ 强制访问控制：SELinux / AppArmor │
├──────────────────────────────┤
│ 自主访问控制：DAC（UGO/ACL）      │
├──────────────────────────────┤
│ 特权控制：Capabilities           │
├──────────────────────────────┤
│ 审计：Audit、BPF LSM              │
├──────────────────────────────┤
│ 系统调用过滤：Seccomp             │
├──────────────────────────────┤
│ 内核完整性：IMA/EVM、Lockdown     │
└──────────────────────────────┘
```

## 二、Capabilities：细粒度特权

传统 Unix 的 root/non-root 二元模型过于粗糙。Linux 2.2 引入 **Capabilities**，将 root 特权拆分为 40+ 个独立权限：

| Capability | 权限 | 风险 |
|------------|------|------|
| `CAP_CHOWN` | 任意修改文件所有者 | 中 |
| `CAP_DAC_OVERRIDE` | 绕过文件读/写/执行权限检查 | 高 |
| `CAP_NET_ADMIN` | 网络配置（路由、iptables、网卡） | 高 |
| `CAP_NET_BIND_SERVICE` | 绑定 1024 以下端口 | 低 |
| `CAP_SYS_ADMIN` | 系统管理万能钥匙（mount、swapon 等） | **极高** |
| `CAP_SYS_PTRACE` | 调试任意进程 | 高 |
| `CAP_SYS_MODULE` | 加载/卸载内核模块 | **极高** |
| `CAP_SYS_RAWIO` | 直接访问硬件 I/O 端口 | **极高** |

### 1. 进程 Capabilities 集合

```c
// include/uapi/linux/capability.h
typedef struct __user_cap_header_struct {
    __u32 version;
    int pid;
} *cap_user_header_t;

typedef struct __user_cap_data_struct {
    __u32 effective;    // 当前生效的 capabilities
    __u32 permitted;    // 允许获得的 capabilities（上限）
    __u32 inheritable;  // 可继承给子进程的 capabilities
} *cap_user_data_t;
```

| 集合 | 含义 |
|------|------|
| `Bounding set` | 允许获得的最大能力集，可缩小不可逆 |
| `Ambient set` | 非特权程序可继承的环境能力 |
| `Effective` | 当前实际生效的能力 |
| `Permitted` | 可添加到 Effective 的最大范围 |

```bash
# 查看进程 capabilities
cat /proc/self/status | grep Cap
CapInh: 0000000000000000
CapPrm: 0000003fffffffff
CapEff: 0000003fffffffff
CapBnd: 0000003fffffffff
CapAmb: 0000000000000000

# 解码 capabilities（使用 capsh）
capsh --decode=0000003fffffffff
```

### 2. 文件 capabilities

可以给可执行文件设置 capabilities，使其无需 SUID 即可获得特定权限：

```bash
# 给 ping 设置 CAP_NET_RAW，不再需要 root 或 SUID
setcap cap_net_raw+ep /usr/bin/ping

# 查看文件 capabilities
getcap /usr/bin/ping
# /usr/bin/ping = cap_net_raw+ep
```

| 标志 | 含义 |
|------|------|
| `e` (effective) | 执行时自动加入 Effective 集合 |
| `p` (permitted) | 允许获得此 capability |
| `i` (inheritable) | 可继承给子进程 |

## 三、Seccomp：系统调用过滤

Seccomp（Secure Computing Mode）限制进程能使用的系统调用。最初是“只允许 read/write/exit/sigreturn”的白名单，后来发展为 **Seccomp-BPF**，允许使用 eBPF 程序动态过滤。

### 1. Seccomp 模式

| 模式 | 说明 | 使用 |
|------|------|------|
| strict | 只允许 read/write/exit/sigreturn | 极少使用 |
| filter | 自定义 BPF 规则 | Docker 默认、Chrome 沙箱 |

### 2. Docker 的默认 Seccomp 配置

Docker 默认启用 Seccomp，屏蔽了约 44 个危险系统调用：

```bash
# 查看 Docker 默认 seccomp 配置
cat /etc/docker/seccomp/default.json | jq '.syscalls[] | select(.action=="SCMP_ACT_ERRNO") | .names'
# 包含：reboot, mount, umount2, kexec_load, open_by_handle_at, ...
```

```json
// 默认屏蔽部分系统调用
{
  "syscalls": [
    {
      "names": ["reboot", "kexec_load", "kexec_file_load"],
      "action": "SCMP_ACT_ERRNO"
    },
    {
      "names": ["mount", "umount2", "pivot_root"],
      "action": "SCMP_ACT_ERRNO"
    }
  ]
}
```

### 3. 自定义 Seccomp 策略

```c
// 编写 seccomp 规则（libseccomp 库）
scmp_filter_ctx ctx = seccomp_init(SCMP_ACT_ALLOW);
seccomp_rule_add(ctx, SCMP_ACT_ERRNO(EPERM), SCMP_SYS(reboot), 0);
seccomp_rule_add(ctx, SCMP_ACT_ERRNO(EPERM), SCMP_SYS(mount), 0);
seccomp_load(ctx);
// 此后进程调用 reboot() 或 mount() 将返回 EPERM
```

## 四、SELinux：强制访问控制（MAC）

### 1. DAC vs MAC

| 模型 | 控制方式 | 问题 |
|------|----------|------|
| DAC | 文件所有者决定权限 | root 可绕过任何权限 |
| MAC | 系统策略决定权限 | 即使 root 也受策略约束 |

SELinux 基于 **TE（Type Enforcement）**模型，每个主体（进程）和客体（文件、端口）都有**安全上下文（Security Context）**：

```bash
# 查看进程安全上下文
ps -eZ | grep nginx
system_u:system_r:httpd_t:s0   nginx

# 查看文件安全上下文
ls -Z /var/www/html/index.html
system_u:object_r:httpd_sys_content_t:s0 /var/www/html/index.html

# 格式：user:role:type:level
#       system_u:system_r:httpd_t:s0
```

### 2. SELinux 策略规则

```
允许规则（Allow Rule）：
  allow httpd_t httpd_sys_content_t:file { read getattr };
  
含义：类型为 httpd_t 的进程可以 read/getattr 类型为 httpd_sys_content_t 的文件
```

常见 SELinux 类型：

| 类型 | 说明 |
|------|------|
| `unconfined_t` | 无限制，相当于关闭 SELinux |
| `httpd_t` | Web 服务器进程 |
| `httpd_sys_content_t` | Web 内容文件 |
| `sshd_t` | SSH 守护进程 |
| `user_t` | 普通用户进程 |
| `init_t` | systemd/init |

### 3. SELinux 模式

```bash
# 查看当前模式
getenforce
# Enforcing / Permissive / Disabled

# 切换模式（临时）
setenforce 0  # Permissive：只记录不拦截
setenforce 1  # Enforcing：启用策略

# 查看审计日志（为什么被阻止）
ausearch -m avc -ts recent
# type=AVC msg=audit(...): avc:  denied  { read } for  pid=1234 comm="nginx" 
#   name="index.html" dev="sda1" ino=56789 scontext=system_u:system_r:httpd_t:s0 
#   tcontext=unconfined_u:object_r:user_home_t:s0 tclass=file
```

## 五、AppArmor：路径-based MAC

AppArmor 与 SELinux 同为 MAC，但策略基于**文件路径**而非类型标签，更易理解和配置：

```bash
# AppArmor 配置文件示例（/etc/apparmor.d/usr.sbin.nginx）
#include <tunables/global>

/usr/sbin/nginx {
  #include <abstractions/base>
  
  capability net_bind_service,
  capability setuid,
  capability setgid,
  
  /usr/sbin/nginx r,
  /etc/nginx/** r,
  /var/log/nginx/** rw,
  /var/www/html/** r,
  
  deny /etc/shadow r,  # 显式拒绝
}
```

| 对比 | SELinux | AppArmor |
|------|---------|----------|
| 策略基础 | 类型标签 | 文件路径 |
| 复杂度 | 高 | 低 |
| 默认发行版 | RHEL/CentOS/Fedora | Ubuntu/SUSE/Debian |
| 灵活性 | 极高（可定义任意关系） | 中等 |

## 六、内核完整性：IMA/EVM 与 Lockdown

### 1. IMA（Integrity Measurement Architecture）

IMA 在文件访问时测量（哈希）文件内容，与预期值对比：

```bash
# 查看 IMA 度量日志
cat /sys/kernel/security/ima/ascii_runtime_measurements
# 10 6c2f... ima-ng sha256:abcd... /usr/bin/ls
# 10 3a8f... ima-ng sha256:ef01... /usr/bin/cat
```

### 2. Lockdown 模式（内核 5.4+）

```bash
# 查看当前 lockdown 模式
cat /sys/kernel/security/lockdown
# [none] integrity confidentiality

echo integrity > /sys/kernel/security/lockdown
```

| 模式 | 限制 |
|------|------|
| `none` | 无限制 |
| `integrity` | 禁止写入 /dev/mem、/dev/kmem，禁止加载未签名的内核模块 |
| `confidentiality` | 禁止提取内核内存（如 debugfs kcore），禁止 eBPF 访问内核指针 |

## 七、总结

| 机制 | 防御层 | 关键点 |
|------|--------|--------|
| DAC | 基础 | `chmod`/`chown`，但 root 可绕过 |
| Capabilities | 特权拆分 | 40+ 细粒度权限，`CAP_SYS_ADMIN` 最危险 |
| Seccomp | 系统调用过滤 | 白名单/黑名单，Docker 默认启用 |
| SELinux | 强制访问控制 | 基于类型的 TE 策略，RHEL 默认 |
| AppArmor | 强制访问控制 | 基于路径，Ubuntu 默认 |
| IMA/EVM | 文件完整性 | 运行时度量，TPM 远程证明 |
| Lockdown | 内核自我保护 | 限制 root 对内核的访问 |

Linux 安全机制的核心原则是 **最小权限** 和 **纵深防御**。没有单一机制能防御所有攻击，但多层组合可以显著降低被攻破的风险。对于生产系统，建议至少启用：**Seccomp + Capabilities 裁剪 + AppArmor/SELinux + Lockdown（如适用）**。
