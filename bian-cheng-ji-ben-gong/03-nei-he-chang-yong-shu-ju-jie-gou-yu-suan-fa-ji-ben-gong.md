# 03-内核常用数据结构与算法基本功

> 内核之所以高效，很大程度归功于它精心选择的数据结构：`list_head` 侵入式链表、`rbtree` 红黑树、`hashtable` 哈希表、`bitmap` 位图、`kfifo` 无锁队列等。本章用用户态最小实现，把它们的思想和操作练会。

## 3.1 侵入式单向/双向链表（`list_head` 思想）

普通链表节点存"数据 + 指针"；内核反过来——把"前后指针"作为一个小结构体内嵌到你的数据里，再用 `container_of` 找回数据（见 02 章）。好处是同一个节点可被挂到多条链表，且无需为每种数据类型重写链表。

```c
// 示例 1：用内嵌节点串起多个 task（双向链表骨架）
#include <stdio.h>
#include <stddef.h>

#define container_of(ptr, type, member) \
    ((type *)((char *)(ptr) - offsetof(type, member)))

struct list_head { struct list_head *next, *prev; };

struct task {
    int pid;
    struct list_head node;
};

int main(void) {
    struct task t1 = { .pid = 1 };
    struct task t2 = { .pid = 2 };
    // 手动串成 a<->b 的小环
    t1.node.next = &t2.node; t1.node.prev = &t2.node;
    t2.node.next = &t1.node; t2.node.prev = &t1.node;

    // 通过节点遍历，找回宿主
    struct list_head *p = &t1.node;
    do {
        struct task *t = container_of(p, struct task, node);
        printf("pid=%d\n", t->pid);
        p = p->next;
    } while (p != &t1.node);
    return 0;
}
```

**动手实验**：把上面的"双向环"改成内核风格的 `LIST_HEAD` 头节点 + `list_add`/`list_for_each` 辅助宏（参考 `include/linux/list.h`），体会头节点如何让"空链表"也保持一致。

## 3.2 位图（bitmap）：用 1 位表示一个状态

内核用 bitmap 管理"哪些页空闲""哪些 CPU 在线""哪些中断已注册"等。一个 `unsigned long` 数组即可表示成千上万个布尔状态，极其省内存。

```c
// 示例 2：最小 bitmap 实现
#include <stdio.h>
#include <stdlib.h>

typedef unsigned long *bitmap;
#define BITS_PER_LONG (sizeof(unsigned long) * 8)

static inline void set_bit(int nr, bitmap b) {
    b[nr / BITS_PER_LONG] |= (1UL << (nr % BITS_PER_LONG));
}
static inline void clear_bit(int nr, bitmap b) {
    b[nr / BITS_PER_LONG] &= ~(1UL << (nr % BITS_PER_LONG));
}
static inline int test_bit(int nr, bitmap b) {
    return !!(b[nr / BITS_PER_LONG] & (1UL << (nr % BITS_PER_LONG)));
}

int main(void) {
    bitmap b = calloc(1, sizeof(unsigned long)); // 64 位，足够本例
    set_bit(3, b); set_bit(7, b);
    printf("bit3=%d bit5=%d\n", test_bit(3, b), test_bit(5, b)); // 1 0
    clear_bit(3, b);
    printf("after clear, bit3=%d\n", test_bit(3, b));             // 0
    free(b);
    return 0;
}
```

**动手实验**：实现一个 `int find_first_zero(bitmap, nbits)`，返回第一个为 0 的位号——这正是内核页分配器"找空闲页"的核心循环。

## 3.3 哈希表：O(1) 查找的基石

内核用哈希表管理进程（`pidHash`）、网络套接字、inode 等。思想：用哈希函数把 key 映射到桶，冲突用链表串接。

```c
// 示例 3：极简哈希表（链地址法）
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BUCKETS 8
struct hent { char key[16]; int val; struct hent *next; };
struct hent *table[BUCKETS] = {0};

unsigned hash(const char *s) {
    unsigned h = 0;
    while (*s) h = (h * 31 + (unsigned char)*s++);
    return h % BUCKETS;
}
void put(const char *k, int v) {
    unsigned i = hash(k);
    for (struct hent *e = table[i]; e; e = e->next)
        if (!strcmp(e->key, k)) { e->val = v; return; }
    struct hent *n = malloc(sizeof *n);
    strcpy(n->key, k); n->val = v; n->next = table[i]; table[i] = n;
}
int get(const char *k) {
    for (struct hent *e = table[hash(k)]; e; e = e->next)
        if (!strcmp(e->key, k)) return e->val;
    return -1;
}
int main(void) {
    put("pid42", 100); put("tcp", 200);
    printf("pid42=%d tcp=%d missing=%d\n", get("pid42"), get("tcp"), get("x"));
    return 0;
}
```

**动手实验**：把桶数改成 1，观察退化成链表后的查找代价；再实现一个 `rehash`（扩容翻倍并重新散列），理解负载因子。

## 3.4 队列/环形缓冲（`kfifo` 思想）

生产者消费者场景（如中断上半部往队列塞数据、进程下半部取）常用无锁环形队列。

```c
// 示例 4：定长环形队列（单生产者单消费者）
#include <stdio.h>
#include <stddef.h>

#define CAP 8
int buf[CAP];
size_t head = 0, tail = 0;   // head=写位置, tail=读位置

int push(int v) {
    if ((head + 1) % CAP == tail) return -1; // 满
    buf[head] = v; head = (head + 1) % CAP; return 0;
}
int pop(int *v) {
    if (head == tail) return -1;              // 空
    *v = buf[tail]; tail = (tail + 1) % CAP; return 0;
}
int main(void) {
    for (int i = 0; i < 3; i++) push(i);
    int x; while (pop(&x) == 0) printf("pop %d\n", x);
    return 0;
}
```

## 3.5 自测题

1. 侵入式链表相比普通链表，最大的两个优点是什么？
2. 一个 `unsigned long` 在 64 位机上能表示多少个独立状态？要表示 1000 个状态最少需要多少个 `unsigned long`？
3. 哈希冲突不可避免，内核网络哈希表用什么方式解决冲突？
4. 环形队列"满"和"空"时 `head`/`tail` 都满足 `head==tail`，代码如何区分二者？

## 3.6 常见陷阱与调试

- **遍历时改链表**：内核规定某些遍历（如 `list_for_each`）不能在遍历中删除当前节点，否则 `next` 悬空；要用 `list_for_each_safe` 提前缓存下一节点。
- **bitmap 越界**：操作第 nr 位前务必 `nr < nbits`，否则会写到相邻 `unsigned long` 甚至越界。
- **哈希函数质量**：糟糕的哈希会让所有 key 落到同一桶，退化为 O(n)；内核多用"乘法散列 + 随机种子"抗碰撞。

---

> 下一章：[04-工具链与调试基本功](04-gong-ju-lian-yu-diao-shi-ji-ben-gong.md)
