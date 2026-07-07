import re

files = [
    r"e:\doc\gitbook\gitbook-linux\linux-cao-zuo-xi-tong-ji-ben-yuan-li\02linux-kernel-nei-he-zheng-ti-jia-gou.md",
    r"e:\doc\gitbook\gitbook-linux\linux-cao-zuo-xi-tong-ji-ben-yuan-li\06linux-cao-zuo-xi-tong-io-ji-zhi-yuan-li.md",
    r"e:\doc\gitbook\gitbook-linux\linux-cao-zuo-xi-tong-ji-ben-yuan-li\07linux-cao-zuo-xi-tong-chu-li-qi-diao-du-ji-ben-zhun-ze-he-shi-xian.md",
    r"e:\doc\gitbook\gitbook-linux\linux-cao-zuo-xi-tong-ji-ben-yuan-li\08linux-nei-he-cao-zuo-xi-tong-yuan-li-yu-gai-shu.md",
    r"e:\doc\gitbook\gitbook-linux\linux-cao-zuo-xi-tong-ji-ben-yuan-li\12linux-cao-zuo-xi-tong-li-jie-cpu-shang-xia-wen-qie-huan.md",
]

def clean_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Step 1: Remove standard git conflict blocks with optional path suffix
    pattern1 = r'<<<<<<< HEAD(?::[^\n]*)?\r?\n(.*?)=======\r?\n(.*?)(?:\r?\n)?>>>>>>> [0-9a-f]+(?::[^\r\n]*)?\r?\n'
    content = re.sub(pattern1, lambda m: m.group(2) + '\n' if not m.group(2).endswith('\n') else m.group(2), content, flags=re.DOTALL)
    
    # Step 2: Remove orphaned ======= lines followed by >>>>>>>
    pattern2 = r'=======\r?\n(.*?)(?:\r?\n)?>>>>>>> [0-9a-f]+(?::[^\r\n]*)?\r?\n'
    content = re.sub(pattern2, lambda m: m.group(1) + '\n' if not m.group(1).endswith('\n') else m.group(1), content, flags=re.DOTALL)
    
    # Step 3: Remove escaped \======= inline
    content = re.sub(r'\\=======\s*', '', content)
    
    # Step 4: Remove escaped arrow lines
    content = re.sub(r'\r?\n\s*< < < < < < < .*\r?\n', '\n', content)
    content = re.sub(r'\r?\n\s*> > > > > > > .*\r?\n', '\n', content)
    
    # Step 5: Remove remaining orphaned >>>>>>> lines
    content = re.sub(r'\r?\n>>>>>>> [0-9a-f]+(?:\S*)?\r?\n', '\n', content)
    content = re.sub(r'^>>>>>>> [0-9a-f]+(?:\S*)?\r?\n', '', content)
    
    # Step 6: Clean up excessive blank lines
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    if content != original:
        print(f"Cleaned: {filepath}")
    
    # Check remaining markers
    if '<<<<<<<' in content:
        print(f"WARNING: Still has <<<<<<< in {filepath}")
    else:
        print(f"OK: {filepath}")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for f in files:
    clean_file(f)
