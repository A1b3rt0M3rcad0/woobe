import os

src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
updated = 0

for root, dirs, files in os.walk(src_dir):
    for fname in files:
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(root, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        orig = content

        content = content.replace(".metadata", ".data")
        content = content.replace("metadata=", "data=")
        content = content.replace('"metadata"', '"data"')
        content = content.replace("'metadata'", "'data'")

        lines = content.split("\n")
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if "metadata:" in stripped and "Mapped" in stripped:
                line = line.replace("metadata:", "data:", 1)
            new_lines.append(line)
        content = "\n".join(new_lines)

        if content != orig:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
            updated += 1
            print(f"Updated: {os.path.relpath(fpath, src_dir)}")

print(f"Total files updated: {updated}")
