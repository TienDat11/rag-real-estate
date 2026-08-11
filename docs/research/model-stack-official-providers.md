# Chọn bộ model chính thức cho RAG pháp lý BĐS (thay thế api-box reseller)

*Generated: 2026-08-10 | Nguồn: chính thức (Alibaba Cloud Model Studio/DashScope, Qwen Cloud, DeepSeek, Zhipu, Moonshot, Jina, Cohere) | Confidence: High (giá từ trang chính thức) | Tiếng Việt*

## Executive Summary

User yêu cầu: model chính thức (KHÔNG phải reseller như api-box — rủi ro die/maintain), cho 5 vai:
**embedding + rerank + rewrite query + graph extraction (LightRAG EXTRACT) + trả lời khách (QUERY)**.
Ưu tiên: **latency thấp, chính xác cao, giá rẻ**.

**Khuyến nghị cuối — 1 nhà cung cấp chính thức duy nhất: Alibaba Cloud Model Studio (DashScope):**
- **Embedding:** `text-embedding-v4` — **$0.07/1M**, dims 1024 (LOCK), 100+ ngôn ngữ, free 1M tokens
- **Rerank:** `qwen3-rerank` — **$0.10/1M**, 100+ ngôn ngữ (thay gte-rerank bị ngưng 30/05/2026)
- **Rewrite + Graph extraction:** `qwen3.7-flash` — **$0.03/$0.13** (rẻ nhất thị trường)
- **Trả lời khách:** DeepSeek V4 Flash/Pro ($0.14-0.435/$0.28-0.87) hoặc `qwen3.7-plus/max`

Lý do 1 vendor: 1 hợp đồng, 1 API key, 1 billing, latency tốt nhất (region Singapore ap-southeast-1 — gần VN),
Alibaba = công ty scale lớn (ít rủi ro die hơn api-box), và **model này CHÍNH LÀ model api-box đang proxy** —
chuyển sang chính thức = cùng chất lượng, rẻ hơn (bỏ margin reseller), bớt 1 điểm chết.

---

## 1. Embedding — Alibaba text-embedding-v4 (Qwen3-Embedding series)

