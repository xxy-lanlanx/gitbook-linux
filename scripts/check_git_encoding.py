import os
import subprocess
import chardet

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
    # Get raw bytes from git HEAD
    result = subprocess.run(
        ["git", "show", f"HEAD:{rel_path}"],
        cwd=root_dir,
        capture_output=True,
    )
    raw = result.stdout
    detected = chardet.detect(raw)
    encoding = detected.get("encoding", "utf-8")
    confidence = detected.get("confidence", 0)
    
    # Check for replacement char in current file
    with open(fpath, "r", encoding="utf-8") as f:
        current_content = f.read()
    current_count = current_content.count("\ufffd")
    
    print(f"{rel_path}: git encoding={encoding} (conf={confidence:.2f}), current replacements={current_count}")
    
    # Try decode git version with detected encoding
    try:
        git_text = raw.decode(encoding or "utf-8")
        git_replacements = git_text.count("\ufffd")
        print(f"  -> git version replacements={git_replacements}")
    except Exception as e:
        print(f"  -> failed to decode with {encoding}: {e}")
        try:
            git_text = raw.decode("gbk")
            git_replacements = git_text.count("\ufffd")
            print(f"  -> gbk decode replacements={git_replacements}")
        except Exception as e2:
            print(f"  -> gbk also failed: {e2}")
