# 02-C 语言与系统编程基本功

> 内核几乎完全用 C 语言（少量汇编）写成。想读懂内核，先要把 C 里"和硬件/内存打交道"的那部分练扎实：**指针、内存模型、结构体、宏、位运算、系统调用**。本章用最小可运行示例逐个突破。

## 2.1 指针与数组：一切的起点

内核里到处是指针：`task_struct *`、`struct file *`、`char *buf`。指针的本质是"一个存放地址的变量"，而数组名在大多数语境下会退化为指向首元素的指针。

```c
// 示例 1：指针与数组的关系
#include <stdio.h>

int main(void) {
    int a[4] = {10, 20, 30, 40};
    int *p = a;                 // 等价于 int *p = &a[0];
    printf("a[2]   = %d\n", a[2]);
    printf("*(p+2) = %d\n", *(p + 2));   // 指针算术：p+2 跳过 2 个 int
    printf("p[2]   = %d\n", p[2]);       // 下标运算符等价于 *(p+2)
    printf("sizeof(a)=%zu, sizeof(p)=%zu\n", sizeof(a), sizeof(p)); // 16 vs 8(64位)
    return 0;
}
```

**关键点**

- `p+2` 不是简单加 2 字节，而是加 `2 * sizeof(int)` 字节——指针算术按"所指类型的大小"步进。
- `sizeof(a)` 是整个数组的字节数；`sizeof(p)` 只是指针本身的大小（64 位下 8 字节）。这是数组"退化"为指针后信息丢失的典型表现。

**动手实验**：把 `int` 换成 `char` 和 `double`，重新打印 `*(p+2)` 与 `sizeof`，观察指针步进的字节数变化。

## 2.2 结构体与内存布局：理解 `container_of` 的前提

内核用结构体把相关数据组织在一起。理解结构体在内存里如何排布（以及对齐 padding），是读懂 `container_of` 宏的关键。

```c
// 示例 2：offsetof 与结构体成员偏移
#include <stdio.h>
#include <stddef.h>

struct task {
    int pid;            // 偏移 0
    int state;          // 偏移 4
    char name[8];       // 偏移 8
    void *stack;        // 偏移 16（因对齐，name 后可能有 padding）
};

int main(void) {
    printf("offsetof(pid)   = %zu\n", offsetof(struct task, pid));
    printf("offsetof(state) = %zu\n", offsetof(struct task, state));
    printf("offsetof(name)  = %zu\n", offsetof(struct task, name));
    printf("offsetof(stack) = %zu\n", offsetof(struct task, stack));
    printf("sizeof(task)    = %zu\n", sizeof(struct task));
    return 0;
}
```

**关键点**：成员之间可能因为**对齐（alignment）**插入填充字节（padding）。`stack` 是指针（需 8 字节对齐），所以即使 `name[8]` 只占 8 字节，`stack` 的偏移也可能是 16 而非 16——请实际编译确认你平台上的结果。

## 2.3 `container_of`：内核最经典的宏

内核链表 `struct list_head` 只存前后指针，并不内嵌数据；要找到"包含它的结构体"，就要用 `container_of` 根据成员地址反推结构体首地址。这是面试和读内核的高频考点。

```c
// 示例 3：手写 container_of（用户态模拟）
#include <stdio.h>
#include <stddef.h>

/* 内核里的定义（简化） */
#define container_of(ptr, type, member) \
    ((type *)((char *)(ptr) - offsetof(type, member)))

struct list_head {                 // 模拟内核链表节点
    struct list_head *next, *prev;
};

struct task {
    int pid;
    struct list_head list;        // 把链表节点嵌在 task 里
};

int main(void) {
    struct task t = { .pid = 42 };
    struct list_head *pos = &t.list;          // 遍历时只拿到 list 的地址
    struct task *owner = container_of(pos, struct task, list); // 反推宿主
    printf("通过 list 节点找回的 pid = %d\n", owner->pid);     // 42
    return 0;
}
```

**关键点**：`(char *)(ptr) - offsetof(type, member)` 先转成 `char *`（逐字节算术），减去成员偏移，就得到结构体首地址，再强转回 `type *`。这是"侵入式链表"的核心思想。

**动手实验**：在 `struct task` 中调换 `pid` 与 `list` 的顺序，重新编译，验证 `container_of` 依然正确——因为它依赖编译期算出的偏移，与顺序无关。

## 2.4 位运算：内核里的"开关与标志"

内核大量用位域表示状态/权限/标志（`flags`）。掌握置位、清位、取位、翻转，才能读懂 `set_bit`、`test_bit` 等。

```c
// 示例 4：用位运算管理一组标志
#include <stdio.h>

enum { F_READ = 1 << 0, F_WRITE = 1 << 1, F_EXEC = 1 << 2 };

void dump(unsigned f) {
    printf("READ=%d WRITE=%d EXEC=%d\n",
           !!(f & F_READ), !!(f & F_WRITE), !!(f & F_EXEC));
}

int main(void) {
    unsigned flags = 0;
    flags |= F_READ | F_WRITE;     // 置位
    dump(flags);                   // READ=1 WRITE=1 EXEC=0
    flags &= ~F_WRITE;             // 清位
    dump(flags);                   // READ=1 WRITE=0 EXEC=0
    flags ^= F_EXEC;               // 翻转
    dump(flags);                   // READ=1 WRITE=0 EXEC=1
    printf("EXEC 是否设置: %d\n", (flags & F_EXEC) ? 1 : 0);
    return 0;
}
```

