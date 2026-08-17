
import os
root = r"D:\rag-real-estate\.venv\Lib\site-packages\lightrag"
path = os.path.join(root, "operate.py")
with open(path, encoding="utf-8", errors="replace") as f:
    lines = f.readlines()
# find 'async def get_keywords_from_query'
for i, line in enumerate(lines):
    if "def get_keywords_from_query" in line:
        start = i
        break
print("".join(lines[start-5:start+60]))
