# Library Research — RAG pháp lý bất động sản (verify 2026-08-09)

> Verify các quyết định kỹ thuật trong ADR-001 (`.claude/CLAUDE.md`) trước khi implement.
> Nguồn: PyPI, GitHub source `HKUDS/LightRAG@main` (raw fetch), HuggingFace, EMNLP 2025 paper, benchmark graphrag-lab 2026-03, aibox API docs.
> Người soạn: subagent research 2026-08-09.

---

## 1. LightRAG — pin version

**Verdict: GIỮ (pin v1.5.x).** API ổn định cho mọi nhu cầu của MVP: PG single-backend, incremental update, dual retrieval.

### Bằng chứng
- **Latest version**: `lightrag-hku` **v1.5.6** — released 2026-08-06 trên PyPI (tag `v1.5.6`). Yêu cầu **Python >=3.10**.
  - Link: https://pypi.org/project/lightrag-hku/
- **Dependencies chính** (từ `pyproject.toml` @main): `networkx` (core), `tiktoken>=0.7.0`, `numpy>=1.24,<3`, `pandas>=2.0,<2.4`, `pydantic`, `aiohttp`, `tenacity`, `json_repair>=0.59.9`, `pypinyin`, `nano-vectordb`, `PyYAML`, `xlsxwriter`, `google-genai`.
  - **transformers KHÔNG phải core dep** — chỉ cần khi dùng local/offline embedding model (extra `offline-llm`). Embedding aibox = HTTP nên không cần transformers.
- **Storage backends** (từ `lightrag/kg/__init__.py` STORAGE_IMPLEMENTATIONS):
  - KV: `JsonKVStorage`, `RedisKVStorage`, `PGKVStorage`, `MongoKVStorage`, `OpenSearchKVStorage`
  - GRAPH: `NetworkXStorage`, `Neo4JStorage`, `PGGraphStorage`, `PGTableGraphStorage`, `MongoGraphStorage`, `MemgraphStorage`, `OpenSearchGraphStorage`
  - VECTOR: `NanoVectorDBStorage`, `MilvusVectorDBStorage`, `PGVectorStorage`, `FaissVectorDBStorage`, `QdrantVectorDBStorage`, `MongoVectorDBStorage`, `OpenSearchVectorDBStorage`
  - DOC_STATUS: `JsonDocStatusStorage`, `PGDocStatusStorage`, ...
- **PG single-backend**: cả 4 loại storage trong **một file** `lightrag/kg/postgres_impl.py` (~9.4k dòng): `PGKVStorage`, `PGVectorStorage`, `PGGraphStorage`, `PGDocStatusStorage` — đúng thiết kế "1 service PostgreSQL". `PGVectorStorage` yêu cầu **pgvector extension** (tự `CREATE EXTENSION IF NOT EXISTS vector`, hỗ trợ HNSW + ivfflat, HNSW_HALFVC cần pgvector>=0.7.0).
- **Incremental update**: `merge_nodes_and_edges()` → `_merge_nodes_then_upsert()` / `_merge_edges_then_upsert()` trong `lightrag/operate.py` — entity/edge đã tồn tại thì **merge data** (gộp description + `merge_source_ids`), chưa tồn tại thì tạo mới. **KHÔNG rebuild graph.** PyPI feature list xác nhận: "Incremental Updates & Selective Deletion" (xóa doc = rebuild lại entity/relation bị ảnh hưởng từ LLM cache).
- **Query API**: `query()` / `aquery()` / `query_data()` / `aquery_data()` / `aquery_llm()` — trả luôn structured retrieval (entities/relations/chunks) để tính confidence + citation. `QueryParam.mode` hỗ trợ `local/global/hybrid/naive/mix/bypass` (default **mix**). Có sẵn `include_references` (citation) và `enable_rerank` (mặc định true).

### Rủi ro
- LightRAG phát hành rất nhanh (v1.5.x liên tục). **Pin version cụ thể** (vd `lightrag-hku==1.5.6`) trong requirements + golden-set regression mỗi lần upgrade (đã có trong plan).
- Storage env vars: PG cần `POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DATABASE` — thêm vào danh sách secrets bắt buộc.

