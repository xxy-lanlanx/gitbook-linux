# 08-Linux 系统调用原理与实现

> 系统调用是用户态程序进入内核态的唯一正规通道。理解它的实现机制，是理解"用户程序如何请求内核服务"的关键。

## 1. 什么是系统调用

**系统调用（System Call）** 是操作系统内核提供给用户态程序的一组标准接口。用户程序通过系统调用请求内核执行特权操作，如读写文件、创建进程、分配内存、网络通信等。

从本质上看，系统调用完成了两件事：

1. **身份切换**：从用户态（ring 3）切换到内核态（ring 0），获得更高的特权级。
2. **服务分发**：根据系统调用号，在内核中找到对应的处理函数并执行。

常见的系统调用包括：

| 类别 | 系统调用 | 功能 |
|------|---------|------|
| 进程控制 | `fork`, `clone`, `execve`, `exit` | 创建/替换/终止进程 |
| 文件操作 | `open`, `read`, `write`, `close` | 打开/读写/关闭文件 |
| 内存管理 | `mmap`, `munmap`, `brk` | 映射/解除映射/调整堆 |
| 进程通信 | `pipe`, `socket`, `shmget` | 创建管道/套接字/共享内存 |
| 设备控制 | `ioctl` | 设备特定控制 |

## 2. 系统调用的入口方式

### 2.1 传统方式：`int 0x80`（x86 32位）

x86 架构下，Linux 早期使用软中断 `int 0x80` 作为系统调用入口：

1. 用户程序把系统调用号放入 `eax` 寄存器。
2. 参数依次放入 `ebx`, `ecx`, `edx`, `esi`, `edi`, `ebp`。
3. 执行 `int 0x80`，触发中断，CPU 切换到内核态。
4. 内核从中断向量表找到处理函数 `system_call()`。
5. 根据 `eax` 中的系统调用号，在 `sys_call_table` 中查找对应的内核函数。

```asm
; 用户态代码示例：调用 sys_write (调用号 4)
mov eax, 4          ; 系统调用号 = __NR_write
mov ebx, 1          ; fd = 1 (stdout)
mov ecx, msg        ; buf
mov edx, len        ; count
int 0x80            ; 陷入内核
```

### 2.2 现代方式：`syscall` / `sysenter` 指令

`int 0x80` 需要查询中断描述符表（IDT），开销较大。现代 x86 处理器提供了更快速的专用指令：

- **x86_64**：`syscall` / `sysret` 指令对
- **x86 (32位)**：`sysenter` / `sysexit` 指令对

`syscall` 指令的优势：

- 不需要查询中断描述符表，直接跳转到预设的入口地址。
- 保存的状态更少，切换速度更快。
- 在现代 Linux 系统上，`getpid()` 等简单系统调用只需约 100-200 纳秒。

### 2.3 ARM 架构的系统调用

ARM 处理器使用 `swi`（Software Interrupt）或 `svc`（Supervisor Call）指令：

```asm
; ARM 示例：调用 sys_write
mov r7, #4          ; 系统调用号
mov r0, #1          ; fd = stdout
ldr r1, =msg        ; buf
mov r2, #len        ; count
swi 0               ; 陷入内核
```

ARM64 则使用 `svc #0` 指令，系统调用号通过 `x8` 寄存器传递。

## 3. 系统调用的内核实现流程

以 x86_64 的 `syscall` 指令为例，完整流程如下：

```
用户态程序
    │
    ▼
调用 glibc 封装函数 (如 write())
    │
    ▼
glibc 把系统调用号放入 rax，参数放入 rdi, rsi, rdx, r10, r8, r9
    │
    ▼
执行 syscall 指令
    │
    ▼
CPU 切换到内核态
    │  • 保存用户态 rsp 到 MSR_LSTAR
    │  • 加载内核栈指针
    │  • rip 跳转到 entry_SYSCALL_64
    │
    ▼
entry_SYSCALL_64 (arch/x86/entry/entry_64.S)
    │
    ▼
save_regs: 保存用户态寄存器到栈帧
    │
    ▼
swapgs: 切换 GS 段，指向 per-cpu 变量区
    │
    ▼
call do_syscall_64 (rax = 系统调用号)
    │
    ▼
sys_call_table[rax] → 调用具体的内核函数 (如 sys_write)
    │
    ▼
内核函数执行完毕，返回值放入 rax
    │
    ▼
恢复寄存器，执行 sysretq 返回用户态
    │
    ▼
用户态继续执行，rax 中保存返回值
```

## 4. 系统调用表

