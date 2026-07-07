import os

files = [
    r"e:\doc\gitbook\gitbook-linux\linux-jin-cheng-guan-li\01linux-jin-cheng-he-xian-cheng.md",
    r"e:\doc\gitbook\gitbook-linux\linux-cao-zuo-xi-tong-ji-ben-yuan-li\11linux-cao-zuo-xi-tong-li-jie-cpu-shang-xia-wen-qie-huan.md",
    r"e:\doc\gitbook\gitbook-linux\linux-cao-zuo-xi-tong-ji-ben-yuan-li\07linux-nei-he-cao-zuo-xi-tong-yuan-li-yu-gai-shu.md",
    r"e:\doc\gitbook\gitbook-linux\linux-cao-zuo-xi-tong-ji-ben-yuan-li\06linux-cao-zuo-xi-tong-chu-li-qi-diao-du-ji-ben-zhun-ze-he-shi-xian.md",
    r"e:\doc\gitbook\gitbook-linux\linux-cao-zuo-xi-tong-ji-ben-yuan-li\05linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li.md",
    r"e:\doc\gitbook\gitbook-linux\linux-cao-zuo-xi-tong-ji-ben-yuan-li\04linux-cao-zuo-xi-tong-xue-xi-nei-he-chu-shi-hua.md",
    r"e:\doc\gitbook\gitbook-linux\linux-cao-zuo-xi-tong-ji-ben-yuan-li\03linux-cao-zuo-xi-tong-xue-xi-qi-dong.md",
    r"e:\doc\gitbook\gitbook-linux\linux-cao-zuo-xi-tong-ji-ben-yuan-li\02linux-kernel-nei-he-zheng-ti-jia-gou.md",
]

for filepath in files:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        cut_index = None
        for i, line in enumerate(lines):
            if line.strip() == "## 编程基本功实践":
                cut_index = i
                break
        
        if cut_index is not None:
            # 删除该行及之后的所有内容
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(lines[:cut_index])
            print(f"[OK] {filepath}")
        else:
            print(f"[SKIP] {filepath}")
    except Exception as e:
        print(f"[ERR] {filepath}: {e}")
