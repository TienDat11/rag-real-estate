
import os, re, sys
root = r"D:\rag-real-estate\.venv\Lib\site-packages\lightrag"
patterns = ["Query nodes", "Local query", "query_entities_from_keywords", "extract_query_entities", "top_k"]
for dirpath, dirnames, filenames in os.walk(root):
    for fn in filenames:
        if not fn.endswith(".py"):
            continue
        path = os.path.join(dirpath, fn)
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    for pat in patterns:
                        if pat in line:
                            rel = os.path.relpath(path, root)
                            print(f"{rel}:{i}: {line.rstrip()[:160]}")
        except OSError:
            pass