**关键点**

- `1 << n` 生成第 n 位为 1 的掩码；
- `flags |= MASK` 置位，`flags &= ~MASK` 清位，`flags ^= MASK` 翻转；
- 取某一位要用 `!!(flags & MASK)` 把非 0 值规范成 1。

**动手实验**：写一个函数 `unsigned set_bit_n(unsigned x, int n)`，把第 n 位置 1 并返回，要求不能用 `if`/三元运算符，只用位运算。

## 2.5 字节序：网络与跨平台绕不开

不同 CPU 对多字节整数的存储顺序不同（大端 / 小端）。网络协议统一用**大端（网络字节序）**，所以内核网络栈充满 `htonl`/`ntohl` 之类的转换。

```c
// 示例 5：观察本机字节序并做转换
#include <stdio.h>
#include <arpa/inet.h>   // htonl/ntohl（Linux）

int main(void) {
    unsigned int v = 0x01020304;
    unsigned char *p = (unsigned char *)&v;
    printf("本机字节序: %02x %02x %02x %02x\n", p[0], p[1], p[2], p[3]);
    // 小端机会打印 04 03 02 01；大端机打印 01 02 03 04
    unsigned int net = htonl(v);
    unsigned char *q = (unsigned char *)&net;
    printf("网络字节序: %02x %02x %02x %02x\n", q[0], q[1], q[2], q[3]);
    return 0;
}
```

**关键点**：`htonl`（host to network, long）把主机序转网络序，`ntohl` 反之。写网络程序时，**凡是经网络收发的多字节整数都必须转换**，否则跨架构通信会解析错乱。

**动手实验**：不调用库函数，自己写一个 `my_htonl(unsigned int)`，用移位和掩码实现主机序→大端，并与 `htonl` 的结果对比。

## 2.6 系统调用与文件 IO：用户态操作系统的入口

用户程序不能直接碰硬件，必须通过**系统调用**进入内核。`open/read/write/close` 就是最典型的文件类系统调用（对应基本原理 05 IO 机制、文件系统章节）。

```c
// 示例 6：用系统调用读写文件（对应内核的 sys_open/read/write）
#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <string.h>

int main(void) {
    int fd = open("demo.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) { perror("open"); return 1; }
    const char *msg = "hello from syscall\n";
    write(fd, msg, strlen(msg));     // 进入内核，由内核把数据拷到页缓存/磁盘
    close(fd);

    fd = open("demo.txt", O_RDONLY);
    char buf[64] = {0};
    ssize_t n = read(fd, buf, sizeof(buf) - 1);
    printf("读到了 %zd 字节: %s", n, buf);
    close(fd);
    return 0;
}
```

**关键点**

- `fd`（文件描述符）是内核里 `struct file` 在用户态的句柄；用户态只持有整数，真正的状态在内核。
- `write` 不保证立刻落盘（涉及页缓存、回写，见内存管理/文件系统章节），这是"IO 机制"原理在代码层的体现。

**动手实验**：用 `strace -f ./a.out` 运行上面的程序，观察它实际触发了哪些系统调用（你会在输出里看到 `openat`、`write`、`close`、`read`）。

## 2.7 自测题

1. `int a[5]; int *p = a;`，表达式 `*(p + 3)` 与 `p[3]` 是否等价？`p + 3` 实际跳过了多少字节？
2. 为什么 `container_of` 要把指针先转成 `char *` 再做减法？
3. 写出把 `unsigned x` 的第 n 位**取反**且**不影响其他位**的表达式。
4. 小端机器上 `int v = 0x12345678;`，`((char *)&v)[0]` 的值是什么？
5. 用户程序调用 `read()` 时，数据从磁盘到用户缓冲经历了哪几层（结合本书 IO / 文件系统章节思考）？

## 2.8 常见陷阱与调试

- **段错误（SIGSEGV）**：90% 来自"解引用空指针 / 已释放指针 / 数组越界"。用 `gdb` 跑，崩溃时 `bt` 看调用栈，定位到具体行。
- **指针算术踩错步长**：忘记指针按类型大小步进，导致读写错位。打印 `sizeof(*p)` 核对。
- **对齐问题**：在部分架构（如某些 ARM）上，未对齐访问会直接总线错误；x86 虽容错但更慢。结构体里把"大对齐成员"放前面通常更省空间。
- **字节序 bug**：多字节数据跨网络/跨设备时没转换，现象是"数字看起来对，但高位低位反了"。

---

> 下一章：[03-内核常用数据结构与算法基本功](03-nei-he-chang-yong-shu-ju-jie-gou-yu-suan-fa-ji-ben-gong.md)
