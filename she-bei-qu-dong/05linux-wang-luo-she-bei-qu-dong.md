# 05-Linux 网络设备驱动

> 基于 Linux 3.10.29 内核分析。字符设备、块设备分别面向「字节流」「块」，而网络设备驱动走的是**协议栈专用路径**（不通过 `read/write`，而通过 `sk_buff` 与 `net_device`）。本章给出网卡驱动的核心框架。

## 1. 网络设备与 net_device

网络设备用 `struct net_device` 描述（不是 `cdev`/`gendisk`）。它**不对应 `/dev` 下的节点**，而是通过 `ifconfig`/`ip` 以接口名（eth0、ens33…）呈现。

```c
struct net_device {
    char name[IFNAMSIZ];          /* 接口名 */
    unsigned long state;          /* 设备状态 */
    const struct net_device_ops *netdev_ops;  /* 关键操作集 */
    const struct ethtool_ops *ethtool_ops;
    struct net_device_stats stats;            /* 收发统计 */
    ...
};
```

### 1.1 关键操作集 net_device_ops

```c
static const struct net_device_ops my_netdev_ops = {
    .ndo_open       = my_open,        /* ifconfig up */
    .ndo_stop       = my_stop,        /* ifconfig down */
    .ndo_start_xmit = my_xmit,        /* 发送数据 */
    .ndo_set_mac_address = my_set_mac,
    ...
};
```

## 2. 注册与注销

```c
struct net_device *dev = alloc_etherdev(sizeof(struct my_priv));
dev->netdev_ops = &my_netdev_ops;
ether_setup(dev);                 /* 初始化以太网默认项 */
register_netdev(dev);             /* 注册，生成 ethN 接口 */

/* 卸载时 */
unregister_netdev(dev);
free_netdev(dev);
```

## 3. 数据载体：sk_buff

网络数据用 `sk_buff`（简称 skb）承载，是协议栈各层之间传递数据的核心结构，支持头部预留、向前/向后推指针：

```c
struct sk_buff {
    unsigned char *head;   /* 缓冲区起点 */
    unsigned char *data;   /* 当前数据起点 */
    unsigned char *tail;   /* 当前数据终点 */
    unsigned char *end;    /* 缓冲区终点 */
    sk_buff_data_t len;    /* 数据长度 */
    ...
};

/* 常用操作 */
skb_put(skb, n);     /* tail 后移 n，增加数据 */
skb_push(skb, n);    /* data 前移 n，加头部（如封装 IP 头） */
skb_pull(skb, n);    /* data 后移 n，去头部（如剥 MAC 头） */
```

## 4. 数据发送（ndo_start_xmit）

协议栈要发送数据时调用驱动的 `ndo_start_xmit`，驱动把 skb 交给硬件 DMA：

```c
static netdev_tx_t my_xmit(struct sk_buff *skb, struct net_device *dev) {
    /* 1) 把 skb->data 映射到 DMA 区域 */
    /* 2) 写硬件发送描述符，启动 DMA */
    /* 3) 发送完成后硬件产生中断，在中断里 dev_kfree_skb(skb) */
    dev->stats.tx_packets++;
    return NETDEV_TX_OK;
}
```

## 5. 数据接收（NAPI 与中断）

接收有两种模式：

### 5.1 传统中断模式

每来一个包就中断一次，适合低速设备；高吞吐下中断风暴会拖垮 CPU。

### 5.2 NAPI（新 API，推荐）

高负载时关中断，改用**轮询**：

```c
static int my_poll(struct napi_struct *napi, int budget) {
    int work = 0;
    while (work < budget && 有包) {
        struct sk_buff *skb = 取一个包();
        skb->protocol = eth_type_trans(skb, dev);
        netif_receive_skb(skb);   /* 递交给协议栈 */
        work++;
    }
    if (work < budget) napi_complete(napi);  /* 收完，重新开中断 */
    return work;
}

/* 中断上半部：关中断并调度 NAPI 轮询 */
static irqreturn_t my_rx_isr(int irq, void *dev) {
    napi_schedule(&priv->napi);
    return IRQ_HANDLED;
}
```

协议栈入口 `netif_receive_skb()` 会把 skb 送往 `ip_rcv()`（详见网络协议栈章节）。

## 6. 驱动骨架示例

```c
static int my_probe(struct platform_device *pdev) {
    struct net_device *dev = alloc_etherdev(sizeof(struct my_priv));
    dev->netdev_ops = &my_netdev_ops;
    /* 申请 IRQ、映射寄存器、初始化 NAPI */
    register_netdev(dev);
    return 0;
}
```

## 7. 小结

网络设备驱动围绕 `net_device` + `sk_buff` 展开：发送走 `ndo_start_xmit`，接收走「中断/NAPI 轮询 → netif_receive_skb」。它不同于字符/块设备，数据不经过 VFS 的 read/write，而是直接汇入内核网络协议栈。
