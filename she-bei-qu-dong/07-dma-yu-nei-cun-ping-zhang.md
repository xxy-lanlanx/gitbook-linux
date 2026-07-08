# 07-DMA 与内存屏障

## 一、DMA 的基本原理

**DMA（Direct Memory Access，直接内存访问）**允许外部设备在不经过 CPU 干预的情况下直接读写系统内存。没有 DMA 时，CPU 必须逐字节将数据从设备读到寄存器，再写入内存——这在网络、磁盘、显卡等高速设备上是不可接受的。

### 1. DMA 传输流程

```
CPU 侧：
  1. 分配 DMA 可用内存（物理连续或 IOMMU 映射）
  2. 配置 DMA 控制器（源地址、目标地址、长度、方向）
  3. 启动 DMA，CPU 去做其他事

DMA 控制器侧：
  4. 直接接管总线，传输数据
  5. 传输完成后发出中断

CPU 收到中断：
  6. 确认传输完成，处理数据
```

### 2. DMA 地址空间问题

传统 DMA 要求内存地址是**物理连续**且落在 DMA 引擎可访问的范围内：

```c
// 物理连续内存分配
void *dma_alloc_coherent(struct device *dev, size_t size,
                         dma_addr_t *dma_handle, gfp_t gfp);
// 返回：
// - 虚拟地址（CPU 使用）
// - dma_handle（DMA 控制器使用，可能是物理地址或 IOMMU 映射地址）
```

**为什么需要 `dma_alloc_coherent` 而不是 `kmalloc`？**

- `kmalloc` 分配的内存可能位于高端内存（highmem），CPU 通过 kmap 访问，但 DMA 引擎可能无法直接访问高端内存地址。
- `dma_alloc_coherent` 确保内存同时满足：CPU 可访问（虚拟地址）、DMA 可访问（总线地址）、缓存一致性（coherent）。

## 二、IOMMU 与流式 DMA

### 1. IOMMU（Input-Output Memory Management Unit）

现代系统（x86 的 VT-d、ARM 的 SMMU）普遍配备了 IOMMU：

```
设备虚拟地址 (IOVA)
       │
       ▼
   ┌──────────┐
   │  IOMMU   │  页表转换
   │ (SMMU)   │
   └────┬─────┘
        │
        ▼
  物理内存地址
```

- IOMMU 让设备可以使用**虚拟地址（IOVA）**访问内存，内核通过页表映射到任意物理页。
- 不再需要物理连续内存，可以使用 `dma_alloc_attrs()` + `DMA_ATTR_NON_CONSISTENT`。
- 提供**内存保护**：设备无法访问未授权的物理页（防止恶意 DMA 攻击）。

### 2. 流式 DMA 映射（Streaming DMA）

对于网络包等不需要长期驻留的数据，使用**流式映射**更灵活：

```c
// 将已有缓冲区映射给 DMA 使用
dma_addr_t dma_map_single(struct device *dev, void *ptr,
                          size_t size, enum dma_data_direction dir);

// 使用完毕后取消映射
void dma_unmap_single(struct device *dev, dma_addr_t dma_addr,
                      size_t size, enum dma_data_direction dir);
```

| 方向 | 含义 | 使用场景 |
|------|------|----------|
| `DMA_TO_DEVICE` | CPU 写入，设备读取 | 发送网络包 |
| `DMA_FROM_DEVICE` | 设备写入，CPU 读取 | 接收网络包 |
| `DMA_BIDIRECTIONAL` | 双向 | 需要同步后回读 |

### 3. 同步点（Sync）的重要性

当 CPU 和 DMA 共享缓存时，必须使用 `dma_sync_*` 系列函数：

```c
// CPU 准备数据后，让 DMA 看到最新数据
void dma_sync_single_for_device(struct device *dev, dma_addr_t addr,
                                size_t size, enum dma_data_direction dir);

// DMA 完成后，让 CPU 看到最新数据
void dma_sync_single_for_cpu(struct device *dev, dma_addr_t addr,
                             size_t size, enum dma_data_direction dir);
```