### Khuyến nghị MVP
- Pin `lightrag-hku==1.5.6`, cấu hình `LLM_BINDING=openai` (aibox) + `EMBEDDING_BINDING=openai` + `RERANK_BINDING=openai` style, storage = PG single-backend.
- Lock `dimensions` của embedding tại lần ghi đầu (schema vector khóa cứng).

---

## 2. Graph engine — NetworkX vs python-igraph vs Neo4j

**Verdict: GIỮ (NetworkX cho dev) NHƯNG cần benchmark gate — và lưu ý quan trọng: production dùng PGGraphStorage (SQL), KHÔNG chạy NetworkX.**

### Bằng chứng
- **NetworkX là default**: `lightrag/kg/networkx_impl.py` — `class NetworkXStorage(BaseGraphStorage)` dùng `nx.Graph` in-memory. Verify bằng grep: `import networkx as nx` (line 10), dump graph bằng `nx.node_link_data` / load `nx.node_link_graph`.
- **Giới hạn cố hữu** (docstring trong networkx_impl.py): graph nằm hoàn toàn trong RAM 1 process; **single-writer invariant** (1 writer/lock, không shared memory, không message bus); thay đổi chỉ in-memory, cross-process visibility yêu cầu commit/tải lại file.
- **Quan trọng**: `PGGraphStorage` (production path của MVP) **KHÔNG dùng NetworkX** — grep `networkx` trong `pg.py` = **0 kết quả**. PGGraphStorage thực thi graph ops bằng SQL/Cypher-style queries trực tiếp trên PostgreSQL (batch upsert/delete, advisory lock). → Điểm yếu NetworkX **không áp dụng** cho production PG.
- **Scale NetworkX**: paper LightRAG (EMNLP 2025) corpus ~300k token → storage 39.5MB, graph hoạt động tốt. NetworkX xử lý hết 10k-100k entity của MVP legal (vài trăm MB RAM).
- **Benchmark gate** (giữ nguyên quyết định cũ): chuyển sang Neo4j/Memgraph khi ingest thật **>10k docs** hoặc **>50k entity**, hoặc query latency vượt ngưỡng SLO. python-igraph/cuGraph = phải fork LightRAG storage → **không đáng** cho MVP.

### Rủi ro
- Nếu MVP vô tình dùng `NetworkXStorage` (default) trong production → gặp single-writer + in-memory + dump file. **Bắt buộc config storage trace tới PG** khi deploy.
- PGGraphStorage chưa có benchmark công bố về hiệu năng ở scale lớn — cần đo lúc implement (đã có mục này trong plan).

### Khuyến nghị MVP
- Dev/POC: NetworkXStorage (0 cấu hình). Production: **PGGraphStorage** (SQL on PG) — 1 service, không NetworkX.
- Ghi benchmark gate vào task node: đo #entity, query latency, ingest latency khi chạy golden set đầu tiên.

---

## 3. Embedding — aibox text-embedding-v4 (fallback Qwen3-Embedding-0.6B)

**Verdict: GIỮ (LOCK).** Model tồn tại, OpenAI-compatible, VN supported. Fallback local hợp lệ.

### Bằng chứng
- **aibox text-embedding-v4** (qua api-box proxy):
  - Endpoint: `POST /v1/embeddings`, body `{"model":"text-embedding-v4","input":"..."}` — OpenAI SDK compatible.
  - **Dimensions**: cấu hình được **64→2048** qua param `dimensions`; **default 1024**, khuyến nghị 1536 cho high-precision. → **Bắt buộc lock dims ở lần ghi đầu** (schema vector).
  - Context: **8,192 tokens**; batch: 10 texts/request; 100+ languages (VN có).
  - **Giá**: ~**$0.0007 / 1M tokens** (aibox claim 70% off so với giá gốc).
  - ⚠️ **Discrepancy base URL**: skill ghi `api-box.vn`, docs aibox ghi `api.ai-box.vn` — **cần verify runtime** bằng curl trước khi fix config.
