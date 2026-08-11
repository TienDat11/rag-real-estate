# LightRAG — Tham chiếu tham số & Các điểm custom tăng độ chính xác

> **Mục đích:** Tra soát khi code — KHÔNG phải research lại.
> **Đối tượng:** `lightrag-hku==1.5.6` (bản dự án LOCK, 2026-08-06) + tính năng mới nhất trên `main`.
> **Nguồn:** source `HKUDS/LightRAG@v1.5.6` (`lightrag.py`, `base.py`, `operate.py`, `addon_params.py`), docs `ProgramingWithCore.md`, `LightRAG-API-Server.md`, `FileProcessingPipeline.md`, `ParagraphSemanticChunking.md`, README, release notes v1.5.x | 2026-08-10 | Tiếng Việt.
> **Độ tin cậy:** MỌI tham số trong tài liệu này đã verify bằng đọc source trực tiếp trên tag v1.5.6 (không suy đoán).

---

## 0. Tóm tắt một màn hình — "điều chỉnh nào tăng accuracy nhất?"

| # | Điều chỉnh | Tác động | Chi phí | Dự án legal nên |
|---|---|---|---|---|
| 1 | **Chunker `P` (Paragraph semantic)** thay vì mặc định `F` | Cao nhất — giữ Điều/Khoản/Bảng nguyên vẹn, hết lỗi heading lệch nội dung | Miễn phí (chỉ qua server pipeline) | ✅ **BẮT BUỘC** khi parse văn bản luật |
| 2 | **`addon_params["language"]="Vietnamese"`** | Entity/relation description + summary đúng ngôn ngữ, tăng retrieval VN | Miễn phí | ✅ BẮT BUỘC |
| 3 | **`entity_type_prompt_file` (YAML profile domain)** | Ép LLM trích đúng type pháp lý (điều luật, văn bản, quy hoạch...) | 1 lần viết prompt | ✅ BẮT BUỘC |
| 4 | **`ENTITY_EXTRACTION_USE_JSON=true`** | Extraction ổn định hơn, ít format lỗi, đặc biệt model nhỏ | Chậm hơn chút | ✅ Nên bật |
| 5 | **`entity_extract_max_gleaning` 1→3** | Graph giàu hơn (LLM quét lại chunk tìm entity bỏ sót) | Tốn 2-3x LLM ingest | ⚠️ Cân nhắc (tốn cost) |
| 6 | **Rerank + `min_rerank_score`** | +20-50% top-k accuracy | +1-2s latency/query | ✅ Có (aibox qwen3-rerank) |
| 7 | **`chunk_token_size` 1200→800 (F/R) hoặc `CHUNK_P_SIZE`** | Chunk nhỏ → entity mật độ cao hơn | Nhiều chunk hơn | ⚠️ Test golden set |
| 8 | **`role_llm_configs` 4 vai khác nhau** | EXTRACT nhanh+rẻ, QUERY mạnh → vừa rẻ vừa chất lượng | Không | ✅ Nên (ds-v4-flash + model lớn) |
| 9 | **`max_total_tokens` 30000→8-12k** | Context ngắn, đỡ loãng, rẻ hơn | Giảm chi tiết | ✅ Có (đã chốt) |
| 10 | **`only_need_context=True` + tự build prompt** | Kiểm soát citation/confidence/lọc hiệu lực | Tự code wrapper | ✅ Có (đã chốt ADR) |

> ⚠️ **Những thứ LightRAG KHÔNG có (đừng mất công tìm):** pagerank, query rewriting/HyDE, web search, `skip_keyword_extraction`, `mix_llm`, `from_scratch`, `batch_insert`, `use_direct_chunk`. Chỉ có **keyword extraction** (không phải rewrite). Muốn rewrite → tự làm TRƯỚC khi gọi query.

---

## 1. Constructor `LightRAG(...)` — toàn bộ tham số (v1.5.6)

> Tất cả mặc định lấy từ env: `get_env_value("TÊN_ENV", DEFAULT)`. Có thể set cả env lẫn param (param object thắng cho instance đó).

### 1.1 Thư mục & workspace

| Tham số | Env | Default | Ý nghĩa |
|---|---|---|---|
| `working_dir` | – | `"./rag_storage"` | Thư mục cache/tmp (với PG vẫn cần cho pipeline status) |
| `workspace` | `WORKSPACE` | `""` | **Cô lập dữ liệu (multi-tenant)** — mỗi workspace 1 bộ graph/vector riêng. Dùng cho phân tách khách hàng |
| `log_level` / `log_file_path` | – | `None` | ⚠️ **Deprecated** — dùng `setup_logger()` thay thế |

### 1.2 Storage (⚠️ CHỐT TRƯỚC lần index đầu)

| Tham số | Env | Default | Dự án dùng |
|---|---|---|---|
| `kv_storage` | – | `"JsonKVStorage"` | **`"PGKVStorage"`** |
| `vector_storage` | – | `"NanoVectorDBStorage"` | **`"PGVectorStorage"`** (cần pgvector) |
| `graph_storage` | – | `"NetworkXStorage"` | **`"PGTableGraphStorage"`** (KHÔNG dùng AGE) |
| `doc_status_storage` | – | `"JsonDocStatusStorage"` | **`"PGDocStatusStorage"`** |
| `vector_db_storage_cls_kwargs` | – | `{}` | Tham số phụ cho vector DB, vd `"cosine_better_than_threshold": 0.2` |

