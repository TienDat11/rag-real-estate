
import os
root = r"D:\rag-real-estate\.venv\Lib\site-packages\lightrag"
targets = [
  ("operate.py", "async def _build_query_context"),
  ("operate.py", "async def _extract_keywords"),
  ("operate.py", "def _extract_keywords"),
  ("operate.py", "llm_func"),
  ("operate.py", "use_llm_func"),
]
for fn, pat in targets:
    path = os.path.join(root, fn)
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                if pat in line:
                    print(f"{fn}:{i}: {line.rstrip()[:180]}")
    except OSError as e:
        print(f"{fn}: ERR {e}")
