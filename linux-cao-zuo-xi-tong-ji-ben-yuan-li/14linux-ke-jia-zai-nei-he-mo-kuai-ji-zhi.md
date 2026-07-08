# 14-Linux 可加载内核模块机制

> 基于 Linux 3.10.29 内核分析。Linux 内核可编译为「单体镜像」或「镜像 + 可加载模块（LKM）」。模块让驱动、文件系统、协议在不重启的情况下动态装入内核，极大方便了开发与部署。

## 1. 什么是内核模块

内核模块（`.ko` 文件）是一段**运行在内核态**的代码，可被 `insmod` 动态链接进运行中的内核，用 `rmmod` 卸载。它：
- 与内核**共享同一地址空间**，出错可能导致内核崩溃（Oops/Panic）；
- 能调用内核导出的符号（函数/变量），但**不能直接用 libc**；
- 常用场景：设备驱动、文件系统、netfilter 模块、调度器插件。

## 2. 模块的基本结构

```c
#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>

static int __init my_init(void) {
    printk(KERN_INFO "my_module: hello, loaded\n");
    return 0;            /* 非 0 表示加载失败 */
}

static void __exit my_exit(void) {
    printk(KERN_INFO "my_module: bye, unloaded\n");
}

module_init(my_init);    /* 指定加载时入口 */
module_exit(my_exit);    /* 指定卸载时入口 */

MODULE_LICENSE("GPL");          /* 许可证，影响符号可用性 */
MODULE_AUTHOR("anonymous");
MODULE_DESCRIPTION("a demo module");
```

- `__init`：加载后该函数所占内存可被释放（仅运行一次）；
- `__exit`：模块不可卸载时该段不链接进模块；
- `MODULE_LICENSE("GPL")`：声明许可证，否则内核标记为「污染（tainted）」，且无法使用 `EXPORT_SYMBOL_GPL` 符号。

## 3. 编译：Kbuild 与 Makefile

模块用内核的 Kbuild 系统编译，需指向已编译的内核源码树：

```makefile
# Makefile
obj-m += my_module.o

KDIR := /lib/modules/$(shell uname -r)/build
PWD  := $(shell pwd)

all:
	$(MAKE) -C $(KDIR) M=$(PWD) modules
clean:
	$(MAKE) -C $(KDIR) M=$(PWD) clean
```

```bash
make                  # 生成 my_module.ko
insmod my_module.ko   # 加载
lsmod | grep my_module
rmmod my_module       # 卸载
dmesg | tail          # 查看 printk 输出
```

## 4. 模块参数

运行时通过参数向模块传值：

```c
static int count = 1;
module_param(count, int, 0644);
MODULE_PARM_DESC(count, "number of times to print");
```

```bash
insmod my_module.ko count=5
# 也可在加载后改：echo 5 > /sys/module/my_module/parameters/count
```

## 5. 符号导出与依赖

模块间可共享函数，内核用 `EXPORT_SYMBOL` 导出：

```c
/* 内核或模块中导出 */
EXPORT_SYMBOL(my_func);          /* 所有模块可用 */
EXPORT_SYMBOL_GPL(my_func);      /* 仅 GPL 模块可用 */

/* 另一模块使用 */
extern void my_func(void);
```

`modprobe` 会**自动解析依赖**（读取 `modules.dep`），先装依赖再装目标；`insmod` 则需手动按顺序。

```bash
modprobe my_module     # 自动处理依赖与别名（推荐）
modinfo my_module.ko   # 查看模块信息/参数
depmod                  # 重建依赖库
```

## 6. 版本与兼容性（vermagic）

模块编译时绑定内核版本、编译器、配置（vermagic）。内核加载时会校验，不匹配通常拒绝加载：

```text
insmod: ERROR: could not insert module my.ko: Invalid module format
```

确保模块用**与运行内核一致**的源码树与配置编译。`CONFIG_MODVERSIONS` 可在一定程度上放宽符号版本校验。

## 7. 模块与内核的交互边界

- 模块运行于**内核态**，可直接访问内核数据结构、注册中断、操作硬件；
- 用户态程序通过 `/dev`、`/proc`、`/sys` 接口与模块通信（见设备驱动章节）；
- 切忌在模块里做用户态假设（无 libc、`printf`→用 `printk`、内存用 `kmalloc` 而非 `malloc`）。

## 8. 小结

内核模块是「动态扩展内核能力」的标准机制：以 `module_init/exit` 定义生命周期，`Kbuild` 编译，`insmod/modprobe` 装载，`EXPORT_SYMBOL` 共享符号。它是设备驱动与各类内核功能最常用的交付形态，也是理解内核「可插拔」设计的关键一环。
