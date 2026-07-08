import os
import chardet

root_dir = r"e:\doc\gitbook\gitbook-linux"
replacement_char = "\ufffd"

files_to_fix = []

for dirpath, dirnames, filenames in os.walk(root_dir):
    for fname in filenames:
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(dirpath, fname)
        with open(fpath, "rb") as f:
            raw = f.read()
        if replacement_char.encode("utf-8") in raw:
            files_to_fix.append(fpath)

for fpath in files_to_fix:
    with open(fpath, "rb") as f:
        raw = f.read()
    detected = chardet.detect(raw)
    encoding = detected.get("encoding", "utf-8")
    confidence = detected.get("confidence", 0)
    print(f"{os.path.relpath(fpath, root_dir)}: encoding={encoding}, confidence={confidence:.2f}")

    # Try decode with detected encoding, fallback to gbk, then utf-8
    try:
        text = raw.decode(encoding or "utf-8")
    except Exception:
        try:
            text = raw.decode("gbk")
        except Exception:
            text = raw.decode("utf-8", errors="replace")
    
    # Save as UTF-8
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(text)
    
    # Verify
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    remaining = content.count(replacement_char)
    print(f"  -> remaining replacements: {remaining}")