Linux 内核中有一张**系统调用表**（System Call Table），是一个函数指针数组，下标是系统调用号，元素是对应的内核函数。

在 x86_64 上，定义在 `arch/x86/entry/syscalls/syscall_64.tbl`：

```
0       read                    sys_read
1       write                   sys_write
2       open                    sys_open
3       close                   sys_close
...     ...                     ...
59      execve                  sys_execve
```

在运行时，内核加载这张表，生成 `sys_call_table` 数组。`do_syscall_64()` 根据 `rax` 中的号查表跳转：

```c
/* arch/x86/entry/common.c */
long do_syscall_64(struct pt_regs *regs)
{
    unsigned long nr = regs->orig_ax;
    
    if (nr < NR_syscalls) {
        regs->ax = sys_call_table[nr](regs->di, regs->si, regs->dx,
                                       regs->r10, regs->r8, regs->r9);
    }
    return regs->ax;
}
```

## 5. 参数传递与系统调用约定

### x86_64 系统调用参数传递

| 参数 | 寄存器 |
|------|--------|
| 系统调用号 | `rax` |
| 第 1 参数 | `rdi` |
| 第 2 参数 | `rsi` |
| 第 3 参数 | `rdx` |
| 第 4 参数 | `r10` |
| 第 5 参数 | `r8` |
| 第 6 参数 | `r9` |

返回值通过 `rax` 传递。错误时返回负的 errno（如 -ENOENT），glibc 会将其转换为 -1 并设置 errno。

### 为什么最多 6 个参数？

x86_64 的 `syscall` 指令只保证保存 `rcx` 和 `r11`，其他寄存器由调用者保存。6 个参数刚好用完常用寄存器，如果参数更多，需要传递指针指向结构体。

## 6. 系统调用 vs 普通函数调用

| 特性 | 普通函数调用 | 系统调用 |
|------|-------------|---------|
| 调用方式 | `call` 指令 | `syscall` / `int 0x80` |
| 特权级变化 | 不变 | 用户态 → 内核态 |
| 参数传递 | 寄存器 + 栈 | 寄存器（最多 6 个） |
| 上下文切换 | 无 | 有（保存/恢复寄存器、栈） |
| 开销 | 几纳秒 | 100-500 纳秒 |
| 安全性 | 同地址空间 | 跨地址空间，内核会校验参数 |

## 7. 添加一个新的系统调用

如果你想给 Linux 内核添加一个新的系统调用，需要做以下几步：

1. **在系统调用表中注册**：
   在 `arch/x86/entry/syscalls/syscall_64.tbl` 中分配一个未使用的号码，关联一个函数名。

2. **声明函数原型**：
   在 `include/linux/syscalls.h` 中声明：`asmlinkage long sys_mycall(...);`

3. **实现内核函数**：
   在合适的子系统目录中实现 `sys_mycall()`。

4. **重新编译内核**：
   编译并安装新内核，用户程序才能使用这个新的系统调用号。

> 实际工程中，添加系统调用非常谨慎，因为一旦号码分配后就不能随意更改，否则会破坏 ABI 兼容性。现代 Linux 更倾向于使用 `ioctl`、`netlink`、`bpf` 等扩展机制，而不是新增系统调用。

## 8. vDSO：加速常见系统调用

对于一些不需要内核特权态也能完成的查询（如 `gettimeofday`, `getcpu`），Linux 引入了 **vDSO（virtual Dynamic Shared Object）**。

vDSO 是内核映射到用户态地址空间的一个小型共享库，用户程序可以直接在用户态调用这些函数，无需陷入内核：

```
gettimeofday()  →  直接读 vDSO 中的数据  →  无需 syscall，纳秒级返回
```

这大大加速了高频但轻量的系统调用。你可以用 `ldd /bin/ls` 看到 `linux-vdso.so.1` 的映射。

## 9. 小结

| 问题 | 答案 |
|------|------|
| 用户程序如何进入内核？ | 通过系统调用，触发 `syscall`/`int 0x80`/`svc` |
| 系统调用号是什么？ | 内核函数指针数组 `sys_call_table` 的下标 |
| 最多几个参数？ | 6 个（通过寄存器） |
| 返回值在哪？ | `rax`/`r0` 寄存器 |
| 为什么 `gettimeofday` 这么快？ | 通过 vDSO 在用户态完成，无需陷入内核 |
| 添加系统调用需要什么？ | 改 syscall table、声明原型、实现函数、重新编译内核 |

系统调用是理解"用户态 ↔ 内核态"边界的第一道门，也是后续理解进程管理、内存管理、文件系统、网络 IO 的入口基础。