如果没有正确同步，CPU 可能读到缓存中的旧数据，而 DMA 已经修改了内存。

## 三、DMA 与缓存一致性

### 1. 三种 DMA 一致性策略

| 策略 | 实现 | 特点 |
|------|------|------|
| 一致（Coherent） | 关闭 DMA 区域的缓存（Uncached）或硬件自动同步 | 最简单，性能略低 |
| 非一致（Non-coherent） | CPU 和 DMA 各自缓存，需要显式 flush/invalidate | 性能最高，但复杂 |
| IOMMU 映射 | IOMMU 维护页表属性（如 ARM 的 Shareable） | 现代主流 |

```c
// 一致映射（简单但慢）
dma_alloc_coherent(dev, size, &dma_handle, GFP_KERNEL);

// 非一致映射（高性能，需要手动同步）
void *cpu_addr = kmalloc(size, GFP_KERNEL);
dma_addr = dma_map_single(dev, cpu_addr, size, DMA_TO_DEVICE);
// ... CPU 写入数据 ...
dma_sync_single_for_device(dev, dma_addr, size, DMA_TO_DEVICE);
// DMA 传输
// ... DMA 完成后 ...
dma_sync_single_for_cpu(dev, dma_addr, size, DMA_FROM_DEVICE);
// CPU 读取数据
dma_unmap_single(dev, dma_addr, size, DMA_FROM_DEVICE);
```

### 2. ARM 的 DMA 内存属性

ARM 架构使用内存类型（Memory Type）和共享属性（Shareability）来定义一致性：

| 内存类型 | 缓存 | 写策略 | 一致性 |
|----------|------|--------|--------|
| Device | 无 | 透传 | 自动一致 |
| Normal, Non-cacheable | 无 | — | 自动一致 |
| Normal, Inner Shareable | 有 | Write-back | 多核缓存一致 |
| Normal, Outer Shareable | 有 | Write-back | 包含 DMA 控制器 |

DMA 区域通常映射为 **Normal, Outer Shareable**，让 CPU 缓存和 DMA 控制器共享一致性。

## 四、内存屏障（Memory Barrier）

### 1. 为什么需要内存屏障

现代 CPU 为了性能，会对指令和内存访问进行**重排序**：

- **编译器重排序**：编译器优化时调整指令顺序
- **CPU 乱序执行**：超标量处理器同时执行多条指令
- **缓存写延迟**：Store Buffer 和 Invalidate Queue 导致内存可见性延迟

在 DMA 和驱动程序中，这种重排序可能导致灾难性后果：

```c
// 驱动代码（无屏障）
buffer[0] = 0xDEADBEEF;  // 1. 写入数据
status = READY;            // 2. 设置状态标志
// DMA 控制器看到 READY 后，开始读取 buffer
// 但 CPU 可能先执行了 2，再执行 1，DMA 读到旧数据！
```

### 2. Linux 内存屏障 API

| 屏障 | 作用 | 适用场景 |
|------|------|----------|
| `mb()` / `smp_mb()` | 全内存屏障，读写都不能跨越 | 设置标志 + 随后 DMA 读取 |
| `rmb()` / `smp_rmb()` | 读屏障，后面的读不能跨越前面的读 | 读取 DMA 完成状态后读取数据 |
| `wmb()` / `smp_wmb()` | 写屏障，前面的写不能跨越后面的写 | 先写数据，再写 DMA 启动寄存器 |
| `dma_wmb()` | 专门针对 DMA 的写屏障 | 设备驱动写描述符后通知设备 |
| `dma_rmb()` | 专门针对 DMA 的读屏障 | 检查设备状态后读取数据 |

### 3. 典型 DMA 驱动中的屏障使用