### 1.3 Retrieval budget (ảnh hưởng trực tiếp context gửi LLM)

| Tham số | Env | Default | Ý nghĩa |
|---|---|---|---|
| `top_k` | `TOP_K` | `40` | Số entity (local) / relation (global) lấy từ graph |
| `chunk_top_k` | `CHUNK_TOP_K` | `20` | Số chunk lấy từ vector search, giữ lại sau rerank (nếu None → bằng top_k) |
| `max_entity_tokens` | `MAX_ENTITY_TOKENS` | `6000` | Token budget cho phần entity context |
| `max_relation_tokens` | `MAX_RELATION_TOKENS` | `8000` | Token budget cho phần relation context |
| `max_total_tokens` | `MAX_TOTAL_TOKENS` | `30000` | **Tổng budget** (system prompt + entity + relation + chunk). Chunk = total − entity − relation |
| `related_chunk_number` | `RELATED_CHUNK_NUMBER` | `5` | Số chunk liên quan kéo theo mỗi entity/relation từ graph |
| `kg_chunk_pick_method` | `KG_CHUNK_PICK_METHOD` | `"VECTOR"` | Cách chọn chunk từ (entity/relation→chunk): `"VECTOR"` (similarity) hay `"WEIGHT"` (weight) |
| `enable_content_headings` | `ENABLE_CONTENT_HEADINGS` | `True` | Gửi đường dẫn heading của chunk (vd `Luật Đất đai → Chương I → Điều 5`) cho LLM — **tăng context cho văn bản luật** |
| `cosine_better_than_threshold` | `COSINE_THRESHOLD` | `0.2` | Ngưỡng similarity khi chọn chunk theo vector |

**Khuyến nghị legal (đã chốt):** `top_k=30-60`, `chunk_top_k=10-20`, `max_total_tokens=8000-12000`, `kg_chunk_pick_method="VECTOR"`, `enable_content_headings=True`.

### 1.4 Entity extraction (điều chỉnh chất lượng graph)

| Tham số | Env | Default | Ý nghĩa |
|---|---|---|---|
| `entity_extract_max_gleaning` | `MAX_GLEANING` | `1` | Số lần LLM **quét lại** chunk tìm entity/relation còn sót. **Tăng lên 3 = graph giàu hơn** (tốn 2-3x LLM ingest) |
| `entity_extract_max_records` | `MAX_EXTRACTION_RECORDS` | (map-reduce chặn) | Trần tổng entity+relation trong 1 response LLM |
| `entity_extract_max_entities` | `MAX_EXTRACTION_ENTITIES` | – | Trần số entity trong 1 response |
| `force_llm_summary_on_merge` | `FORCE_LLM_SUMMARY_ON_MERGE` | – | Số description tối thiểu để ép LLM tóm tắt khi merge entity (tránh nối chuỗi thô) |
| `entity_extraction_use_json` | `ENTITY_EXTRACTION_USE_JSON` | `false` | **JSON structured output** — ổn định hơn, model nhỏ chạy tốt hơn. `true` khuyến nghị |

### 1.5 Chunking

| Tham số | Env | Default | Ý nghĩa |
|---|---|---|---|
| `chunk_token_size` | `CHUNK_SIZE` | `None`→`1200` | Max token/chunk. `None` = lấy từ `addon_params["chunker"]` |
| `chunk_overlap_token_size` | `CHUNK_OVERLAP_SIZE` | `None`→`100` | Overlap giữa 2 chunk liền kề |
| `tokenizer` | – | `None`→Tiktoken | Hàm tokenizer; mặc định TiktokenTokenizer |
| `tiktoken_model_name` | – | `"gpt-4o-mini"` | Model tiktoken dùng để đếm token |
| `chunking_func` | – | `chunking_by_token_size` | ⚠️ Legacy escape hatch — **bị bỏ qua** khi chọn F/R/V/P qua pipeline; chỉ dùng cho `ainsert(text)` trực tiếp |

> ⚠️ **Quan trọng:** `ainsert()` luôn chunk theo **F (fixed token)**. Muốn dùng R/V/P → phải qua **server REST pipeline** (`LIGHTRAG_PARSER` + `process_options`) hoặc `apipeline_enqueue_documents`. Đây là lý do dự án nên chạy LightRAG server thay vì gọi SDK trực tiếp khi cần chunking P.

### 1.6 Embedding

| Tham số | Env | Default | Ý nghĩa |
|---|---|---|---|
| `embedding_func` | – | `None` (**bắt buộc**) | `EmbeddingFunc` — khai báo bắt buộc `embedding_dim` + `max_token_size` |
| `embedding_token_limit` | – | tự set | Lấy từ `embedding_func.max_token_size` (không set tay) |
| `embedding_chunk_overlap_token_size` | `EMBEDDING_CHUNK_OVERLAP_TOKEN_SIZE` | `100` | Overlap khi hard-fallback cắt lại chunk quá dài so với embedding context |
| `embedding_batch_num` | `EMBEDDING_BATCH_NUM` | – | **Số text/request embedding** — tăng → giảm số API calls, ingest nhanh hơn (aibox: 10 text/request) |
| `embedding_func_max_async` | `EMBEDDING_FUNC_MAX_ASYNC` | – | Số embedding call đồng thời tối đa |
| `embedding_cache_config` | – | `{"enabled": False, "similarity_threshold": 0.95, "use_llm_check": False}` | Cache embedding: query trùng (similarity ≥0.95) → dùng lại vector, không tính lại |
| `default_embedding_timeout` | `EMBEDDING_TIMEOUT` | – | Timeout embedding (giây) |

