import os

base_dir = r"e:\doc\gitbook\gitbook-linux\linux-cao-zuo-xi-tong-ji-ben-yuan-li"

# 从大到小重命名，避免覆盖
renames = [
    ("12linux-nei-he-diao-shi-yu-xing-neng-fen-xi.md", "13linux-nei-he-diao-shi-yu-xing-neng-fen-xi.md"),
    ("11linux-cao-zuo-xi-tong-li-jie-cpu-shang-xia-wen-qie-huan.md", "12linux-cao-zuo-xi-tong-li-jie-cpu-shang-xia-wen-qie-huan.md"),
    ("10linux-nei-he-shi-jian-guan-li-yu-ding-shi-qi.md", "11linux-nei-he-shi-jian-guan-li-yu-ding-shi-qi.md"),
    ("09linux-zhong-duan-yu-yi-chang-chu-li-ji-zhi.md", "10linux-zhong-duan-yu-yi-chang-chu-li-ji-zhi.md"),
    ("08linux-xi-tong-diao-yong-yuan-li-yu-shi-xian.md", "09linux-xi-tong-diao-yong-yuan-li-yu-shi-xian.md"),
    ("07linux-nei-he-cao-zuo-xi-tong-yuan-li-yu-gai-shu.md", "08linux-nei-he-cao-zuo-xi-tong-yuan-li-yu-gai-shu.md"),
    ("06linux-cao-zuo-xi-tong-chu-li-qi-diao-du-ji-ben-zhun-ze-he-shi-xian.md", "07linux-cao-zuo-xi-tong-chu-li-qi-diao-du-ji-ben-zhun-ze-he-shi-xian.md"),
    ("05linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li.md", "06linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li.md"),
]

for old, new in renames:
    old_path = os.path.join(base_dir, old)
    new_path = os.path.join(base_dir, new)
    if os.path.exists(old_path):
        os.rename(old_path, new_path)
        print(f"Renamed: {old} -> {new}")
    else:
        print(f"SKIP (not found): {old}")

# 移动 IO 基础文件到正确位置
src = r"e:\doc\gitbook\gitbook-linux\linux-jin-cheng-guan-li\02linux-nei-he-io-ji-chu-zhi-shi-yu-gai-nian.md"
dst = os.path.join(base_dir, "05linux-nei-he-io-ji-chu-zhi-shi-yu-gai-nian.md")
if os.path.exists(src):
    os.rename(src, dst)
    print(f"Moved: 02linux-nei-he-io-ji-chu-zhi-shi-yu-gai-nian.md -> 05linux-nei-he-io-ji-chu-zhi-shi-yu-gai-nian.md")
else:
    print(f"SKIP (not found): {src}")
