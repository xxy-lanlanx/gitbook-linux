import os

root_dir = r"e:\doc\gitbook\gitbook-linux"
replacement_char = "\ufffd"
results = []

total_files = 0
total_occurrences = 0

for dirpath, dirnames, filenames in os.walk(root_dir):
    for fname in filenames:
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(dirpath, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        count = content.count(replacement_char)
        if count > 0:
            rel_path = os.path.relpath(fpath, root_dir)
            results.append((rel_path, count))
            total_files += 1
            total_occurrences += count

print(f"Total files with replacement char: {total_files}")
print(f"Total occurrences: {total_occurrences}")
print()
for rel_path, count in results:
    print(f"{count:5d}  {rel_path}")