### 1.7 LLM (4 vai trò — ⭐ điểm custom quan trọng nhất)

| Tham số | Env | Default | Ý nghĩa |
|---|---|---|---|
| `llm_model_func` | – | `None` (**bắt buộc**) | Callable `(prompt, system_prompt, history_messages, keyword_extraction, **kwargs) -> str` — tự viết wrapper gọi aibox |
| `role_llm_configs` | – | `None` | ⭐ **Cấu hình LLM RIÊNG cho từng vai**: `{"EXTRACT": {...}, "QUERY": {...}, "KEYWORDS": {...}, "VLM": {...}}`. Mỗi entry: `func`, `kwargs`, `max_async`, `timeout` |
| `llm_model_name` | – | `"gpt-4o-mini"` | Tên model (info) |
| `llm_model_kwargs` | – | `{}` | Kwargs thêm truyền vào `llm_model_func` (vd `temperature`) |
| `summary_max_tokens` | `SUMMARY_MAX_TOKENS` | `500` | Max token mô tả entity/relation |
| `summary_context_size` | `SUMMARY_CONTEXT_SIZE` | `10000` | Max token mỗi response LLM khi tóm tắt map-reduce |
| `summary_length_recommended` | `SUMMARY_LENGTH_RECOMMENDED` | – | Độ dài khuyến nghị output tóm tắt |
| `llm_model_max_async` | `MAX_ASYNC_LLM` (alias `MAX_ASYNC`) | – | Số LLM call đồng thời tối đa |
| `default_llm_timeout` | `LLM_TIMEOUT` | – | Timeout LLM (giây). **Hiệu lực thực = 2x config** (vd `EXTRACT_LLM_TIMEOUT=300` → 600s) |
| `enable_llm_cache` | – | `True` | Cache response LLM trùng query |
| `enable_llm_cache_for_entity_extract` | – | `True` | Cache extraction (tốn nhất — **giữ lại** khi dọn cache) |

**Vai LLM (4 vai — khuyến nghị từ README v1.5):**

| Vai | Công việc | Khuyến nghị |
|---|---|---|
| `EXTRACT` | Trích entity/relation từng chunk | **Non-thinking**, vừa đủ mạnh, nhanh (Claude Haiku / Qwen3 / DeepSeek-v4-lite) |
| `KEYWORDS` | Trích keyword từ query | **Phi-thinking, nhỏ, nhanh** (ảnh hưởng latency query) |
| `QUERY` | Viết câu trả lời từ context dài + nhiễu | **Mạnh nhất**, thinking OK |
| `VLM` | Phân tích ảnh/bảng khi `VLM_PROCESS_ENABLE=true` | Vision model |

### 1.8 Rerank

| Tham số | Env | Default | Ý nghĩa |
|---|---|---|---|
| `rerank_model_func` | – | `None` | Callable rerank — **tất cả config model/key/top_n nằm TRONG hàm này** |
| `rerank_model_max_async` | `MAX_ASYNC_RERANK` | fallback `MAX_ASYNC_LLM` | Số rerank call đồng thời |
| `default_rerank_timeout` | `RERANK_TIMEOUT` | `30` | Timeout rerank (ngắn hơn LLM timeout) |
| `min_rerank_score` | `MIN_RERANK_SCORE` | `0.0` | **Lọc chunk sau rerank**: chunk có score < ngưỡng bị loại. Dự án: `0.3-0.4` cho legal (kết hợp confidence HIGH ≥0.8 cho câu cuối) |

**Rerank provider (server `.env`):** `RERANK_BINDING=cohere|jina|aliyun|null` + `RERANK_MODEL`, `RERANK_BINDING_HOST`, `RERANK_BINDING_API_KEY`. aibox qwen3-rerank = payload Cohere-flat → dùng `generic_rerank_api(response_format="standard")` hoặc `RERANK_BINDING=cohere`.

### 1.9 Concurrency & pipeline (tuning hiệu năng, không phải accuracy)

| Tham số | Env | Default | Ý nghĩa |
|---|---|---|---|
| `max_parallel_insert` | `MAX_PARALLEL_INSERT` | `3` | Số document xử lý song song. **≈ 1/3 `MAX_ASYNC_LLM`** (nguyên tắc chính thức) |
| `max_parallel_parse_native/mineru/docling` | `MAX_PARALLEL_PARSE_*` | – | Số file parse song song theo engine |
| `max_parallel_analyze` | `MAX_PARALLEL_ANALYZE` | – | Số item multimodal analyze song song |
| `queue_size_parse/analyze/insert` | `QUEUE_SIZE_*` | – | Hàng đợi pipeline |
| `pipeline_scheduling_page_size` | `PIPELINE_SCHEDULING_PAGE_SIZE` | – | Paging scheduler (0 = tắt) |
| `pipeline_require_strict_storage_reads` | – | – | Fail startup nếu doc_status thiếu strict capability |
| `max_pending_documents` | `MAX_PENDING_DOCUMENTS` | – | Giới hạn doc chờ (0 = tắt) |
| `vlm_process_enable` | `VLM_PROCESS_ENABLE` | `false` | Master switch VLM multimodal |

### 1.10 Giới hạn nguồn & bảo mật