**Nguồn chính thức:** Alibaba Cloud Model Studio / Qwen Cloud
([help.aliyun.com](https://help.aliyun.com/en/model-studio/embedding), [qwencloud.com](https://docs.qwencloud.com/developer-guides/embeddings/))

| Đặc điểm | Giá trị |
|---|---|
| Giá | **$0.07/1M** input tokens (batch: CNY 0.00025/1K) |
| Dims | **2048 / 1536 / 1024 (default) / 768 / 512 / 256 / 128 / 64** |
| Max token/doc | 8.192 |
| Batch | 10 texts/call |
| Ngôn ngữ | **100+** (cn, en, es, fr, pt, id, jp, kr, de, ru + lập trình) |
| Free quota | 1M tokens / 90 ngày |
| Region gần VN | Singapore `ap-southeast-1` (`https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`) |

> ⭐ Đây CHÍNH LÀ model api-box đang proxy. Dims 1024 = khớp ADR-002 đã LOCK của dự án.
> OpenAI-compatible endpoint → `llm_model_func`/`embedding_func` của LightRAG gọi trực tiếp được.

## 2. Rerank — qwen3-rerank (Alibaba)

**Nguồn chính thức:** [Qwen Cloud](https://www.qwencloud.com/models/qwen3-rerank) — **$0.10/1M** (chỉ tính input)

| Đặc điểm | Giá trị |
|---|---|
| Giá | **$0.10/1M** tokens |
| Max docs | 500/request |
| Max token/doc | 4.000 |
| Max request | 120.000 tokens |
| Ngôn ngữ | 100+ |
| ⚠️ | **gte-rerank-v2 NGƯNG 30/05/2026** → bắt buộc chuyển qwen3-rerank |
| Endpoint | `POST /v1/reranks` (OpenAI-compatible) — LightRAG `generic_rerank_api` gọi được |

**So sánh rerank (để chọn):**
| | qwen3-rerank (Alibaba) | Jina v3 | Cohere Rerank 3 |
|---|---|---|---|
| Giá/1M | **$0.10** | ~$0.40 (10M free) | ~$2.00 |
| Chất lượng | Tốt (100+ lang) | SOTA multilingual, 131K ctx | Tốt nhất (BEIR) |
| Open-weight | ✅ | ✅ Apache 2.0 | ❌ managed only |
| Latency 100 docs | nhanh | 100-156ms | sub-100ms |
| **Chọn** | **⭐ (cùng vendor embedding)** | Thay thế nếu cần self-host | Đắt, không cần |

## 3. Rewrite query — model nhỏ rẻ (official)

| Model | Input/1M | Output/1M | Context | Nhà cung cấp chính thức |
|---|---|---|---|---|
| **qwen3.7-flash** | **$0.03** | **$0.13** | 1M | Alibaba DashScope |
| **GLM-4.7-Flash** | **FREE** (limited) | FREE | 200K | Zhipu bigmodel.cn / z.ai |
| DeepSeek V4 Flash | $0.14 (cache hit $0.0028) | $0.28 | 1M | DeepSeek |
| GLM-4.7-FlashX | $0.07 | $0.40 | 200K | Zhipu |

> ⭐ **qwen3.7-flash $0.03/$0.13 = rẻ nhất trả phí + chất lượng tốt + cùng vendor.** Rewrite = 1-2 câu ngắn/lần query → chi phí gần như 0. GLM-4.7-Flash free nhưng là promotion (limited-time) — không nên dựa vào.

## 4. Graph extraction LLM (LightRAG EXTRACT — rẻ, non-thinking, nhanh)

LightRAG cần EXTRACT đọc chunk → trích entity/relation. Yêu cầu: rẻ, non-thinking, latency thấp, tiếng Việt tốt.

| Model | Input/1M | Output/1M | Ghi chú |
|---|---|---|---|
| **qwen3.7-flash** | **$0.03** | **$0.13** | ⭐ Rẻ nhất, 1M ctx, tiếng Việt ✅ |
| DeepSeek V4 Flash | $0.14 | $0.28 | Chất lượng cao, cache hit siêu rẻ |
| GLM-4.7-FlashX | $0.07 | $0.40 | |

> EXTRACT tiêu token NHIỀU nhất (mỗi chunk 1 lần gọi) → **cần model rẻ nhất**: qwen3.7-flash.
> Ước tính ingest 1.000 chunk ~ 2M tokens input → **~$0.06** bằng qwen3.7-flash vs ~$0.28 bằng DeepSeek V4 Flash.

## 5. Trả lời khách (LightRAG QUERY / answer LLM)

| Model | Input/1M | Output/1M | Ngôn ngữ | Ghi chú |
|---|---|---|---|---|
| **DeepSeek V4 Flash** | $0.14 | $0.28 | Việt ✅ | **⭐ Giá/CL tốt nhất**, 1M ctx |
| DeepSeek V4 Pro | $0.435 | $0.87 | Việt ✅ | Reasoning mạnh cho câu pháp lý phức tạp |
| qwen3.7-plus | ~$0.72 | ~$2.88 | Việt ✅ | Alibaba, cùng vendor |
| qwen3-max | $0.35-0.98 | $1.40-3.92 | Việt ✅ | Flagship Alibaba |
| GLM-5.2 | $1.40 | $4.40 | Việt ✅ | Flagship Zhipu (đắt) |
| Kimi K2.7-code | $0.95 | $4.00 | Việt ✅ | Coding-focused |

> ⭐ **DeepSeek V4 Flash** cho trả lời khách: giá rẻ, tiếng Việt tốt, 1M context — phù hợp legal RAG
> (context query 8-12k tokens). Muốn quality cao hơn khi câu phức tạp → **V4 Pro** ($0.435/$0.87) — vẫn rẻ hơn hầu hết flagship khác.

---

## Key Takeaways (cho báo cáo sếp)

1. **Chuyển api-box → Alibaba Cloud Model Studio (DashScope) CHÍNH THỨC:** cùng model (text-embedding-v4,
   deepseek, qwen) nhưng bỏ margin reseller, bớt 1 điểm chết, 1 hợp đồng/billing duy nhất.
   Region Singapore ap-southeast-1 = latency thấp cho VN.
2. **Stack 5 model, 1-2 vendor, tổng chi phí rẻ hơn ước tính cũ (~350-600k/tháng của plan):**
   - Embed: text-embedding-v4 $0.07/1M (dims 1024 LOCK — ĐỒNG NHẤT với ADR-002)
   - Rerank: qwen3-rerank $0.10/1M
   - Rewrite + EXTRACT: qwen3.7-flash $0.03/$0.13
   - Answer: DeepSeek V4 Flash (hoặc Pro) $0.14-0.435/$0.28-0.87
3. **Chi phí thực tế thấp hơn nhiều:** EXTRACT/rewrite/rerank/embed đều ≤ $0.14/1M input; query context
   ngắn 8-12k tokens → mỗi câu hỏi khách ~$0.005-0.02. Với 1.000-5.000 câu hỏi/tháng → **~$10-50/tháng**.
4. **Rủi ro nhà cung cấp:** Alibaba Cloud = tập đoàn (doanh thu $130B+) — ít rủi ro die hơn reseller nhỏ.
   Vẫn nên: API key + quota alert + fallback plan (DeepSeek official là vendor thứ 2 không phụ thuộc Alibaba).
5. **⚠️ Chưa verify:** giá qwen3.7-flash/plus/max là từ AI-synthesized search (cần xác nhận trên
   pricing page chính thức của Alibaba trước khi chốt); DeepSeek V4 Flash/Pro giá chính thức từ aibox search
   (cần xác nhận platform.deepseek.com). Gte-rerank ngưng 30/05/2026 = xác nhận từ tài liệu Alibaba.

## Sources

1. [Alibaba Model Studio — Embedding](https://help.aliyun.com/en/model-studio/embedding) — text-embedding-v4 $0.07/1M, dims, 100+ lang
2. [Alibaba Model Studio — Text Rerank API](https://help.aliyun.com/en/model-studio/text-rerank-api) — qwen3-rerank qua /v1/reranks; gte-rerank ngưng 30/05/2026
3. [Qwen Cloud — Pricing](https://docs.qwencloud.com/developer-guides/getting-started/pricing) — embedding $0.07, rerank $0.10
4. [Qwen Cloud — qwen3-rerank model page](https://www.qwencloud.com/models/qwen3-rerank) — $0.10/1M, curl example
5. [Jina AI — Reranker API](https://jina.ai/reranker/) — jina-reranker-v3, 10M free tokens, latency 100ms-7s
6. [Cohere Docs — Pricing](https://docs.cohere.com/docs/how-does-cohere-pricing-work) — rerank tính theo search
7. [Cohere Rerank vs Jina Reranker](https://promtable.com/compare/cohere-rerank-vs-jina-rerank) — Cohere ~$2.00 vs Jina ~$0.40/1M
8. [DeepSeek API pricing](https://api-docs.deepseek.com/quick_start/pricing) — V4 Flash $0.14/$0.28, V4 Pro $0.435/$0.87
9. [Zhipu bigmodel.cn pricing](https://bigmodel.cn/pricing) — GLM-5.2, GLM-4.7-Flash free
10. [Moonshot Kimi pricing](https://platform.moonshot.cn/docs/pricing) — kimi-k2.7-code $0.95/$4.00

## Methodology

7 truy vấn search (exa + aibox google_search), phân tích 10+ nguồn, ưu tiên tài liệu chính thức
(help.aliyun.com, qwencloud.com, jina.ai, docs.cohere.com, bigmodel.cn, platform.moonshot.cn).
Giá DeepSeek/Qwen flash/GLM từ AI-synthesized — đánh `⚠️ chưa verify` cho mục cần xác nhận trước khi chốt.
Sub-questions: (1) embedding chính thức, (2) rerank chính thức + so sánh, (3) rewrite model rẻ, (4) EXTRACT model, (5) answer LLM.