```c
// 发送网络包：先写数据，再写描述符，最后通知设备
void tx_packet(struct ring *ring, struct sk_buff *skb)
{
    // 1. 拷贝数据到 DMA 缓冲区
    memcpy(ring->tx_buf[ring->tx_next], skb->data, skb->len);
    
    // 2. 写屏障：确保数据先写入内存，再写描述符
    dma_wmb();
    
    // 3. 写描述符（设备会读取）
    ring->tx_desc[ring->tx_next].addr = ring->tx_buf_dma[ring->tx_next];
    ring->tx_desc[ring->tx_next].len = skb->len;
    ring->tx_desc[ring->tx_next].flags = DESC_OWN;  // 交给设备
    
    // 4. 写屏障：确保描述符先写入，再通知设备
    wmb();
    
    // 5. 写设备寄存器通知 DMA 开始
    writel(ring->tx_next, ring->mmio + TX_TAIL_REG);
}
```

```c
// 接收网络包：先检查描述符，再读数据
void rx_packet(struct ring *ring)
{
    // 1. 读取描述符状态
    u32 flags = ring->rx_desc[ring->rx_next].flags;
    
    // 2. 读屏障：确保描述符读取完成后再读数据
    dma_rmb();
    
    // 3. 读取 DMA 缓冲区中的数据
    if (flags & DESC_RX_OK) {
        skb = build_skb(ring->rx_buf[ring->rx_next]);
        // ...
    }
}
```

### 4. 编译器屏障 vs 硬件屏障

```c
// 编译器屏障：防止编译器重排序
barrier();

// 硬件内存屏障：防止 CPU 和缓存重排序
smp_mb();

// 带编译器屏障的赋值
WRITE_ONCE(var, value);   // 等价于：barrier(); var = value; barrier();
READ_ONCE(var);           // 等价于：barrier(); return var; barrier();
```

在驱动代码中，访问设备寄存器应始终使用 `readl()`/`writel()` 系列，它们内部已包含适当的屏障。直接通过指针访问 MMIO 是危险的。

## 五、DMA 与设备树（ARM）

在 ARM 设备中，DMA 通常通过设备树（DTS）描述：

```dts
// arch/arm/boot/dts/some-soc.dtsi
dma: dma-controller@48000000 {
    compatible = "some,vendor-dma";
    reg = <0x48000000 0x1000>;
    interrupts = <GIC_SPI 50 IRQ_TYPE_LEVEL_HIGH>;
    #dma-cells = <1>;
    dma-channels = <8>;
    dma-requests = <64>;
};

// 网卡设备使用 DMA
ethernet@50000000 {
    compatible = "some,vendor-eth";
    reg = <0x50000000 0x4000>;
    interrupts = <GIC_SPI 60 IRQ_TYPE_LEVEL_HIGH>;
    dmas = <&dma 5>, <&dma 6>;  // 使用 DMA 通道 5 和 6
    dma-names = "rx", "tx";
};
```

驱动代码中通过 `dma_request_chan()` 获取 DMA 通道：

```c
struct dma_chan *dma_request_chan(struct device *dev, const char *name);
// 对于上面的 DTS，name = "rx" 或 "tx"
```

## 六、总结

| 概念 | 要点 |
|------|------|
| DMA | 设备直接访问内存，绕过 CPU |
| IOMMU | 让设备使用虚拟地址，提供保护和灵活性 |
| Coherent DMA | 关闭缓存或硬件自动同步，最简单 |
| Streaming DMA | 复用已有缓冲区，需手动 sync |
| 内存屏障 | 防止编译器和 CPU 重排序，保证 DMA 可见性 |
| `dma_wmb()` | 写数据 → 写描述符 → 通知设备 |
| `dma_rmb()` | 读描述符 → 读数据 |

编写设备驱动时，DMA 和内存屏障是最容易出现 bug 的地方。遵循原则：

1. **分配内存优先使用 `dma_alloc_coherent`**，除非性能测试证明需要流式映射
2. **每次 DMA 前后都调用 `dma_sync_*`**，宁可多调用不可遗漏
3. **写寄存器前使用 `wmb()`，读寄存器后使用 `rmb()`**
4. **使用 `readl`/`writel` 而不是裸指针**，它们已包含正确屏障