| Tham số | Env | Default | Ý nghĩa |
|---|---|---|---|
| `max_graph_nodes` | – | – | Max node trong graph query |
| `max_source_ids_per_entity/relation` | – | – | Trần số nguồn (doc) gán mỗi entity/relation |
| `source_ids_limit_method` | `SOURCE_IDS_LIMIT_METHOD` | `"IGNORE_NEW"` | Khi quá trần: `IGNORE_NEW` (bỏ nguồn mới) hay `FIFO` (đổi sớm nhất) |
| `max_file_paths` / `file_path_more_placeholder` | – | – | Trần file_path lưu trên entity/relation (citation) |

### 1.11 Deprecated / không tồn tại

- `auto_manage_storages_states` — deprecated (không auto-init storage).
- `ollama_server_infos` — chỉ cho Ollama.
- **KHÔNG tồn tại trong v1.5.6:** `use_web_search`, `skip_keyword_extraction`, `mix_llm`, `cohere`, `namespace`, `from_scratch`, `fast_insert`, `batch_insert`, `sync_storage`, `pagerank`, `node_embedding_algo`, `llm_model_max_token_size`, `chunk_overlap_token_ratio`.

---

## 2. `QueryParam` — toàn bộ tham số query (v1.5.6)

| Field | Env | Default | Ý nghĩa |
|---|---|---|---|
| `mode` | – | `"mix"` | `local` / `global` / `hybrid` / `naive` / `mix` / `bypass` |
| `only_need_context` | – | `False` | Chỉ lấy context retrieval, **KHÔNG gọi LLM trả lời** → dự án dùng để tự build citation/confidence |
| `only_need_prompt` | – | `False` | Chỉ lấy prompt đã gom, không gọi LLM |
| `response_type` | – | `"Multiple Paragraphs"` | Định dạng trả lời: "Multiple Paragraphs", "Bullet Points", "One Sentence"... |
| `stream` | – | `False` | Streaming output |
| `top_k` | `TOP_K` | `40` | Entity (local) / relation (global) |
| `chunk_top_k` | `CHUNK_TOP_K` | `20` | Chunk từ vector + giữ sau rerank |
| `max_entity_tokens` | `MAX_ENTITY_TOKENS` | `6000` | Budget entity context |
| `max_relation_tokens` | `MAX_RELATION_TOKENS` | `8000` | Budget relation context |
| `max_total_tokens` | `MAX_TOTAL_TOKENS` | `30000` | Tổng budget |
| `hl_keywords` | – | `[]` | ⭐ **Inject sẵn high-level keyword** → bỏ qua LLM KEYWORDS (điều khiển retrieval tay) |
| `ll_keywords` | – | `[]` | ⭐ Inject sẵn low-level keyword |
| `conversation_history` | – | `[]` | Lịch sử chat — **CHỈ gửi LLM cho ngữ cảnh, KHÔNG dùng cho retrieval** |
| `user_prompt` | – | `None` | Hướng dẫn thêm cho LLM trả lời — **KHÔNG ảnh hưởng retrieval** |
| `enable_rerank` | `RERANK_BY_DEFAULT` | `True` | Bật rerank (nếu có model) |
| `include_references` | – | `False` | Kèm danh sách nguồn (reference) trong response |

> ⚠️ **KHÔNG có trong QueryParam v1.5.6:** `min_rerank_score` (là constructor param của LightRAG), `rerank_top_k`, `max_token_for_text_unit`, `use_web_search`, `task_name`.

**Cách dùng cho dự án (legal wrapper):**
```python
param = QueryParam(
    mode="mix",                       # hoặc "hybrid" khi đã quen
    only_need_context=True,           # lấy context → tự filter hiệu lực → tự build prompt
    top_k=40, chunk_top_k=15,
    max_total_tokens=10000,           # 8-12k cho legal
    enable_rerank=True,
)
result = await rag.aquery_data(question, param=param)   # structured: entities/relations/chunks
```

---

## 3. `addon_params` — toàn bộ key (v1.5.6)

> `addon_params` là dict tự do, được normalize vào `_addon_params`. Key nào bỏ trống sẽ backfill từ env.

| Key | Env | Default | Ý nghĩa |
|---|---|---|---|
| `language` | `SUMMARY_LANGUAGE` | `"English"` | ⭐ Ngôn ngữ output extraction/summary/keyword. **Legal VN: `"Vietnamese"`** |
| `entity_type_prompt_file` | `ENTITY_TYPE_PROMPT_FILE` | `""` | ⭐ **YAML profile** (đặt `PROMPT_DIR/entity_type/`, mặc định `./prompts`) định nghĩa `entity_types_guidance`, `entity_extraction_examples`, `entity_extraction_json_examples`. Thay thế env `ENTITY_TYPES` (đã deprecated từ v1.5.0) |
| `chunker` | `CHUNK_*` | xem dưới | Cấu hình chunker F/R/V/P — **snapshot theo từng doc** tại thời điểm enqueue |

**`chunker` đầy đủ (default):**
```python
{
  "chunk_token_size": 1200,                       # top-level fallback (trừ P)
  "fixed_token": {                                # F
    "chunk_token_size": 1200,
    "chunk_overlap_token_size": 100,
    "split_by_character": None,
    "split_by_character_only": False,
  },
  "recursive_character": {                        # R
    "chunk_token_size": 1200,
    "chunk_overlap_token_size": 100,
    "separators": ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
  },
  "semantic_vector": {                            # V (không overlap)
    "chunk_token_size": 1200,
    "breakpoint_threshold_type": "percentile",
    "breakpoint_threshold_amount": None,
    "buffer_size": 1,
    "sentence_split_regex": "(?<=[.?!])\\s+|(?<=[。？！])",
  },
  "paragraph_semantic": {                         # P
    "chunk_token_size": 2000,                     # KHÔNG kế thừa top-level (CHUNK_P_SIZE)
    "chunk_overlap_token_size": 100,              # CHUNK_P_OVERLAP_SIZE
  },
}
```

