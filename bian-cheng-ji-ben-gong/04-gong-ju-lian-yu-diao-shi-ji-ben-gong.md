# 04-工具链与调试基本功

> "能编译"只是第一步，"能调试"才决定你能不能真正吃透一个内核机制。本章覆盖日常最高频的四件套：`gcc` 编译选项、`Makefile`、`gdb`、`strace`/`valgrind`，并给出可直接照做的实验。

## 4.1 `gcc`：把选项用对

| 选项 | 作用 | 何时用 |
|------|------|--------|
| `-std=c11 -Wall -Wextra` | 现代标准 + 严格警告 | 永远开着，警告常是隐藏 bug |
| `-g` | 生成调试符号 | 要 `gdb` 必须加 |
| `-O0` / `-O2` | 关闭 / 开启优化 | 调试用 `-O0`（否则变量被优化掉、行号错乱） |
| `-fsanitize=address` | 编译期插入内存错误检测 | 怀疑越界/泄漏时首选 |
| `-static` | 静态链接 | 做最小可移植镜像时 |

```bash
# 带调试符号、无优化、严格警告地编译
gcc -std=c11 -Wall -Wextra -g -O0 demo.c -o demo
```

**动手实验**：故意写 `int a[3]; a[5]=1;`（越界），分别用 `gcc -O0` 和 `gcc -O2` 编译运行，再用 `-fsanitize=address` 编译，观察错误如何被立刻定位到行。

## 4.2 `Makefile`：别再手敲 gcc

```makefile
# 最小可用 Makefile
CC      ?= gcc
CFLAGS  ?= -std=c11 -Wall -Wextra -g -O0
TARGETS  = demo list_demo bit_demo

all: $(TARGETS)

%: %.c
	$(CC) $(CFLAGS) $< -o $@

clean:
	rm -f $(TARGETS)

.PHONY: all clean
```

要点：`$<` 是依赖（源文件），`$@` 是目标；`%: %.c` 是模式规则，一次搞定所有示例；`.PHONY` 声明伪目标避免和同名文件冲突。

**动手实验**：`make` 一键编出本章所有示例；改一个 `.c` 再 `make`，确认只重编了它（增量构建）。

## 4.3 `gdb`：看透运行时

```bash
gcc -g -O0 demo.c -o demo
gdb ./demo
(gdb) break main          # 在 main 设断点
(gdb) run                 # 运行
(gdb) next                # 单步（不进函数）
(gdb) step                # 单步（进函数）
(gdb) print pid           # 打印变量
(gdb) x/4xw &v           # 以 4 个 16 进制字查看 v 的内存
(gdb) backtrace           # 崩溃时看调用栈
(gdb) watch flags         # 变量变化时中断（定位"谁改了我的标志"）
```

**动手实验**：在 02 章 `container_of` 示例里，对 `main` 设断点，用 `print &t` 和 `print pos` 对比地址，再用 `x/16xb pos` 看 `list` 节点在 `task` 中的内存布局，直观验证偏移。

## 4.4 `strace`：看见系统调用

```bash
# 跟踪某进程碰过的所有系统调用
strace -f ./demo 2>&1 | head -40
# 只关心文件类调用
strace -e trace=file ./demo
# 统计各调用耗时/次数
strace -c ./demo
```

这能让你把"用户态代码"和"内核真正做的事"对应起来——例如 02 章 `open/write/read` 会在 `strace` 里显示为 `openat/write/read`。

**动手实验**：`strace -e trace=network ./your_client`，观察 `socket/connect/sendto/recvfrom`，把网络协议栈章节的"系统调用边界"落在实际输出上。

## 4.5 `valgrind`：抓住内存泄漏

```bash
gcc -g -O0 leak.c -o leak
valgrind --leak-check=full ./leak
```

它会报告"definitely lost / indirectly lost"的内存，精确到分配处的调用栈。

**动手实验**：写一个 `malloc` 后 `return` 却忘记 `free` 的程序，用 valgrind 定位泄漏点，再补上 `free` 复测到 clean。

## 4.6 自测题

1. 为什么调试时推荐 `-O0` 而不是 `-O2`？
2. `gdb` 里 `next` 和 `step` 的区别？想进 `container_of` 这种宏展开该用什么？
3. 如何只用 `strace` 判断一个程序"卡在等 IO 还是算得慢"？
4. `valgrind` 报 "still reachable" 与 "definitely lost" 有何区别，哪个必须修？

## 4.7 常见陷阱与调试

- **忘加 `-g`**：`gdb` 里看不到变量、行号对不上——重新带 `-g` 编译。
- **优化破坏调试**：`-O2` 下变量被寄存器化/内联，打印 `pid` 可能显示 `<optimized out>`，务必 `-O0`。
- **strace 权限**：跟踪别人/系统进程需要权限；跟踪自己编译的程序最方便。
- **valgrind 慢**：它会把程序跑慢几十倍，只用于排错，不用于性能基准。

---

> 下一章：[05-计算机系统基础基本功](05-ji-suan-ji-xi-tong-ji-chu-ji-ben-gong.md)
