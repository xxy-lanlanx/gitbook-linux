import re

files = [
    r"e:\doc\gitbook\gitbook-linux\linux-cao-zuo-xi-tong-ji-ben-yuan-li\02linux-kernel-nei-he-zheng-ti-jia-gou.md",
    r"e:\doc\gitbook\gitbook-linux\linux-cao-zuo-xi-tong-ji-ben-yuan-li\05linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li.md",
    r"e:\doc\gitbook\gitbook-linux\linux-cao-zuo-xi-tong-ji-ben-yuan-li\06linux-cao-zuo-xi-tong-chu-li-qi-diao-du-ji-ben-zhun-ze-he-shi-xian.md",
    r"e:\doc\gitbook\gitbook-linux\linux-cao-zuo-xi-tong-ji-ben-yuan-li\07linux-nei-he-cao-zuo-xi-tong-yuan-li-yu-gai-shu.md",
    r"e:\doc\gitbook\gitbook-linux\linux-cao-zuo-xi-tong-ji-ben-yuan-li\11linux-cao-zuo-xi-tong-li-jie-cpu-shang-xia-wen-qie-huan.md",
]

def resolve_conflicts(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 匹配冲突块: <<<<<<< HEAD ... ======= ... >>>>>>> hash
    pattern = r'<<<<<<< HEAD\r?\n(.*?)=======\r?\n(.*?)(?:\r?\n)?>>>>>>> [0-9a-f]+\r?\n'
    
    def replace(match):
        remote = match.group(2)
        # 保留远端版本，确保以换行结尾
        if not remote.endswith('\n'):
            remote += '\n'
        return remote
    
    new_content = re.sub(pattern, replace, content, flags=re.DOTALL)
    
    remaining = False
    if '<<<<<<< HEAD' in new_content:
        print(f"WARNING: '<<<<<<< HEAD' remaining in {filepath}")
        remaining = True
    if '>>>>>>> ' in new_content:
        print(f"WARNING: '>>>>>>> ' remaining in {filepath}")
        remaining = True
    if not remaining:
        print(f"Resolved: {filepath}")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

for f in files:
    resolve_conflicts(f)
