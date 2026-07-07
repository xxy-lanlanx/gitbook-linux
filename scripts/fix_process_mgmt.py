import os
import re

base_dir = r"e:\doc\gitbook\gitbook-linux\linux-jin-cheng-guan-li"
summary_path = r"e:\doc\gitbook\gitbook-linux\SUMMARY.md"

# Mapping: old_number -> new_number
renames = {
    "03": "02",
    "04": "03",
    "05": "04",
    "06": "05",
    "07": "06",
}

# 1. Rename files
for old_num, new_num in renames.items():
    for fname in os.listdir(base_dir):
        if fname.startswith(old_num):
            new_name = fname.replace(old_num, new_num, 1)
            old_path = os.path.join(base_dir, fname)
            new_path = os.path.join(base_dir, new_name)
            os.rename(old_path, new_path)
            print(f"Renamed: {fname} -> {new_name}")
            break

# 2. Update first line title in each file
for new_num, old_num in [(v, k) for k, v in renames.items()]:
    for fname in os.listdir(base_dir):
        if fname.startswith(new_num):
            fpath = os.path.join(base_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            # Replace first line title number
            content = re.sub(rf"^# {old_num}-", f"# {new_num}-", content, count=1)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Updated title in: {fname}")
            break

# 3. Update SUMMARY.md
with open(summary_path, "r", encoding="utf-8") as f:
    summary = f.read()

for old_num, new_num in renames.items():
    summary = summary.replace(
        f"linux-jin-cheng-guan-li/{old_num}",
        f"linux-jin-cheng-guan-li/{new_num}"
    )
    # Also update the link text number if present
    summary = re.sub(
        rf"(\[){old_num}(-Linux.*?\]\(linux-jin-cheng-guan-li/{new_num})",
        rf"\1{new_num}\2",
        summary
    )

with open(summary_path, "w", encoding="utf-8") as f:
    f.write(summary)

print("Updated SUMMARY.md")