- **Fallback Qwen3-Embedding-0.6B** (HuggingFace `Qwen/Qwen3-Embedding-0.6B`):
  - 0.6B params, 28 layers, **context 32K**, **dims 1024** (MRL 32-1024), instruction-aware, 100+ languages.
  - Hỗ trợ chạy bằng **transformers** (official README) + **sentence-transformers** + FlagEmbedding. Chạy được qua Ollama (`qwen3-embedding` role).
  - Recommendation official: dense top-100 → rerank (khớp pipeline LightRAG).

### Rủi ro
- **Đổi model = re-embed toàn bộ** — đã LOCK, không đổi. Nhưng dims aibox có thể chọn 1024 vs 1536: **chọn 1 giá trị ngay từ đầu**, không đổi giữa chừng.
- Base URL chưa xác nhận chính xác (api-box.vn vs api.ai-box.vn).
- Fallback Qwen3-Embedding-0.6B dims = 1024 → nếu aibox dims chọn 1536, fallback sẽ **khác dims** → phải chọn dims ≤1024 (khớp fallback) hoặc chấp nhận re-embed khi fallback.

### Khuyến nghị MVP
- Chọn **dims = 1024** (default) cho cả aibox lẫn fallback Qwen3-Embedding-0.6B → vector schema thống nhất, fallback không cần re-embed.
- Verify base URL + dims thực bằng 1 curl trước khi fix embedding schema.

---

## 4. Rerank — aibox qwen3-rerank (fallback bge-reranker-v2-m3)

**Verdict: GIỮ.** API shape đã verify, tích hợp được thẳng vào LightRAG.

### Bằng chứng
- **aibox qwen3-rerank**: `POST /v1/rerank` — **Jina/Cohere-compatible**:
  - Request: `{model:"qwen3-rerank", query, documents[], top_n?, return_documents?, instruct?}`
  - Response: `results[] = {index, relevance_score}` (0-1), `usage.total_tokens`
  - Giới hạn: max 500 documents/request, 4,000 tokens/doc, 120k total input.
- **LightRAG tích hợp sẵn**: `lightrag/rerank.py` có `generic_rerank_api(query, documents, model, base_url, api_key, ..., response_format="standard"|"aliyun")` — format "standard" (Jina/Cohere) **khớp chuẩn aibox**. Có cả `ali_rerank` (DashScope format). Gắn qua `LightRAG(..., rerank_model_func=partial(generic_rerank_api, model="qwen3-rerank", base_url="<aibox>/v1/rerank", ...))`.
- **Fallback bge-reranker-v2-m3** (HuggingFace `BAAI/bge-reranker-v2-m3`): base bge-m3, **multilingual**, max length **8192** (khuyến nghị 1024 do fine-tune). Chạy bằng `FlagReranker` (FlagEmbedding) hoặc transformers `AutoModelForSequenceClassification`. Prompt: "Given a query A and a passage B, determine whether the passage contains an answer..."
- LightRAG QueryParam có sẵn `enable_rerank` (default true) + `min_rerank_score` (lọc sau rerank) — dùng cho confidence tier.

### Rủi ro
- aibox rerank response "standard" format cần **smoke test** 1 lần (đúng `results[].relevance_score`); nếu aibox trả "aliyun" format thì đổi `response_format="aliyun"`.
- bge-reranker-v2-m3 recommend max_length=1024 — chunk dài pháp lý cần cắt.

### Khuyến nghị MVP
- Dùng `generic_rerank_api` + format "standard" cho qwen3-rerank. Fallback bge-reranker-v2-m3 qua FlagReranker nếu aibox chết.
- Cấu hình `min_rerank_score` làm ngưỡng confidence HIGH (≥0.8 theo ADR).

---

## 5. LightRAG vs GraphRAG (Microsoft) — benchmark 2025-2026

**Verdict: GIỮ (LightRAG).** Bằng chứng mới nhất xác nhận ưu thế về cost + incremental; GraphRAG thắng fidelity ở 1 số benchmark nhưng không có incremental update.