> ⚠️ `enable_multimodal_pipeline` = deprecated & ignored (đã chuyển sang `process_options`).

**Precedence chunker:** `addon_params["chunker"]` rõ ràng > env `CHUNK_*` theo strategy > constructor legacy > env legacy (`CHUNK_SIZE`, `CHUNK_OVERLAP_SIZE`).

---

## 4. Insert & Delete — signature chính xác

### 4.1 `insert` / `ainsert` (SDK path — CHỈ chunk F)

```python
async def ainsert(
    self,
    input: str | list[str],                    # text hoặc list text
    split_by_character: str | None = None,     # cắt theo ký tự (legacy)
    split_by_character_only: bool = False,
    ids: str | list[str] | None = None,        # số lượng phải khớp input
    file_paths: str | list[str] | None = None, # ⭐ citation tracking
    track_id: str | None = None,
) -> str
```
- `insert(...)` = wrapper sync (gọi `loop.run_until_complete`) — **KHÔNG dùng trong async context**; ưu tiên `ainsert`.
- ⚠️ **`ainsert` luôn chunk F** — không chọn được R/V/P. Muốn P → server pipeline.

### 4.2 Server pipeline (đường dẫn có R/V/P + parser)

```python
await rag.apipeline_enqueue_documents(files)       # enqueue file (chunk_options snapshot tại đây)
await rag.apipeline_process_enqueue_documents()    # xử lý theo LIGHTRAG_PARSER + hint
```
- `LIGHTRAG_PARSER=docx:native-teP,pdf:mineru-iteP,*:docling-iteP,*:legacy-R` — route theo extension.
- Filename hint: `report.[-P(drop_rf=true)].docx` — ghi đè per-file.
- Option: `i`(ảnh) `t`(bảng) `e`(công thức) `!`(bỏ graph, chỉ vector) `F`/`R`/`V`/`P`(chunker).

### 4.3 Delete

```python
async def adelete_by_doc_id(self, doc_id: str) -> DeletionResult
```
- Xóa chunk + entity/relation **chỉ thuộc doc đó**, **tái tạo** entity/relation dùng chung (từ LLM cache). Không undo được. Chỉ async.

---

## 5. Query API — `query` / `aquery` / `aquery_data` / `aquery_llm`

| Method | Trả về | Dùng khi |
|---|---|---|
| `aquery(q, param)` | str (câu trả lời) | Chat đơn giản |
| `aquery_data(q, param)` | `QueryResult` (content + **raw_data** structured: entities/relations/chunks + keywords + references) | ⭐ **Dự án legal: lấy raw_data để tính confidence/citation** |
| `aquery_llm(q, param)` | str | Muốn app tự gọi LLM (ít dùng) |
| `aquery()` với `param.only_need_context=True` | `QueryContextResult` (context + raw_data) | Lấy context thô → tự build prompt |

**Server REST (port 9621):**
- `POST /query` — non-stream, `{"query", "mode", "top_k", "chunk_top_k", "max_total_tokens", "user_prompt", "conversation_history", "include_references", "include_chunk_content", "enable_rerank"}`
- `POST /query/stream` — NDJSON (line 1 = references, các line sau = response chunks)
- `POST /query/data` — ⭐ structured (entities/relations/chunks/keywords/references) — **luôn có references**
- `POST /documents/upload`, `/documents/scan`, `/documents/text(s)`
- `GET /documents` (trạng thái), `GET /documents/{id}/status`
- `GET/TRACE /trace` — tracing
- Flag: `--host 0.0.0.0 --port 9621 --working-dir ./rag_storage --input-dir ./inputs --workspace <name> --api-prefix /rag --rerank-binding cohere`
- Env: `RERANK_BINDING`, `EMBEDDING_ASYMMETRIC`, `LIGHTRAG_PARSER`, `LLM_BINDING`, `EMBEDDING_BINDING`...

> ⚠️ **Bảo mật:** server mặc định KHÔNG auth (đã có CVE). Phải đặt sau reverse-proxy có auth + rate-limit.

---

## 6. Chunking 4 chiến lược — chi tiết & khi nào dùng

| Chiến lược | Cách cắt | Overlap | Đặc điểm | Dự án legal |
|---|---|---|---|---|
| **F** (Fixed) | Token cố định / theo ký tự | Có | Legacy, `ainsert` mặc định | ⚠️ Không nên cho luật |
| **R** (Recursive) | Cascade separator `\n\n → \n → 。！？ → ；， → space → ""` | Có | Tôn trọng ranh giới câu/đoạn VN (có dấu CJK) | OK nếu không vào được P |
| **V** (Vector) | SemanticChunker: cắt theo breakpoint ngữ nghĩa giữa 2 câu liền | **Không** | Tự cắt theo chủ đề; chunk quá dài → tự tách R | ⚠️ Tốn embedding, không chắc ranh giới luật |
| **P** (Paragraph) | **Theo heading/đoạn/bảng thật của tài liệu** (từ `.blocks.jsonl` sidecar) | Section không overlap; body dài overlap theo `CHUNK_P_OVERLAP_SIZE` | ⭐ Native; cần sidecar (native/mineru/docling); **giữ Điều/Khoản/Bảng nguyên vẹn** | ✅ **TỐT NHẤT cho văn bản luật** |

