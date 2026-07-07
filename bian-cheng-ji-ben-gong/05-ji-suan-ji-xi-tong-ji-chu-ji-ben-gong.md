# 05-计算机系统基础基本功

> 内核直接跟硬件打交道：寄存器、MMU、中断、DMA……这些都属于"计算机系统基础"。本章补齐理解内核所必需的数制、字节序、对齐、内存布局与中断常识，并配可运行验证。

## 5.1 数制与位级视角

CPU 只认 0/1。熟练在 2/10/16 进制间转换，并能用掩码"取出/修改某几位"，是读内核寄存器的前提。

```c
// 示例 1：用掩码取一个字节的高 4 位和低 4 位
#include <stdio.h>
int main(void) {
    unsigned char reg = 0b1011'0100;     // 也可以用 0xB4
    unsigned hi = (reg >> 4) & 0x0F;     // 高 4 位
    unsigned lo = reg & 0x0F;            // 低 4 位
    printf("reg=0x%02X hi=0x%X lo=0x%X\n", reg, hi, lo); // B 4
    return 0;
}
```

**动手实验**：把 `reg` 的 bit2 置 1、bit5 清 0，但不动其他位（用 `|=` / `&=~`）。

## 5.2 字节序：寄存器/网络里的坑

见 02 章 2.5。`lscpu | grep -i byte` 可查本机大小端。ARM 既可以小端也可以大端，Linux 常用小端；网络一律大端。

```c
// 示例 2：用联合体检测本机字节序（不改任何头文件）
#include <stdio.h>
union { unsigned u; unsigned char c[4]; } e = { .u = 0x01020304 };
int main(void) {
    if (e.c[0] == 0x04) printf("小端(little-endian)\n");
    else                printf("大端(big-endian)\n");
    return 0;
}
```

## 5.3 对齐与 `sizeof`：结构体内存布局

CPU 访问对齐地址更快，某些架构（典型如部分 ARM）访问未对齐地址会直接总线错误。编译器会自动插入 padding。

```c
// 示例 3：对比两种成员排列的 sizeof
#include <stdio.h>
struct bad  { char c; int i; short s; };   // 可能因对齐而变大
struct good { int i; short s; char c; };   // 大成员在前更紧凑
int main(void) {
    printf("sizeof(bad)=%zu sizeof(good)=%zu\n", sizeof(struct bad), sizeof(struct good));
    return 0;
}
```

**动手实验**：用 `offsetof` 打印两个结构各成员偏移，理解 padding 从哪来；把 `c` 放到 `good` 末尾后 `sizeof` 是否变小？

## 5.4 内存布局：从地址看世界

一个进程的虚拟地址空间从上到下大致是：内核空间（高位）→ 栈 → 堆 → 数据段 → 代码段（低位）。理解"指针的值到底是什么地址"对读懂内核分页至关重要。

```c
// 示例 4：直观感受不同变量落在不同段
#include <stdio.h>
#include <stdlib.h>
int g = 1;                 // 数据段
int main(void) {
    int l = 2;             // 栈
    int *h = malloc(4);   // 堆
    printf("代码(main)=%p\n", (void*)main);
    printf("全局 g   =%p\n", (void*)&g);
    printf("局部 l   =%p\n", (void*)&l);
    printf("堆   h   =%p\n", (void*)h);
    free(h);
    return 0;
}
```

> 你会看到：栈地址最高，堆次之，全局/代码更低——这正是"栈向下增长、堆向上增长"的直观证据（对应内存管理章节的分页与虚拟地址）。

## 5.5 中断与异常：CPU 的"打断机制"

中断是硬件（如网卡、定时器）打断 CPU 当前执行、跳到中断处理程序的机制；异常是 CPU 执行指令出错（如除零、缺页）。内核靠中断/异常接管硬件事件——这也正是"上下文切换""系统调用"的入口。

```c
// 示例 5：用户态感受"异常"——除零触发 SIGFPE
#include <stdio.h>
#include <signal.h>
void on_fpe(int s) { printf("捕获到异常信号 %d（除零）\n", s); _exit(0); }
int main(void) {
    signal(SIGFPE, on_fpe);
    int a = 1 / 0;        // 触发异常，内核向进程发 SIGFPE
    return a;
}
```

**关键点**：用户态的"信号"其实是内核把硬件异常"翻译"后投递给进程的——这层翻译就是内核中断/异常处理子系统的职责。

## 5.6 自测题

1. 小端机上 `unsigned x=0x44332211;`，`(char*)&x` 指向的字节值是？
2. 为什么有些架构要求 `int*` 必须 4 字节对齐？不对齐会怎样？
3. 进程虚拟地址空间中，栈和堆的增长方向分别是什么？
4. 中断和异常的根本区别是什么？系统调用走的是哪一类？
5. 用掩码把 `reg` 的 bit3~bit5 这三位置成 `101`（不影响其他位），写出表达式。

## 5.7 常见陷阱与调试

- **写裸寄存器忘了 volatile**：操作 MMIO 寄存器时要用 `volatile`（告诉编译器别优化掉"看似无用"的读写），否则读写被优化掉，硬件行为错乱。
- **字节序误判**：跨设备解析多字节字段前，先用 5.2 的方法确认两端字节序。
- **对齐崩溃**：在严格架构上手写结构体强转/网络收包直接 `(struct hdr*)` 强转可能未对齐崩溃；应先 `memcpy` 到对齐缓冲。

---

> 返回：[01-编程基本功总览](01-bian-cheng-ji-ben-gong-zong-lan.md)
