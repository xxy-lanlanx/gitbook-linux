import shutil
import os

base = r"e:\doc\gitbook\gitbook-linux\linux-cao-zuo-xi-tong-ji-ben-yuan-li"

# Delete corrupted files
for f in ["06linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li.md", "07linux-cao-zuo-xi-tong-chu-li-qi-diao-du-ji-ben-zhun-ze-he-shi-xian.md", "08linux-nei-he-cao-zuo-xi-tong-yuan-li-yu-gai-shu.md", "12linux-cao-zuo-xi-tong-li-jie-cpu-shang-xia-wen-qie-huan.md"]:
    path = os.path.join(base, f)
    if os.path.exists(path):
        os.remove(path)
        print(f"Deleted: {f}")
    else:
        print(f"Not found: {f}")

# Copy clean old files to new names
copies = [
    ("05linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li.md", "06linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li.md"),
    ("06linux-cao-zuo-xi-tong-chu-li-qi-diao-du-ji-ben-zhun-ze-he-shi-xian.md", "07linux-cao-zuo-xi-tong-chu-li-qi-diao-du-ji-ben-zhun-ze-he-shi-xian.md"),
    ("07linux-nei-he-cao-zuo-xi-tong-yuan-li-yu-gai-shu.md", "08linux-nei-he-cao-zuo-xi-tong-yuan-li-yu-gai-shu.md"),
    ("11linux-cao-zuo-xi-tong-li-jie-cpu-shang-xia-wen-qie-huan.md", "12linux-cao-zuo-xi-tong-li-jie-cpu-shang-xia-wen-qie-huan.md"),
]

for old, new in copies:
    old_path = os.path.join(base, old)
    new_path = os.path.join(base, new)
    if os.path.exists(old_path):
        shutil.copy2(old_path, new_path)
        print(f"Copied: {old} -> {new}")
    else:
        print(f"Not found: {old}")

# Delete old files
for f in ["05linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li.md", "06linux-cao-zuo-xi-tong-chu-li-qi-diao-du-ji-ben-zhun-ze-he-shi-xian.md", "07linux-nei-he-cao-zuo-xi-tong-yuan-li-yu-gai-shu.md", "11linux-cao-zuo-xi-tong-li-jie-cpu-shang-xia-wen-qie-huan.md"]:
    path = os.path.join(base, f)
    if os.path.exists(path):
        os.remove(path)
        print(f"Deleted old: {f}")
    else:
        print(f"Not found old: {f}")

print("Done")