### Bằng chứng
- **Paper LightRAG (EMNLP 2025 Findings, `2025.findings-emnlp.568.pdf`)** — data Legal:
  - **Retrieval tokens**: LightRAG **<100 tokens** (keyword generation + retrieval, 1 API call) vs GraphRAG **610,000 tokens** (610 level-2 communities × 1,000 tokens, hàng trăm API calls).
  - **Incremental update**: thêm bộ data mới cỡ legal dataset → GraphRAG phải **dismantle + regenerate** community structure (~1,399 × 2 × 5,000 tokens ≈ **14M tokens**); LightRAG chỉ **merge entity/relation vào graph hiện có**, không rebuild.
  - **Query latency**: LightRAG **11.2s** vs GraphRAG **23.6s** (avg).
  - **Storage**: LightRAG **39.5MB** vs GraphRAG **286.7MB**.
  - **Insertion** (5 docs, 41k-74k tokens): LightRAG 418-561s vs GraphRAG 642-953s.
- **graphrag-lab** (2026-03-29, benchmark 9 frameworks, gpt-5.4-mini gen / claude-haiku-4-5 judge, 4 metrics):
  | Rank | Framework | Avg | Query latency | Ghi chú |
  |---|---|---|---|---|
  | 1 | nano-graphrag | 3.95 | 4.1s | Leiden community |
  | 2 | cognee | 3.75 | 1.8s | |
  | 3 | fast-graphrag | 3.70 | 2.8s | |
  | 4 | **lightrag** | **3.60** | **4.7s** | 5 search modes |
  | 5 | **microsoft graphrag** | **3.10** | **0.9s** | faithfulness cao nhất |
  | 6 | graphiti | 2.30 | 0.3s | |
- **arxiv 2506.05690 (2026-02)**: GraphRAG nói chung **thường underperform vanilla RAG** trên nhiều task (NQ -13.4% accuracy; latency +2.3×). Lưu ý: **prompt LightRAG ≈10^4 tokens** (không phải <100) — <100 chỉ là phần keyword-gen + retrieval.
- Kết luận cho legal: LightRAG thắng về **incremental + cost + latency trading**; GraphRAG (MS) thắng faithfulness nhưng **không có incremental update** (full re-index mỗi update) → loại cho data 6 tháng. nano-graphrag là lựa chọn thay thế đáng theo dõi nếu cần chất lượng cao hơn, nhưng là fork nhỏ hơn, ít tính năng storage.

### Rủi ro
- Con số "2h/$22 vs 14h/$180" trong CLAUDE.md chưa có nguồn trực tiếp từ paper (paper cho giây/token, không phải $ cụ thể) — đánh dấu là estimate.
- Benchmark graphrag-lab dùng gpt-5.4-mini + rating model khác — không phải benchmark legal VN; dùng làm tham khảo tương đối.

### Khuyến nghị MVP
- Giữ LightRAG. Chạy **golden set legal VN riêng** (đã có `eval/golden_set.json`) làm benchmark thật; nếu LightRAG dưới ngưỡng chất lượng → cân nhắc nano-graphrag (Leiden) nhưng phải đánh đổi incremental update.

---

## 6. Token cost — claim "<100 token/query"

**Verdict: SỬA/ĐỔI claim trong CLAUDE.md — cần diễn giải lại chính xác.**

### Bằng chứng
- **Đúng**: paper LightRAG (Table 3) — retrieval phase dùng **<100 tokens** cho keyword generation + graph retrieval (low-level + high-level keywords, 1 API call). Đây là phần "điều phối" retrieval.
- **KHÔNG đúng nếu hiểu là toàn bộ context gửi LLM**: implementation v1.5.6 có cơ chế token budget riêng (`QueryParam` + `_apply_token_truncation` trong `operate.py`):
  - `DEFAULT_TOP_K = 40` (entities trong local mode)
  - `DEFAULT_CHUNK_TOP_K = 20` (chunks sau rerank)
  - `DEFAULT_MAX_ENTITY_TOKENS = 6000`
  - `DEFAULT_MAX_RELATION_TOKENS = 8000`
  - `DEFAULT_MAX_TOTAL_TOKENS = 30000` (budget toàn bộ context entities+relations+chunks+prompt)