**Cấu hình P quan trọng (env):**
- `CHUNK_P_SIZE` = `2000` (mặc định riêng, KHÔNG kế thừa `CHUNK_SIZE`)
- `CHUNK_P_OVERLAP_SIZE` = `100` (mặc định kế thừa `CHUNK_OVERLAP_SIZE`)
- `CHUNK_P_DROP_REFERENCES=true` — bỏ khối tài liệu tham khảo (tránh bão entity từ citation, gây LLM timeout)
- Ngưỡng P (tính theo N=`CHUNK_P_SIZE`): `target_max=N`, `target_ideal=0.75N`, `table_max=0.625N`, `table_ideal=0.375N`, `small_tail=0.125N`
- P auto-degrade về R khi thiếu sidecar (không mất doc).

> **Với văn bản luật VN:** `LIGHTRAG_PARSER=docx:native-P,pdf:mineru-P,*:docling-P,*:legacy-R` + `CHUNK_P_SIZE=1500-2000` + `CHUNK_P_DROP_REFERENCES=true`. Điều/Khoản thường nằm gọn trong 1 section → P giữ nguyên vẹn, retrieval local mode khớp "Điều 123 BLDS" chính xác.

---

## 7. Query modes — khi nào dùng gì

| Mode | Đường retrieval | Dự án legal dùng khi |
|---|---|---|
| `local` | Entity cụ thể + 1-hop neighbors | Hỏi điều khoản/entity cụ thể ("thế chấp là gì?") |
| `global` | Relation/edge + chủ đề rộng | Hỏi tổng quan/cross-doc ("so sánh các hình thức chuyển nhượng") |
| `hybrid` | local + global song song | Câu vừa chi tiết vừa tổng quan |
| `naive` | Pure vector (không graph) | Chunk đơn giản, không cần quan hệ |
| `mix` | local + global + naive | **Default, đầy đủ nhất** — khuyến nghị |
| `bypass` | Không retrieval — LLM trả lời thẳng | Kiểm tra LLM, không phải RAG |

> Với rerank bật → nên dùng `mix` (README khuyến nghị). `mix` chậm hơn `naive` chút.

---

## 8. ⭐ Danh sách điểm custom tăng accuracy (áp dụng cho rag-real-estate)

### 8.1 Layer ingest (chất lượng graph)

1. **`addon_params["language"]="Vietnamese"`** — extraction/summary/keyword đúng tiếng Việt. ⚠️ Nếu để default "English", LLM mô tả entity bằng tiếng Anh → retrieval VN kém.
2. **`entity_type_prompt_file`** — tạo `prompts/entity_type/legal_vn.yml`:
   ```yaml
   entity_types_guidance: |
     - VănBản: tên văn bản pháp luật (Luật Đất đai 2024, Nghị định...)
     - ĐiềuLuật: điều/khoản cụ thể (Điều 27, Khoản 2 Điều 123...)
     - TổChức: cơ quan/công ty (UBND, Sở Tài nguyên...)
     - KháiNiệm: thuật ngữ pháp lý (thế chấp, cầm cố, quy hoạch...)
     - ĐịaĐiểm: địa danh, thửa đất, dự án
   entity_extraction_examples: [...]
   ```
   → Ép LLM trích đúng loại thực thể pháp lý, giảm nhiễu.
3. **`ENTITY_EXTRACTION_USE_JSON=true`** — output JSON ổn định hơn delimiter text.
4. **`entity_extract_max_gleaning=3`** (nếu budget LLM cho phép) — graph dày hơn. Cân nhắc cost: ingest legal 6 tháng/lần → chấp nhận được.
5. **Chunker P** + `CHUNK_P_DROP_REFERENCES=true` — giữ Điều/Khoản nguyên vẹn.
6. **`force_llm_summary_on_merge` thấp** (vd 2) — ép LLM tóm tắt thay vì nối mô tả dài khi merge entity → summary sạch, cụ thể.

### 8.2 Layer retrieval

7. **Rerank + `min_rerank_score`** — aibox qwen3-rerank (Cohere-flat). `min_rerank_score=0.3` lọc chunk rác; kết hợp confidence HIGH ≥0.8.
8. **`kg_chunk_pick_method="VECTOR"`** — chọn chunk theo similarity thay vì weight mặc định.
9. **`enable_content_headings=True`** — LLM thấy "Luật Đất đai 2024 → Chương III → Điều 27" giúp trả lời đúng ngữ cảnh.
10. **`top_k`/`chunk_top_k`/`max_total_tokens`** — tinh chỉnh qua golden set (bắt đầu 40/20/10000).
11. **`hl_keywords`/`ll_keywords` inject** — nếu biết trước domain (vd query có "thế chấp") → inject sẵn keyword để bỏ LLM keyword-gen, ổn định + rẻ hơn.
12. **`only_need_context=True` + `aquery_data`** — lấy raw_data (entities/relations/chunks + score) → tự tính confidence 3-tier + filter hiệu lực + citation → tự build prompt → gọi LLM QUERY. Đây là **lớp chống hallucination** của dự án.

### 8.3 Layer model

