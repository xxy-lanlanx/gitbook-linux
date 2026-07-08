import os
import re

root_dir = r"e:\doc\gitbook\gitbook-linux"
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

for rel_path in files:
    fpath = os.path.join(root_dir, rel_path)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find all contexts around replacement chars
    contexts = []
    for m in re.finditer(r'[\ufffd]', content):
        start = max(0, m.start() - 5)
        end = min(len(content), m.end() + 5)
        contexts.append(content[start:end])
    
    print(f"\n{rel_path}: {len(contexts)} occurrences")
    # Show unique contexts (first 20)
    unique = list(dict.fromkeys(contexts))[:20]
    for ctx in unique:
        print(f"  {ctx.replace(chr(0xfffd), '[R]')}")

