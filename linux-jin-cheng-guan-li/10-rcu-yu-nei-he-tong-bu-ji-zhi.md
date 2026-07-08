# 10-RCU 与内核同步机制深入

## 一、为什么需要 RCU

在读多写少的场景中，传统读写锁（`rwlock`、`seqlock`）存在以下问题：

- **读写锁**：读锁会阻塞写锁，写锁会阻塞所有读锁。当读操作极频繁时，写操作可能长时间饥饿。
- **顺序锁（seqlock）**：写操作不阻塞读，但读操作需要反复重试（直到序列号一致）。对于读操作极多的场景，重试开销累积严重。

**RCU（Read-Copy-Update）**的设计目标：

- **读操作无需任何锁、无需原子操作、无缓存行乒乓**，性能接近裸读
- **写操作通过复制 + 替换 + 延迟释放完成**，不需要阻塞读
- 典型场景：路由表、文件系统缓存、设备列表、进程链表等读多写少的数据结构

## 二、RCU 核心思想

RCU 基于一个关键观察：在 Linux 内核中，任何代码都不会长期阻塞（不能睡眠的上下文）。因此，只要等待一个**宽限期（Grace Period）**——即所有 CPU 都至少发生一次上下文切换——就可以确保所有旧的 RCU 读端临界区都已结束。

### 1. RCU 三阶段

```
阶段 1：读取（Read Side）
  rcu_read_lock()
      │
      ▼
  读取共享数据（指针解引用）
      │
      ▼
  rcu_read_unlock()

阶段 2：更新（Update Side）
  1. 复制旧数据到新内存
  2. 修改新数据
  3. 原子替换指针（publish）
  4. 等待 Grace Period（synchronize_rcu()）
  5. 释放旧数据（callback）
```

### 2. 关键保证：Publish-Subscribe 机制

```c
struct foo {
    int a;
    int b;
};

struct foo *gp = NULL;

// 写端：发布新数据
void update(void)
{
    struct foo *p = kmalloc(sizeof(*p), GFP_KERNEL);
    p->a = 1;
    p->b = 2;
    
    // 关键：rcu_assign_pointer 保证 p->a 和 p->b 的写入
    // 对读端可见后，才更新 gp
    rcu_assign_pointer(gp, p);
    
    // 等待宽限期
    synchronize_rcu();
    
    // 现在可以安全释放旧数据
    kfree(old_p);
}

// 读端：订阅数据
void read(void)
{
    struct foo *p;
    
    rcu_read_lock();
    p = rcu_dereference(gp);  // 保证看到完整的指针和指向的数据
    if (p) {
        // 使用 p->a, p->b
        do_something(p->a, p->b);
    }
    rcu_read_unlock();
}
```

## 三、RCU 的内核实现

### 1. 宽限期（Grace Period）机制

Linux 使用**树形 RCU（Tree RCU）**来管理宽限期：

```
RCU层级（以 64 CPU 为例）：

        rcu_node[0]          (根节点，覆盖所有 CPU)
       /    \
   rcu_node[1] rcu_node[2]   (覆盖 CPU 0-31 / 32-63)
   /   \
rcu_node[3] ...               (覆盖 CPU 0-15)
...
rcu_node[N]                  (叶节点，每个覆盖 1-4 个 CPU)
```

每个 CPU 在 `rcu_read_lock()` 时标记 `rcu_data.gpcpu`，在 `rcu_read_unlock()` 或上下文切换时清除。当一个 `rcu_node` 下的所有 CPU 都完成时，向上汇报，直到根节点确认全局宽限期完成。

### 2. 核心数据结构

```c
// kernel/rcu/tree.h
struct rcu_state {
    struct rcu_node node[NUM_RCU_NODES];  // 树形节点
    struct rcu_data percpu[NR_CPUS];      // 每 CPU 数据
    unsigned long gp_seq;                // 当前宽限期序列号
};

struct rcu_node {
    raw_spinlock_t lock;
    unsigned long gp_seq;       // 当前节点确认的 gp
    unsigned long qsmask;       // 哪些 CPU 尚未完成 quiescent state
    // ...
};

struct rcu_data {
    unsigned long gp_seq;       // 本 CPU 看到的 gp
    struct rcu_head *nxttail[RCU_NEXT_TAIL]; // 回调队列
    bool gp_started;            // 是否正在读端临界区
};
```

### 3. 关键路径代码

```c
// kernel/rcu/tree.c
static __always_inline void rcu_read_lock(void)
{
    __rcu_read_lock();
    // 在不可抢占内核中：禁止抢占即等同于进入 RCU 读端
    // 在可抢占内核中：需要显式跟踪 RCU 状态
}

void synchronize_rcu(void)
{
    // 1. 发起新的 Grace Period 请求
    rcu_gp_init();
    
    // 2. 等待所有 CPU 完成 quiescent state
    wait_for_gp_completion();
    
    // 3. 执行所有注册的回调
    invoke_rcu_callbacks();
}
```