13. **`role_llm_configs`** — 3 vai khác nhau:
    ```python
    rag = LightRAG(
        llm_model_func=aibox_complete,          # base: query
        role_llm_configs={
            "extract":   {"func": aibox_complete, "kwargs": {"model": "ds-v4-flash"}, "max_async": 8},
            "keywords":  {"func": aibox_complete, "kwargs": {"model": "ds-v4-flash"}, "max_async": 8},
            "query":     {"func": aibox_complete, "kwargs": {"model": "ds-v4-sonnet"}, "max_async": 4},
        },
    )
    ```
    → EXTRACT/KEYWORDS rẻ + nhanh, QUERY mạnh.
14. **`llm_model_kwargs={"temperature": 0}`** cho extraction (xác định), `0.2-0.3` cho query.

### 8.4 Layer hiệu năng (để pipeline không nghẽn)

15. `MAX_PARALLEL_INSERT` ≈ `MAX_ASYNC_LLM / 3`.
16. `EMBEDDING_BATCH_NUM` tăng (aibox ≤10) → giảm API calls.
17. Timeout: `EXTRACT_LLM_TIMEOUT` đủ lớn (chunk dài legal dễ nhiều entity) — hiệu lực thực = 2x.
18. `OPENAI_LLM_MAX_TOKENS`/`OPENAI_LLM_MAX_COMPLETION_TOKENS` chặn output cực dài (rule: `max_output < timeout × tokens_per_sec`).

### 8.5 Điều CẤM / rủi ro ghi nhớ

- ⚠️ **Đổi embedding model/dims/`EMBEDDING_ASYMMETRIC` = phải xóa vector + re-index toàn bộ.** (Đã LOCK aibox v4 dims 1024.)
- ⚠️ **Đổi `LIGHTRAG_PARSER`/chunker chỉ ảnh hưởng doc mới enqueue** — doc cũ giữ `chunk_options` snapshot cũ. Muốn đổi → xóa + upload lại.
- ⚠️ **Đổi engine parser cho doc cũ** → xóa + upload lại (không reprocess được cross-engine).
- ⚠️ `ENTITY_TYPES` deprecated → dùng `ENTITY_TYPE_PROMPT_FILE`.
- ⚠️ Storage env PG: cần `POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DATABASE` (+ `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_WORKSPACE` cho multi-tenant).
- ⚠️ `MAX_PARALLEL_INSERT` > `MAX_ASYNC_LLM` → query chậm (đã có trong checklist lỗi).

---

## 9. Env vars quan trọng — bảng tra nhanh

| Env | Default | Ghi chú |
|---|---|---|
| `WORKSPACE` | `""` | Multi-tenant isolation |
| `TOP_K` / `CHUNK_TOP_K` | `40` / `20` | Retrieval |
| `MAX_ENTITY_TOKENS` / `MAX_RELATION_TOKENS` / `MAX_TOTAL_TOKENS` | `6000` / `8000` / `30000` | Token budget (legal: 8-12k total) |
| `RELATED_CHUNK_NUMBER` | `5` | Chunk theo entity/relation |
| `KG_CHUNK_PICK_METHOD` | `VECTOR` | `WEIGHT` hoặc `VECTOR` |
| `ENABLE_CONTENT_HEADINGS` | `true` | Heading breadcrumb cho LLM |
| `COSINE_THRESHOLD` | `0.2` | Threshold similarity |
| `MAX_GLEANING` | `1` | →3 cho graph giàu |
| `ENTITY_EXTRACTION_USE_JSON` | `false` | →true khuyến nghị |
| `ENTITY_TYPE_PROMPT_FILE` | `""` | YAML profile domain |
| `SUMMARY_LANGUAGE` | `English` | →`Vietnamese` |
| `CHUNK_SIZE` / `CHUNK_OVERLAP_SIZE` | `1200` / `100` | Chunk F/R |
| `CHUNK_P_SIZE` / `CHUNK_P_OVERLAP_SIZE` | `2000` / `100` | Chunk P |
| `CHUNK_P_DROP_REFERENCES` | – | Bỏ references trước chunk P |
| `CHUNK_R_SEPARATORS` | CJK cascade | Separator R |
| `LLM_TIMEOUT` / `EXTRACT_LLM_TIMEOUT` | – | Hiệu lực thực = 2x |
| `MAX_ASYNC_LLM` / `MAX_PARALLEL_INSERT` | – | `insert ≈ llm/3` |
| `EMBEDDING_BATCH_NUM` / `EMBEDDING_FUNC_MAX_ASYNC` | – | Embedding throughput |
| `EMBEDDING_ASYMMETRIC` | `false` | Chỉ khi model hỗ trợ prefix/task param |
| `RERANK_BINDING` / `RERANK_MODEL` / `RERANK_BINDING_HOST` / `RERANK_BINDING_API_KEY` | – | Rerank provider |
| `RERANK_BY_DEFAULT` | `true` | Enable rerank mặc định |
| `MIN_RERANK_SCORE` | `0.0` | Lọc chunk sau rerank |
| `MAX_ASYNC_RERANK` / `RERANK_TIMEOUT` | fallback / `30` | Rerank concurrency/timeout |
| `VLM_PROCESS_ENABLE` | `false` | Bật multimodal |
| `LIGHTRAG_PARSER` | – | Route parser + chunker theo extension |
| `POSTGRES_USER/PASSWORD/DATABASE/HOST/PORT` | – | PG storage |

