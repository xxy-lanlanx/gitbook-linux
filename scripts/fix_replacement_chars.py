import os, re

root = r"e:\doc\gitbook\gitbook-linux"
files = [
    "linux-cao-zuo-xi-tong-ji-ben-yuan-li/05linux-nei-he-io-ji-chu-zhi-shi-yu-gai-nian.md",
    "linux-cao-zuo-xi-tong-ji-ben-yuan-li/06linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li.md",
    "linux-cao-zuo-xi-tong-ji-ben-yuan-li/07linux-cao-zuo-xi-tong-chu-li-qi-diao-du-ji-ben-zhun-ze-he-shi-xian.md",
    "linux-cao-zuo-xi-tong-ji-ben-yuan-li/08linux-nei-he-cao-zuo-xi-tong-yuan-li-yu-gai-shu.md",
    "linux-cao-zuo-xi-tong-ji-ben-yuan-li/12linux-cao-zuo-xi-tong-li-jie-cpu-shang-xia-wen-qie-huan.md",
    "linux-jin-cheng-guan-li/02linux-nei-he-liu-da-jin-cheng-tong-xin-ji-zhi-yuan-li.md",
    "linux-jin-cheng-guan-li/03linux-nei-he-socket-tong-xin-yuan-li.md",
    "linux-jin-cheng-guan-li/04linux-nei-he-jin-cheng-de-guan-li-yu-diao-du.md",
    "linux-jin-cheng-guan-li/05linux-nei-he-jin-cheng-guan-li-bing-fa-tong-bu-yu-yuan-zi-cao-zuo.md",
]

r = chr(0xfffd)

def fix(text):
    text = text.replace(f'操{r}', '操作')
    text = text.replace(f'空{r}', '空间')
    text = text.replace(f'地{r}', '地方')
    text = text.replace(f'内存映{r}', '内存映射')
    text = text.replace(f'从磁盘{r}', '从磁盘到')
    text = text.replace(f'缓冲区{r}用户', '缓冲区到用户')
    text = text.replace(f'程序调{r}', '程序调用')
    text = text.replace(f'"消费{r}生产', '"消费与生产')
    text = text.replace(f'0% {r}CP', '0% 的CPU')
    text = text.replace(f'户空间{r}', '户空间）')
    text = text.replace(f'的进程{r}', '的进程。')
    text = text.replace(f'缓冲区{r}', '缓冲区。')
    text = text.replace(f'序使用{r}', '序使用。')
    text = text.replace(f'送出去{r}', '送出去。')
    text = text.replace(f'的任务{r}', '的任务。')
    text = text.replace(f'本声明{r}', '本声明。')
    text = text.replace(f'的过程{r}', '的过程。')
    text = text.replace(f'输方式{r}', '输方式。')
    text = text.replace(f'塞状态{r}', '塞状态。')
    text = text.replace(f'给磁盘{r}', '给磁盘。')
    text = text.replace(f'区已满{r}', '区已满。')
    text = text.replace(f'求为止{r}', '求为止。')
    text = text.replace(f'O请求{r}', 'O请求。')
    text = re.sub(rf'([a-zA-Z]+){r}\*', r'\1）**', text)
    text = re.sub(rf'([a-zA-Z]+){r}\)', r'\1）', text)
    text = re.sub(rf'([a-zA-Z]+){r},', r'\1），', text)
    text = re.sub(rf'([a-zA-Z]+){r}\s*', r'\1）', text)
    text = re.sub(rf'理解{r}\*', '理解）**', text)
    text = re.sub(rf'模型{r}\*', '模型）**', text)
    text = re.sub(rf'划分{r}\*', '划分）**', text)
    for w in '理解 模型 划分 规则 使用 执行 空间 出去 运行 指令 过程 了 呢 间 程 块 围 式 能 况 系 备 度 构 器 数 容 面 内 外 上 下 左 右 中 前 后 大 小 多 少 好 坏 高 低 长 短 新 旧 难 易 快 慢 早 晚 先 后 主 次 重 轻 深 浅 宽 窄 厚 薄 强 弱 硬 软 干 湿 冷 热 酸 甜 苦 辣 咸 淡 香 臭 明 暗 亮 黑 白 红 黄 蓝 绿 紫 灰 青 粉 棕 橙 金 银 铜 铁 木 水 火 土 风 雨 雪 霜 雾 雷 电 云 气 光 声 色 味 声 音 乐 歌 舞 画 书 诗 文 字 词 句 段 篇 章 节 页 行 列 表 图 像 影 视 听 说 读 写 想 看 见 听 闻 摸 尝 做 干 活 动 静 动 变 化 改 革 新 旧 老 少 男 女 父 母 子 女 兄 弟 姐 妹 夫 妻 儿 孙 老 师 生 友 客 人 民 国 家 党 政 府 军 队 官 兵 警 察 法 律 规 章 制 度 则 范 标 准 则 原 理 论 说 法 观 点 意 见 建 议 想 法 主 义 思 路 方 法 式 样 类 种 型 类 别 级 等 层 面 方 向 位 置 点 处 所 地 区 域 范 围 边 缘 界 线 面 体 形 状 态 势 式 样 貌 相 象'.split():
        text = re.sub(rf'{w}{r}(?=[\n\s，])', f'{w}。', text)
    return text

results = []
for rel in files:
    fp = os.path.join(root, rel)
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    before = content.count(r)
    fixed = fix(content)
    after = fixed.count(r)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(fixed)
    results.append(f'{rel}: {before} -> {after}')

with open(os.path.join(root, 'scripts', 'fix_results.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(results))
    f.write(f'\nTotal: {sum(int(r.split("->")[0].strip()) for r in results)} -> {sum(int(r.split("->")[1].strip()) for r in results)}\n')