### 4. 可睡眠 RCU（SRCU）

标准 RCU 读端临界区不能睡眠。对于需要睡眠的场景，使用 SRCU：

```c
#include <linux/srcu.h>

struct srcu_struct ss;

// 初始化
init_srcu_struct(&ss);

// 读端（可以睡眠）
int idx = srcu_read_lock(&ss);
// ... 读取数据，可以睡眠 ...
srcu_read_unlock(&ss, idx);

// 写端
synchronize_srcu(&ss);  // 等待 SRCU 宽限期
// 释放旧数据
```

SRCU 的宽限期判定更严格：必须等待所有 `srcu_read_lock()` 对应的 `srcu_read_unlock()` 都调用完毕。

## 四、RCU 与链表操作

Linux 提供了一套 RCU 安全的链表 API：

```c
// include/linux/rculist.h
struct list_head my_list;

// 读端遍历
void read_list(void)
{
    struct my_struct *p;
    
    rcu_read_lock();
    list_for_each_entry_rcu(p, &my_list, list) {
        // 使用 p
    }
    rcu_read_unlock();
}

// 写端删除
void delete_entry(struct my_struct *target)
{
    struct my_struct *old;
    
    // 1. 从链表移除
    list_del_rcu(&target->list);
    
    // 2. 等待宽限期
    synchronize_rcu();
    
    // 3. 释放
    kfree(target);
}

// 写端插入（头插）
void add_entry(struct my_struct *new)
{
    list_add_rcu(&new->list, &my_list);
}
```

## 五、RCU 与其他同步机制对比

| 机制 | 读开销 | 写开销 | 读端限制 | 典型场景 |
|------|--------|--------|----------|----------|
| 自旋锁 | 原子操作+缓存锁 | 同读 | 不能睡眠 | 短小临界区 |
| 读写锁 | 原子引用计数 | 原子操作 | 不能睡眠 | 读多写少 |
| 顺序锁 | 无锁（重试） | 无锁 | 可能重试 | 时间计数器 |
| **RCU** | **零开销** | 复制+延迟释放 | 不能睡眠 | **读极多的链表/哈希表** |
| SRCU | 零开销 | 更长的 GP | 可以睡眠 | 读端需睡眠 |

## 六、实际使用场景

### 1. 内核路由表

```c
// net/ipv4/fib_trie.c
struct fib_alias *fib_find_alias(struct hlist_head *head, ...)
{
    struct fib_alias *fa;
    
    hlist_for_each_entry_rcu(fa, head, fa_list) {
        // 无锁遍历路由表
    }
    return fa;
}

// 路由更新时
void fib_add_alias(struct fib_alias *new, ...)
{
    // 1. 分配新节点
    // 2. 插入到 trie
    // 3. synchronize_rcu() 或 call_rcu() 释放旧节点
}
```

### 2. 内核模块列表

```c
// kernel/module.c
struct module *find_module(const char *name)
{
    struct module *mod;
    
    list_for_each_entry_rcu(mod, &modules, list) {
        if (strcmp(mod->name, name) == 0)
            return mod;
    }
    return NULL;
}
```

## 七、调试与验证

```bash
# 查看 RCU 状态
cat /sys/kernel/debug/rcu/rcu_preempt/rcudata

# 查看宽限期信息
cat /sys/kernel/debug/rcu/rcu_preempt/rcugp

# 查看 RCU 回调队列长度
cat /sys/kernel/debug/rcu/rcu_preempt/rcu_callback

# 使用 RCU 调试配置
CONFIG_RCU_TRACE=y
CONFIG_PROVE_RCU=y
```

## 八、总结

| 概念 | 要点 |
|------|------|
| RCU 核心 | 读端无锁，写端复制+替换+延迟释放 |
| 宽限期 | 所有 CPU 至少一次上下文切换 |
| `rcu_dereference` | 读端获取指针，保证可见性 |
| `rcu_assign_pointer` | 写端发布指针，保证顺序 |
| `synchronize_rcu` | 同步等待宽限期完成 |
| `call_rcu` | 异步注册回调，宽限期后执行 |
| SRCU | 读端可睡眠的 RCU 变体 |

RCU 是 Linux 内核中读性能最高的同步机制，但使用限制（读端不能睡眠）使其适用范围有限。正确理解宽限期和 `rcu_dereference`/`rcu_assign_pointer` 的语义，是安全使用 RCU 的前提。