---

## 10. Mini checklist khi code

- [ ] `initialize_storages()` + `initialize_pipeline_status()` (2 bước bắt buộc)
- [ ] Embedding + dims LOCK (aibox v4, 1024) — config 1 chỗ env
- [ ] `addon_params["language"]="Vietnamese"` + `entity_type_prompt_file` profile
- [ ] Storage PG 4 loại + `CREATE EXTENSION vector`
- [ ] Chunker P qua `LIGHTRAG_PARSER` (server pipeline) — không dùng `ainsert` cho luật
- [ ] `ENTITY_EXTRACTION_USE_JSON=true`
- [ ] Rerank aibox + `min_rerank_score`
- [ ] `role_llm_configs` 3 vai
- [ ] Query: `mode="mix"`, `only_need_context=True`, `max_total_tokens=8-12k`
- [ ] Backup `pg_dump` trước upgrade; golden-set regression mỗi update
- [ ] `MAX_PARALLEL_INSERT` ≈ 1/3 `MAX_ASYNC_LLM`

---

## 11. ⚠️ Retrieval thực tế v1.5.6 — KHÔNG dùng PPR-Fusion, KHÔNG có BM25 (verify code + paper)

> **Paper LightRAG (EMNLP 2025) KHÔNG mô tả PPR-Fusion.** Cả bản arxiv v3 (aclanthology `2025.findings-emnlp.568`) đều mô tả retrieval là: **(i) LLM keyword extraction → (ii) vector matching** (ll_keywords ↔ entities, hl_keywords ↔ relations) **→ (iii) gather 1-hop neighbors** (tập `{vi | vi ∈ V ∧ (vi ∈ Nv ∨ vi ∈ Ne)}`). KHÔNG có Personalized PageRank, KHÔNG có score propagation. "PPR-Fusion" KHÔNG nằm trong paper LightRAG.
> **Code v1.5.6** (`operate.py`): thuần vector similarity + degree + 1-hop + weight. **KHÔNG có BM25** (grep toàn file = 0 kết quả).
> **BM25 đang được thiết kế cho LightRAG nhưng CHƯA merge** — issue #3198 (2026-06-04): đề xuất `SupportsHybridQuery` (dense + lexical fuse trong engine; PG `tsvector`+GIN / Qdrant / Milvus / OpenSearch), BM25 như **parallel seed path** vào graph bên cạnh vector path. Cần theo dõi nếu muốn dùng khi release.

**Thuật toán retrieval THỰC TẾ (4-stage):** `Search → Truncate → Merge chunks → Build context`

1. **Entity retrieval (local mode)** — `_get_node_data`:
   - `entities_vdb.query(ll_keywords)` → vector similarity search (top_k)
   - Gắn `rank` = **node degree** (bậc của đồ thị, KHÔNG phải pagerank)
   - `_find_most_related_edges_from_entities`: lấy toàn bộ cạnh của các entity đó (1-hop), sort theo `(rank, weight)` — **CHỈ 1-hop, KHÔNG lan truyền score qua graph**
2. **Relation retrieval (global mode)** — `_get_edge_data`:
   - `relationships_vdb.query(hl_keywords)` → vector similarity search, **giữ nguyên thứ tự similarity** (không sort lại theo weight)
   - Lấy entity hai đầu các cạnh này
3. **Chunk selection** — `_find_related_text_unit_from_entities/_from_relations`, chọn theo `kg_chunk_pick_method`:
   - `WEIGHT`: `pick_by_weighted_polling` — đếm **tần suất chunk xuất hiện** trong entity/relation (dedup + sort theo count)
   - `VECTOR`: `pick_by_vector_similarity` — similarity giữa query embedding và chunk embedding
4. **Naive (vector-only)** — `naive_query`: `chunks_vdb.query(query)` → token budget → LLM

### Hệ quả cho dự án (quan trọng)

- **Không có "lan truyền" ý nghĩa qua đồ thị** — chất lượng retrieval phụ thuộc: vector similarity (entity/relation embed) + 1-hop structure + weight/degree + chunk tần suất.
- **`top_k` càng quan trọng** vì không có PPR: tăng `top_k` (vd 60-80) để bù cho việc không lan truyền tới entity xa hơn.
- **Edge càng được trích đúng (chất lượng extraction) càng quan trọng** — relation description/keywords là dữ liệu vector search global. Đây là lý do `entity_type_prompt_file` + `ENTITY_EXTRACTION_USE_JSON` + `language="Vietnamese"` nâng chất lượng retrieval.
- **`kg_chunk_pick_method="VECTOR"`** (default) → chunk từ graph-align theo vector; `WEIGHT` → theo tần suất. Với văn bản luật, VECTOR thường tốt hơn khi query rõ ràng.
- Nếu muốn hành vi kiểu PPR (duyệt nhiều-hop theo mức quan trọng) → phải **tự implement ngoài** (vd: query nhiều vòng tăng `top_k`, hoặc tự chạy pagerank trên `PGTableGraphStorage` trước khi query).

---

## Liên kết

- Tài liệu liên quan: `.claude/plans/lightrag-overview.plan.md` (tổng quan + lỗi), `docs/research/library-research.md` (verify ADR-001), `docs/research/storage-pipeline-research.md`.
- Nguồn gốc: `HKUDS/LightRAG@v1.5.6` + docs trên repo. Khi upgrade version → **chạy lại bước verify tham số** vì API thay đổi nhanh.