- Cơ chế: `_apply_token_truncation` cắt entity/relation context theo `max_entity_tokens` / `max_relation_tokens` bằng tiktoken, rồi `max_total_tokens` giới hạn tổng. → Context thực gửi LLM **hàng nghìn tokens**, không phải <100.
- arxiv 2506.05690 xác nhận: "LightRAG produces lengthy prompts (≈10^4 tokens)".

### Rủi ro
- Claim "Token <100/retrieval" nếu hiểu sai → thiết kế prompt/wrapper sai giới hạn context; chi phí LLM query thực tế cao hơn tưởng tượng.
- Cần đo real token spend khi chạy golden set (chi phí query = LLM context ≈ 10^4 tokens/lần, không phải <100).

### Khuyến nghị MVP
- Cập nhật CLAUDE.md: **"Retrieval overhead (keyword-gen + graph search) <100 tokens; context gửi LLM được giới hạn bởi max_total_tokens (default 30k) — cần theo dõi token spend thực"**.
- Set `max_total_tokens` theo budget chi phí mong muốn (vd 8-12k) thay vì default 30k để tiết kiệm.

---

## Tóm tắt quyết định cần cập nhật vào CLAUDE.md

| # | Mục | CLAUDE.md hiện tại | Thay đổi |
|---|---|---|---|
| 1 | LightRAG version | "pin version" (chưa ghi số) | Ghi **v1.5.6 (2026-08-06)**, Python ≥3.10, deps chính: networkx, tiktoken, pydantic, aiohttp, nano-vectordb, json_repair (transformers KHÔNG bắt buộc) |
| 2 | Graph engine | "NetworkX default, cần benchmark" | **Giữ NetworkX cho dev; production dùng PGGraphStorage (SQL, KHÔNG NetworkX)** — điểm yếu NetworkX không áp dụng production. Benchmark gate: >10k docs / >50k entity → Neo4j |
| 3 | Embedding dims | "text-embedding-v4 LOCK" | Bổ sung: dims configurable 64-2048, default 1024 — **chốt 1024** để khớp fallback Qwen3-Embedding-0.6B (dims 1024). Base URL cần verify (api-box.vn vs api.ai-box.vn) |
| 4 | Rerank API | "qwen3-rerank, verify 2026-08-09" | Ghi rõ: `/v1/rerank` Jina/Cohere-compatible; LightRAG `generic_rerank_api` response_format="standard"; fallback bge-reranker-v2-m3 (8192 max, recommend 1024) |
| 5 | LightRAG vs GraphRAG | "LightRAG 2h/$22 vs GraphRAG 14h/$180" | Giữ LightRAG; **đổi số liệu sang nguồn paper**: retrieval <100 vs 610k tokens; incremental merge vs rebuild 14M tokens; query 11.2s vs 23.6s; benchmark graphrag-lab 2026: lightrag 3.60/4.7s vs MS 3.10/0.9s (faithfulness). "2h/$22" = estimate chưa có nguồn |
| 6 | Token <100 | "Token <100/retrieval" | **SỬA**: <100 chỉ là keyword-gen + graph search overhead; context LLM giới hạn bởi max_total_tokens (default 30k, khuyến nghị 8-12k cho legal) |

## 3 rủi ro lớn nhất
1. **Claim token sai lệch** ("<100/retrieval" hiểu nhầm thành context LLM) → ước lượng chi phí query sai, thiết kế prompt sai giới hạn. Context thực ≈ 10^4 tokens/lần.
2. **Embedding dims + base URL chưa chốt runtime**: aibox dims linh hoạt 64-2048 và base URL có 2 phiên bản (api-box.vn / api.ai-box.vn) — phải verify bằng curl trước lần ghi schema đầu; đổi dims giữa chừng = re-embed toàn bộ.
3. **NetworkX single-writer nếu vô tình dùng storage default trong production**: phải ép config PGGraphStorage (SQL) khi deploy; PGGraphStorage scale lớn chưa có benchmark công bố — cần đo lúc implement.
