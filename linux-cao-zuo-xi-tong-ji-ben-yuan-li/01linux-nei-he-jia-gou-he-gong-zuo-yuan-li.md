# 01-Linux 内核架构和工作原理（导论）

> 本篇是"Linux 操作系统基本原理"部分的开篇，先建立整体认知：什么是操作系统与内核、Linux 内核属于哪一类、它的层次如何。后续 02 起进入内核整体架构与各子系统的细节。

## 1. 什么是操作系统 / 内核

- **操作系统（OS）**：管理硬件资源、为应用程序提供运行环境的系统软件。它向下驱动 CPU、内存、磁盘、网卡等设备，向上通过**系统调用**给程序提供统一接口。
- **内核（kernel）**：操作系统的核心部分，运行在特权级（内核态），拥有对硬件的完整控制权。我们常说的"Linux"其实是指"Linux 内核 + GNU 等用户态工具"组成的完整系统。

## 2. Linux 内核的设计形态：宏内核

| 类型 | 特点 | 代表 |
|------|------|------|
| 宏内核（monolithic） | 所有子系统（进程/内存/文件/网络/驱动）都在内核态，调用开销小、性能好 | Linux、Unix |
| 微内核（microkernel） | 仅保留最基础功能在内核态，其余以服务进程形式运行在用户态，模块化但IPC开销大 | Minix、QNX、鸿蒙（部分） |

Linux 是宏内核，但通过**可加载内核模块（LKM）**获得了类似微内核的扩展性——驱动、文件系统等可以动态插入/卸载，而不必重新编译整个内核。

## 3. 内核的层次（自顶向下）

1. **系统调用接口**：用户态进入内核的唯一正规入口（`open`/`read`/`fork`/`mmap`…）。
2. **内核子系统**：进程调度、内存管理、虚拟文件系统 VFS、网络子系统、进程间通信 IPC。
3. **架构相关层（arch/）**：与 CPU 体系结构绑定的部分（如 ARM 的上下文切换、页表格式）。
4. **硬件抽象 / 驱动**：直接操作寄存器、MMIO、中断控制器。

> 这条"用户态 → 系统调用 → 子系统 → 硬件"的链路，会贯穿全书。每往下一层，你就更接近 C/汇编/计算机系统基础。

## 4. 本书的分析基准

- 内核版本：**Linux 3.10.29**（LTS，长期维护，资料多）。
- 体系结构：以 **ARM** 为主（嵌入式最常见），涉及 x86 处会注明。
- 目标读者：想建立操作系统整体认知的学习者，以及需要查阅底层实现的嵌入式工程师。

## 5. 本部分目录

- [02-Linux Kernel 内核整体架构](../linux-cao-zuo-xi-tong-ji-ben-yuan-li/02linux-kernel-nei-he-zheng-ti-jia-gou.md)
- [03-Linux 操作系统学习——启动](../linux-cao-zuo-xi-tong-ji-ben-yuan-li/03linux-cao-zuo-xi-tong-xue-xi-qi-dong.md)
- [04-Linux 操作系统学习——内核初始化](../linux-cao-zuo-xi-tong-ji-ben-yuan-li/04linux-cao-zuo-xi-tong-xue-xi-nei-he-chu-shi-hua.md)
- [05-Linux 操作系统 IO 机制原理](../linux-cao-zuo-xi-tong-ji-ben-yuan-li/05linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li.md)
- [06-Linux 处理器调度基本准则和实现](../linux-cao-zuo-xi-tong-ji-ben-yuan-li/06linux-cao-zuo-xi-tong-chu-li-qi-diao-du-ji-ben-zhun-ze-he-shi-xian.md)
- [07-Linux 内核操作系统原理与概述](../linux-cao-zuo-xi-tong-ji-ben-yuan-li/07linux-nei-he-cao-zuo-xi-tong-yuan-li-yu-gai-shu.md)
- [08-Linux ARM 体系结构处理器机制原理与实现](../linux-cao-zuo-xi-tong-ji-ben-yuan-li/08linux-cao-zuo-xi-tong-arm-ti-xi-jie-gou-chu-li-qi-ji-zhi-yuan-li-yu-shi-xian.md)
- [09-Linux 汇编语言基础知识](../linux-cao-zuo-xi-tong-ji-ben-yuan-li/09linux-cao-zuo-xi-tong-hui-bian-yu-yan-ji-chu-zhi-shi.md)
- [10-Linux 汇编指令入门级整理知识点](../linux-cao-zuo-xi-tong-ji-ben-yuan-li/10linux-cao-zuo-xi-tong-hui-bian-zhi-ling-ru-men-ji-zheng-li-zhi-shi-dian.md)
- [11-Linux 理解 CPU 上下文切换](../linux-cao-zuo-xi-tong-ji-ben-yuan-li/11linux-cao-zuo-xi-tong-li-jie-cpu-shang-xia-wen-qie-huan.md)

---

> 下一篇：[02-Linux Kernel 内核整体架构](../linux-cao-zuo-xi-tong-ji-ben-yuan-li/02linux-kernel-nei-he-zheng-ti-jia-gou.md)
