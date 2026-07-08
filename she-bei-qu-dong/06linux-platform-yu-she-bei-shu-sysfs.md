# 06-Linux Platform 模型、设备树与 sysfs

> 基于 Linux 3.10.29 内核分析。嵌入式 SoC 上大量「非即插即用」的片上外设（I2C 控制器、PWM、GPIO…）无法像 PCI 那样自动枚举，于是内核用 **Platform 总线**描述它们，现代 ARM 上再用 **设备树（Device Tree）** 声明硬件信息。这一切在用户空间通过 **sysfs** 暴露。

## 1. Platform 总线/设备/驱动

Platform 是内核中的一种「伪总线」，用于把无自枚举能力的设备与驱动匹配起来。三者关系（呼应第 01 章总线-设备-驱动模型）：

```text
platform_device  ──匹配──>  platform_driver
（描述资源：寄存器地址、IRQ）   （描述probe/remove逻辑）
        │
        └── 匹配依据：name 或 of_match_table（设备树）
```

### 1.1 platform_device（资源声明）

```c
static struct resource my_res[] = {
    [0] = { .start = 0x40000000, .end = 0x40000FFF,
            .flags = IORESOURCE_MEM },          /* 寄存器区间 */
    [1] = { .start = 32, .end = 32,
            .flags = IORESOURCE_IRQ },          /* 中断号 */
};

static struct platform_device my_dev = {
    .name = "my_led",
    .id   = -1,
    .resource = my_res,
    .num_resources = ARRAY_SIZE(my_res),
};
platform_device_register(&my_dev);
```

### 1.2 platform_driver（驱动逻辑）

```c
static int my_probe(struct platform_device *pdev) {
    struct resource *r = platform_get_resource(pdev, IORESOURCE_MEM, 0);
    void __iomem *base = ioremap(r->start, resource_size(r));
    /* 注册中断、初始化硬件、建立 sysfs/字符设备 */
    return 0;
}
static int my_remove(struct platform_device *pdev) { /* 反初始化 */ return 0; }

static struct platform_driver my_drv = {
    .probe  = my_probe,
    .remove = my_remove,
    .driver = { .name = "my_led", .owner = THIS_MODULE },
};
module_platform_driver(my_drv);   /* 宏：注册/注销 */
```

## 2. 设备树（Device Tree）

ARM 早期内核把硬件信息硬编码在 C 文件里（`machine_desc`），导致「每款板子一个内核」。设备树把硬件描述从内核里**剥离成数据**：

- **DTS**：设备树源文件（`.dts`），用树形文本描述 CPU、内存、外设、寄存器、中断；
- **DTB**：编译后的二进制，由 bootloader 传给内核；
- **DTC**：DTS 编译器。

```dts
/ {
    soc {
        uart0: serial@4000c000 {
            compatible = "vendor,uart";
            reg = <0x4000c000 0x1000>;   /* 寄存器地址+长度 */
            interrupts = <0 32 4>;        /* 中断号/类型 */
            status = "okay";
        };
    };
};
```

驱动通过 `of_match_table` 与 `compatible` 字符串匹配：

```c
static const struct of_device_id my_of_match[] = {
    { .compatible = "vendor,uart" },
    { }
};
static struct platform_driver my_drv = {
    .probe = my_probe,
    .driver = { .name = "my_uart", .of_match_table = my_of_match },
};
```

在 `probe()` 中读取设备树资源：

```c
struct device_node *np = pdev->dev.of_node;
base = of_iomap(np, 0);                 /* 按设备树 reg 映射 */
irq = irq_of_parse_and_map(np, 0);      /* 解析中断号 */
```

## 3. sysfs：内核对象的用户空间视图

`sysfs` 挂载于 `/sys`，把内核的 `kobject` 层级映射成目录树，是「设备-驱动-总线」关系的可视化窗口。

### 3.1 kobject / kset

```c
struct kobject {
    const char *name;
    struct kobject *parent;
    struct kset *kset;
    struct kobj_type *ktype;   /* 含 release、属性操作 */
};
```

- `kobject` 是几乎所有内核对象（device、driver、bus）的「基类」；
- `kset` 是 kobject 的集合（如 `/sys/bus`、`/sys/devices`）；
- 引用计数归零时调用 `ktype->release` 释放对象。

### 3.2 属性文件（attribute）

把内核变量以文件形式暴露给用户空间，可读写：

```c
static ssize_t enabled_show(struct kobject *k, struct kobj_attribute *a, char *buf) {
    return sprintf(buf, "%d\n", g_enabled);
}
static ssize_t enabled_store(struct kobject *k, struct kobj_attribute *a,
                             const char *buf, size_t n) {
    sscanf(buf, "%d", &g_enabled);
    return n;
}
static struct kobj_attribute enabled_attr =
    __ATTR(enabled, 0644, enabled_show, enabled_store);

/* 创建到 sysfs */
sysfs_create_file(&dev->kobj, &enabled_attr.attr);
```

用户空间即可：

```bash
cat /sys/devices/platform/my_led/enabled
echo 1 > /sys/devices/platform/my_led/enabled
```

### 3.3 常见 sysfs 路径

```text
/sys/devices/        所有设备（真实硬件拓扑）
/sys/bus/            按总线分类（pci/platform/i2c…）
/sys/class/          按功能分类（net/leds/tty…）
/sys/module/         已加载模块的参数与状态
```

## 4. 与 procfs / debugfs 的区别

- **sysfs**：描述「设备与对象的体系结构」，一个属性一个文件，要求稳定 ABI；
- **procfs**（`/proc`）：最初用于进程信息，后来杂项滥用，新接口应优先用 sysfs；
- **debugfs**（`/sys/kernel/debug`）：仅供调试，无稳定性保证，可放任意内部状态。

## 5. 小结

Platform 模型 + 设备树让 ARM 驱动「与板级硬件解耦」：硬件信息写在 DTS，驱动通过 `compatible` 匹配，资源用 `of_` 接口读取；sysfs 则把内核对象以文件树呈现，是排查设备/驱动匹配问题的第一现场。
