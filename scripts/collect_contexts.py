import os
import re
from collections import defaultdict

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

context_map = defaultdict(int)

for rel_path in files:
    fpath = os.path.join(root_dir, rel_path)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    for m in re.finditer(r'[\ufffd]', content):
        start = max(0, m.start() - 3)
        end = min(len(content), m.end() + 3)
        prefix = content[start:m.start()]
        suffix = content[m.end():end]
        key = prefix + "[R]" + suffix
        context_map[key] += 1

output_path = os.path.join(root_dir, "scripts", "replacement_contexts.txt")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(f"Total unique contexts: {len(context_map)}\n\n")
    for key, count in sorted(context_map.items(), key=lambda x: -x[1]):
        f.write(f"{count:4d}  {key}\n")

print(f"Total unique contexts: {len(context_map)}")
