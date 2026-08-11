# Deep Research: MLOps A-Z tại Việt Nam/Đà Nẵng — Cloud, Platform, Best Practices cho RAG

*Ngày: 2026-08-10 | Dự án: rag-real-estate (LightRAG 1.5.6 + PostgreSQL + FastAPI + aibox) | Sources: 4 agents, ~120+ nguồn web | Confidence: High (đa nguồn hội tụ) / Medium (số liệu giá VN đơn nguồn / AI-synthesized — đã đánh dấu)*

> Báo cáo này trả lời 2 yêu cầu: (1) **"Tất cả các nguồn MLOps đẩy lên cloud — hạ tầng tốt nhất tại VN/Đà Nẵng hỗ trợ từ A-Z, nhất là RAG dễ deploy"**;
> (2) **"Tài liệu chú tâm những gì cần biết để MLOps tốt nhất và tối ưu nhất"**.
> Bổ sung cho (KHÔNG trùng): [guardrails-roles-mlops-research.md](./guardrails-roles-mlops-research.md) (bảo mật/RBAC/deploy ĐN cơ bản),
> [postgresql-lightrag-mlops.md](./postgresql-lightrag-mlops.md) (PG tuning + LightRAG-PG),
> [lightrag-params-reference.md](./lightrag-params-reference.md) (tham số v1.5.6), [model-stack-official-providers.md](./model-stack-official-providers.md).

---

## Executive Summary

1. **🔴 Tin mới làm thay đổi khuyến nghị trước đây (doc cũ chốt "Viettel #1")**: **FPT Cloud (FPT AI Factory) giờ là lựa chọn A-Z tốt nhất cho RAG production tại ĐN** — GPU H100 **$2.54/giờ (rẻ hơn cả RunPod $2.99)**, **DC Đà Nẵng có thật** (F-City, Ngũ Hành Sơn, hoàn thành 6/2024), managed PostgreSQL đủ engine, K8s GPU, Object Storage, template vLLM/Ollama sẵn. ([factory.fpt.ai](https://factory.fpt.ai/gpu-container), [fptcloud.com](https://fptcloud.com/en/pricing/), [FPT DC ĐN](https://fpt.vn/tin-tuc/fpt-cat-noc-trung-tam-du-lieu-tai-da-nang-9618.html))
2. **Viettel vẫn #1 cho budget MVP** (rẻ nhất compute CPU, DC ĐN) nhưng GPU thế hệ cũ (T4/A30/A100), managed PG cũ (12/15) → đủ dev/POC, không lý tưởng production LLM. **VNG/GreenNode** = sovereign AI mạnh (H100/GH200, MaaS Qwen3/Claude/GPT) nhưng giá GPU không công khai, không DC ĐN. ([viettel-cloud.com.vn](https://viettel-cloud.com.vn/cloud-gpu/), [greennode.ai](https://greennode.ai/))
3. **AWS/GCP/Azure KHÔNG có full region tại VN** — AWS Local Zone Hà Nội GA 19/6/2026 **không GPU, không RDS** → không đáp ứng use-case này; region gần nhất là Singapore/Thailand (latency 30-45ms từ ĐN). ([AWS Local Zone HN](https://aws.amazon.com/about-aws/whats-new/2026/06/aws-local-zones-hanoi-vietnam/))
4. **Cho dự án này (không cần GPU — LLM/embedding qua API aibox): "đừng adopt platform"** — stack OSS tối giản đủ (FastAPI container + LightRAG server + PG single-backend + Langfuse self-host + Evidently/Prometheus). TCO OSS chỉ thắng managed khi >50 production models. ([kodekloud](https://kodekloud.com/blog/top-mlops-tools/))
5. **pgvector là default đúng** cho <10k docs (~vài trăm nghìn vectors ≪ giới hạn 5-20M) — zero infra mới, ACID với metadata pháp lý. Qdrant/Milvus/Pinecone = thừa cho scale này. ([tensoria.fr](https://tensoria.fr/en/blog/vector-database-comparison))
6. **Dùng API thay vì self-host GPU tại VN** — GPU nội địa đắt (A30 ~$4.6k/tháng Viettel; H100 ~80.000đ/giờ), breakeven self-host ≈ >10M tokens/tháng; MVP legal chưa đạt. Nếu self-host: **vLLM** (793 tok/s vs Ollama 41; TGI vào maintenance 12/2025). ([Red Hat](https://developers.redhat.com/articles/2025/08/08/ollama-vs-vllm-deep-dive-performance-benchmarking), [pristren](https://pristren.com/blog/open-source-llm-production-guide/))
7. **3 lever cost lớn nhất** (effort-to-payoff): **prompt caching 41-80%** → **model tiering 40-60%** → **batch API ~50%**; rerank top 3-5 chunks thắng nhồi 20. ([bigdataboutique](https://bigdataboutique.com/blog/llm-cost-optimization-techniques), [arxiv 2601.06007](https://arxiv.org/abs/2601.06007v2))
8. **⚠️ Compliance cập nhật**: Nghị định 13/2023 đã được thay thế từ 01/01/2026 bởi **Luật Bảo vệ Dữ liệu cá nhân + NĐ 356/2025/NĐ-CP** (phạt tới 5% doanh thu) — *cần verify văn bản gốc trước khi dùng* (aibox synthesis, đơn nguồn).

---

## Phần 1. Cloud / Hạ tầng GPU tại Việt Nam & Đà Nẵng (2026)

### 1.1 Bảng so sánh 8 provider

| Provider | DC tại ĐN | GPU (loại) | Giá tham khảo (≈/tháng, trừ khi ghi khác) | Managed PG | Managed K8s | Note |
|---|---|---|---|---|---|---|
| **FPT Cloud / AI Factory** ⭐ A-Z | ✅ **F-City Ngũ Hành Sơn (6/2024)** | ✅ H100, H200 SXM5, B300 | GPU VM 1xH100 = **$2.54/h**; GPU Container 1xH200 = **$6.6/h**; Server từ $2.0/h | ✅ (PG/MySQL/Redis/Kafka/ClickHouse + TimescaleDB) | ✅ (MFKE, hỗ trợ GPU) | Toàn diện nhất; AI Factory (vLLM/Ollama notebook); monitoring/backup; S3-compatible |
| **Viettel Cloud** | ✅ Software Park, 02 Quang Trung, Hải Châu | ⚠️ T4/A30/A100 (cũ) | Cloud Server 4vCPU/4GB = **900K VND**; GPU T4 8vCPU/16GB = 8,7tr; A30 ~14,6-114,6tr (2 nguồn mâu thuẫn) | ✅ vDBS (PG **12 & 15**) | ✅ vOKS | Rẻ nhất CPU; PG version cũ; console kém dev-friendly |
| **VNG Cloud / GreenNode** | ❌ (HN + HCM + Bangkok, 6 AZ) | ✅ H100, GH200, L40S, A40, RTX 5090/4090 | **Giá GPU KHÔNG công khai** (EST: H100 ~80.000đ/h) | ✅ vDB | ✅ VKS 1.28-1.30 | Sovereign AI (ISO 27701); **MaaS** Qwen3/Claude/GPT; hướng enterprise/contract |
| **VNPT Cloud** | ✅ IDC An Đồn (Sơn Trà) | ⚠️ A100, T4 | Không công khai | ✅ | ✅ VKS | Nhà nước; phù hợp cơ quan nhà nước |
| **CMC Cloud** | ❌ (HN x2 + HCM) | ✅ Elastic GPU | Không công khai | ✅ RDS PG **15/16/17** + PITR + HA + Autoscale | ✅ + DevSecOps | PG version mới nhất; ~25% thị phần cloud nội địa; đắt/overkill cho MVP |
| **Bizfly (VCCorp)** | ❌ | ❌ Không tìm thấy GPU | VPS từ 95K VND | ⚠️ DB engine không rõ | ✅ BKE | Không phù hợp AI workload |
| **Nhan Hoa (Cloud365)** | Colo tại Viettel/FPT/CMC DC | ⚠️ GPU consumer (treo game — KHÔNG datacenter) | VPS NVMe từ 112K | ❌ | ❌ | KHÔNG phù hợp RAG enterprise |
| **AWS Local Zone Hà Nội** | ⚠️ Local Zone HN (parent = Singapore) | ❌ **KHÔNG GPU** (C7i/M7i/R7i) | Local Zone pricing | ❌ **KHÔNG RDS** | ✅ ECS/EKS | GA 19/6/2026; S3 One Zone-IA + EBS → data residency hạn chế; **chưa đủ cho RAG** |

Nguồn: [factory.fpt.ai](https://factory.fpt.ai/gpu-container) · [fptcloud.com/en/pricing](https://fptcloud.com/en/pricing/) · [docs.fptcloud.com](https://docs.fptcloud.com/vi/docs/intro/) · [ai-docs.fptcloud.com GPU VM billing](https://ai-docs.fptcloud.com/account/billing/tutorials/billing-policy/gpu-vm-billing) · [fptcloud PG engine](https://fptcloud.com/en/product/postgresql-database-engine-en/) · [viettel cloud-gpu](https://viettel-cloud.com.vn/cloud-gpu/) · [viettel cloud-server](https://viettel-cloud.com.vn/cloud-server/) · [viettel-idc](https://viettel-idc.com.vn/index.php/dich-vu/viettel-cloud-gpu.html) · [vngcloud](https://vngcloud.vn/en/product/gpu-cloud) · [greennode MaaS](https://docs.greennode.ai/ai-stack/model-as-a-service/model-pricing-list.md) · [vnpt](https://cloud.vnpt.vn/dich-vu) · [cmccloud RDS](https://cmccloud.vn/dich-vu/relational-database-service) · [bizfly](https://bizflycloud.vn/) · [nhanhoa cloud-gpu](https://nhanhoa.com/may-chu/cloud-gpu.html) · [AWS Local Zone HN](https://aws.amazon.com/about-aws/whats-new/2026/06/aws-local-zones-hanoi-vietnam/)

### 1.2 Cloud quốc tế — trạng thái & latency

- **AWS KHÔNG có full region tại VN** — trang Global Infrastructure (8/2026) chỉ liệt kê planned: Saudi Arabia, Chile. ([aws global-infra](https://aws.amazon.com/about-aws/global-infrastructure/))
- AWS có ở VN: **Local Zone Hà Nội GA 19/6/2026** (`ap-southeast-1-han-1a`, CPU-only) + **Direct Connect Hà Nội 16/12/2025** (1/10/100 Gbps). ([AWS whats-new DX](https://aws.amazon.com/about-aws/whats-new/2025/12/aws-direct-connect-hanoi/))
- Region ASEAN mới nhất: **ap-southeast-7 Thailand** (GA 8/1/2025, 3 AZ, AWS đầu tư >$5 tỷ). ([AWS blog Thailand](https://aws.amazon.com/blogs/aws/announcing-the-new-aws-asia-pacific-thailand-region/))
- **Latency ĐN → Singapore (ESTIMATE)**: HCM→SIN ~20-28ms; ĐN nằm giữa → ~30-45ms một chiều. Cloud nội địa: ~5-15ms từ ĐN. ([zenlayer](https://www.zenlayer.kr/global-network/performance/))

### 1.3 GPU hosting nội địa (ngoài cloud lớn) — ESTIMATE (blog thứ cấp)

| Provider | GPU | Giá | Loại |
|---|---|---|---|
| FPT AI Factory | H100 | **$2.54/h (~64.000đ/h)** | Enterprise, data trong nước |
| Sunteco | T4 ~15.000đ/h; RTX 4090 ~40.000đ; A100 80GB ~70.000đ; **H100 ~80.000đ/h** | pay-as-you-go VNĐ | Dev + enterprise |
| EzyCloudX | RTX 5090/3090 Ti... | từ ~5.000đ/h | Dev cá nhân |
| iRender | RTX 4090/3090 | ~7.500đ/h | Render 3D + AI |
| ThueGPU.vn | P40, RTX 3090, A6000 | gói tháng từ ~500K | Render/giả lập |

**So sánh GPU/giờ VN vs quốc tế**: H100 VN ~80.000đ/h ≈ **$3.2/h** vs RunPod H100 SXM **$2.99/h** vs **FPT $2.54/h** → **FPT rẻ hơn cả RunPod**; A100 SXM RunPod $1.49/h; RTX 4090 RunPod $0.69/h. NVIDIA H100 VN không đắt hơn nhiều nhưng dữ liệu nằm trong nước. ([sunteco](https://sunteco.vn/bang-gia-thue-gpu-cloud-viet-nam-2026/), [runpod](https://www.runpod.io/pricing))

### 1.4 Data residency & compliance (ảnh hưởng chọn cloud)

- **Nghị định 13/2023/NĐ-CP** (hiệu lực 1/7/2023): chuyển dữ liệu cá nhân ra nước ngoài cần Hồ sơ đánh giá tác động (Mẫu 06) gửi Bộ Công an trong 60 ngày. ([vanban.chinhphu.vn](https://vanban.chinhphu.vn/?docid=207759))
- **⚠️ Từ 01/01/2026 (ĐÃ QUA so với hôm nay)**: NĐ 13 được thay thế bởi **Luật Bảo vệ Dữ liệu cá nhân + NĐ 356/2025/NĐ-CP** — phạt tới **5% tổng doanh thu**; Luật Dữ liệu 60/2024 hiệu lực 1/7/2025 siết thêm cloud/AI. *Nguồn: aibox synthesis + blog pháp lý — bắt buộc đối chiếu văn bản gốc khi implement.* ([altas.vn](https://altas.vn/ban-tin-phap-ly-luat-bao-ve-du-lieu-ca-nhan))
- **Hệ quả dự án**: văn bản pháp luật = dữ liệu công (ít ràng buộc); NHƯNG nếu chatbot lưu PII mua giới/khách (tên, SĐT, hồ sơ) → **cloud nội địa (FPT/VNG/Viettel/CMC/VNPT) loại bỏ hoàn toàn rủi ro chuyển dữ liệu**; AWS/GCP/Azure (data Singapore) tạo nghĩa vụ compliance phức tạp.

### 1.5 Khuyến nghị cho rag-real-estate

| Nhu cầu | Chọn | Lý do |
|---|---|---|
| **MVP budget (không GPU — API aibox)** | **Viettel VPS tự quản PG** ~235-315K VND/tháng (xác nhận lại từ doc cũ) | Rẻ nhất; DC ĐN latency <5ms; PG chạy cùng box (PGTableGraphStorage plain PG) |
| **Production A-Z + GPU khi cần** | **FPT Cloud** (AI Factory) | DC ĐN + GPU rẻ nhất công khai + managed PG/K8s/Object Storage + template vLLM/Ollama |
| **Sovereign AI / MaaS / contract enterprise** | **VNG GreenNode** | H100/GH200 hiện đại, MaaS Qwen3/Claude/GPT, ISO 27701 |
| **Managed PG version mới (16/17) + PITR** | **CMC Cloud** | RDS PG 15/16/17 + PITR + HA (không DC ĐN) |
| **Tránh** | AWS Local Zone HN (không GPU/RDS), Bizfly (không GPU AI), Nhan Hoa (consumer GPU) | Không đáp ứng |

> ⚠️ Toàn bộ bảng giá VN từ AI-synthesized/đơn nguồn — **bắt buộc quote vendor** trước khi chốt. Giá VN biến động.

---

## Phần 2. MLOps Platform Landscape A-Z (2025-2026) — cho RAG

### 2.1 Self-hosted OSS stack — trạng thái & vai trò

Thị trường 2026 chia 3 camp: cloud-native suites (SageMaker/Vertex/Azure) · best-of-breed đa cloud (Databricks/W&B/Comet) · **OSS tự lắp ráp với MLflow là "open standard" trung tâm**. Xu hướng chủ đạo: **LLMOps (prompt versioning, eval, tracing, RAG observability) đã thành feature của MLOps**. ([ciopages](https://www.ciopages.com/buyer-guides/mlops-platform))

| Tool | Loại | Vai trò | Ghi chú 2025-2026 |
|---|---|---|---|
| **MLflow 3.x** | OSS (Apache) | Tracking + Model Registry + **GenAI eval/tracing/prompt mgmt** | MLflow Tracing + Unified Evaluation (LLM-as-judge) hỗ trợ RAG chains ([addepto](https://addepto.com/mlops-platforms-in-2026/)) |
| **Kubeflow + KServe** | OSS | K8s-native orchestration + serving | Cần platform engineering mạnh; KServe = CNCF serving standard (scale-to-zero, canary) ([kodekloud](https://kodekloud.com/blog/top-mlops-tools/)) |
| **Airflow / Prefect** | OSS | Orchestration | Prefect = "teams escaping Airflow pain"; Airflow vẫn thống trị jobs ([kodekloud](https://kodekloud.com/blog/top-mlops-tools/)) |
| **BentoML** | OSS + BentoCloud | Model packaging/serving | Dễ nhất laptop→prod; Yatai self-host phát triển chậm 2025 |
| **Ray Serve** | OSS | Distributed serving, multi-model graph | **Tốt nhất cho RAG pipeline** (embedding→rerank→LLM), autoscale theo queue; ops nặng |
| **vLLM** | OSS | LLM inference engine | Xem 2.4 |
| **Grafana/Prometheus + Langfuse + Evidently + Arize Phoenix** | OSS | Metrics + tracing + drift/eval | Xem 2.5 |

**Nguyên tắc vàng cho team nhỏ**: "**đừng adopt platform**" — 2-3 người thì MLflow (tracking) + deploy FastAPI/BentoML container + Prefect (nếu cần) là đủ. TCO OSS chỉ thắng managed khi **>50 production models**; dưới đó engineering time đắt hơn tiền platform. ([kodekloud](https://kodekloud.com/blog/top-mlops-tools/), [aiadvisorypractice](https://aiadvisorypractice.com/blog/mlops-platform-comparison-enterprise-buyers))

### 2.2 Managed MLOps / cloud AI — RAG native + giá

| Platform | RAG native | Giá tham khảo | Ghi chú |
|---|---|---|---|
| **Vertex AI RAG Engine** | ✅ managed pipeline, BYO vector DB | Agent Search $1.50/1k queries; storage $5/GB/tháng | Đang mid-rename vào "Gemini Enterprise Agent Platform" ([forage.ai](https://forage.ai/blog/rag-as-a-service-platforms/)) |
| **AWS Bedrock KB + SageMaker** | ✅ managed RAG, connectors | OpenSearch Serverless **$345-700/tháng min (kể cả idle)**; **Aurora pgvector $0.10/hr** | KB = "black box" hạn chế custom chunking/rerank ([technologymatch](https://technologymatch.com/blog/aws-bedrock-vs-azure-openai-vs-google-vertex-ai-enterprise-ai-comparison)) |
| **Azure ML + AI Search** | ✅ On Your Data, Foundry grounding | AI Search Basic $97/SU/tháng; S1 $324/SU/tháng | GigaOm enterprise readiness cao nhất 2.95/3; nhưng = 3 sản phẩm lắp ghép ([azumo](https://azumo.com/artificial-intelligence/ai-insights/mlops-platform-comparison-2026)) |
| **Databricks Mosaic AI** | ✅ Agent Framework + Vector Search + MLflow 3 eval | Usage-based (DBU) | Overkill project nhỏ |
| **Qwak (JFrog ML)** | ✅ LLM Model Library 1-click | Free 100 QPU; **$1.2/QPU** | Serving + RAG workflows ([qwak.com](https://www.qwak.com/)) |
| **Varia ML** | ✅ Eval chuyên RAG — grounding, hallucination 94%, deterministic (σ=0) | Free 50 evals; Lite $19; Starter $49; Business $249 | Domain legal/clinical/finance tuned; KHÔNG phải full MLOps (không serving) |
| **Galileo** | ✅ Eval + observability GenAI; Luna models distilled (-96% cost) | Free 5k traces; Pro $100/tháng; AWS MP $12,500/12mo | Mạnh nhất eval-to-guardrail ([galileo.ai/pricing](https://galileo.ai/pricing)) |

**Build vs Buy RAG**: managed $500-5.000/tháng (MVP) → $2.000-15.000 (production); build custom $30k-120k một lần + $300-2.000/tháng infra; **crossover ~100k-500k queries/tháng** thì build rẻ hơn. LLM API cost chiếm phần lớn ($1k-10k/tháng) — giống nhau dù build hay buy. ([inventiple](https://www.inventiple.com/blog/rag-pipeline-cost-2026))

### 2.3 Vector DB production (scale <10k docs)

| DB | Self/Managed | Scale hợp lý | Incremental | Cost (10M vec) | Phù hợp <10k docs? |
|---|---|---|---|---|---|
| **pgvector** | Cả hai | **<5-20M vectors**; HNSW recall 95%+; p50 8-15ms @1M | ✅ ACID cùng data | ~$50/tháng (trong PG sẵn có) | ✅ **Tối ưu nhất** — 0 infra mới |
| **Qdrant** | Cả hai | 10M-500M | ✅ | ~$100 | ⚠️ Thừa nếu đã có PG |
| **Weaviate** | Cả hai | 10M+ | ✅ | ~$120 | ⚠️ Hybrid search tốt nhưng v3→v4 breaking |
| **Pinecone** | Managed-only | Billion | ✅ | ~$300 | ⚠️ Lock-in cao nhất |
| **Milvus/Zilliz** | Cả hai | 100M-billion | ✅ | ~$180 | ❌ **Overkill** — cần K8s + etcd + object storage |
| **Elasticsearch** | Cả hai | Hybrid | ✅ | cao (RAM) | ❌ Thừa; RAGFlow mới cần |

**Đồng thuận nguồn**: "Under 5M vectors + đã có Postgres → **pgvector là default đúng**" — xóa 1 service khỏi ops surface, consistency vector+data trong cùng transaction (update 6 tháng không lo sync lệch). **Dự án này: <10k docs ≈ <30k chunks ≈ vài trăm nghìn vectors — pgvector dư sức, ngay cả IVFFlat cũng đủ; benchmark gate 50k entities vẫn xa giới hạn.** ([tensoria.fr](https://tensoria.fr/en/blog/vector-database-comparison), [tomodahinata](https://tomodahinata.com/en/blog/pgvector-vs-pinecone-qdrant-weaviate-milvus-vector-database-comparison-guide), [semantic.io](https://semantic.io/insights/vector-database-comparison-2026))
⚠️ Một benchmark vendor-adjacent thấy pgvector recall 94.2% vs Qdrant 99.1% @100k — với legal yêu cầu recall cao có thể cân nhắc, nhưng phải **re-benchmark trên data thật của dự án**. ([markaicode](https://markaicode.com/best/best-vector-database-for-enterprise-rag/))

### 2.4 LLM inference serving — self-host GPU vs API

| Engine | Kết quả benchmark | Ghi chú |
|---|---|---|
| **vLLM** | **793 tok/s vs Ollama 41** (A100, Llama-3.1-8B); P99 80ms vs 673ms; PagedAttention dùng 19-27% ít GPU mem hơn TGI | Standard production; HF khuyến nghị vLLM/SGLang cho deployment mới ([Red Hat](https://developers.redhat.com/articles/2025/08/08/ollama-vs-vllm-deep-dive-performance-benchmarking)) |
| **TGI** | — | **Vào maintenance mode 11/12/2025** — hết feature mới |
| **Ollama** | P99 24.7s @50 concurrent | Chỉ dev/single-user; không continuous batching |
| **SGLang** | 2.850 vs 2.400 tok/s (A100, DeepSeek-R1-32B) | Challenger; RadixAttention mạnh cho RAG/prefix reuse |

([gingerlabs](https://gingerlabs.ai/blog/vllm-vs-ollama-vs-tgi), [gigagpu](https://gigagpu.com/vllm-vs-tgi-vs-ollama/))

**API vs self-host — breakeven (ESTIMATE, nhiều nguồn khớp)**: self-host rẻ hơn khi **>500k-10M tokens/tháng**; dưới ~10M thì API kinh tế hơn tính cả engineering time. Ví dụ: 10M tokens/tháng → API ~$330/tháng (GPT-4o mini) vs self-host vLLM A10G ~$864 on-demand / ~$288 spot. ([honestradar](https://honestradar.com/vps-hosting/ai-inference-vps-comparison-2026/), [pristren](https://pristren.com/blog/open-source-llm-production-guide/))

**→ Khuyến nghị cho VN (GPU đắt)**: **Dùng API là chính** — embedding/rerank qua aibox (đã chốt), LLM qua API. Chỉ self-host GPU khi: (a) volume >10M tokens/tháng, HOẶC (b) bắt buộc data residency local. Nếu self-host: **vLLM** trên GPU thuê giờ (FPT $2.54/h rẻ nhất / Sunteco VNĐ), không thuê full-time.

### 2.5 RAG orchestrator — LightRAG vs phần còn lại

| Framework | Stars | Điểm mạnh | Điểm yếu | Deploy production |
|---|---|---|---|---|
| **LightRAG** | 14.6k | **Graph RAG rẻ nhất** (<100 tokens retrieval vs GraphRAG 610k); incremental update không rebuild; 6 modes; chạy CPU | Ecosystem nhỏ, emerging; guardrails yếu (không tenant isolation) | PoC → mid-market |
| **LangChain/LangGraph** | 105k | Orchestration lớn nhất, 1.0 LTS | Abstraction che phần cần tune; breaking changes | Default pick production |
| **LlamaIndex** | 40.8k | Retrieval quality tốt nhất, 160+ connectors | Ít mature agent | All scales |
| **Haystack** | 15-20k | Enterprise production nhất; eval best-in-class; YAML pipeline compliance | Community nhỏ | Mid → Enterprise |
| **RAGFlow** | 48.5k | Deep PDF/table parsing tốt nhất (hợp đồng pháp lý), UI sẵn | Nặng: ES + **min 32GB RAM** | Doc-heavy mid-market |

**LightRAG production — vấn đề thực tế có nguồn (GitHub issues)**:
- **PG deadlock khi nhiều server init index cùng lúc** (CREATE INDEX CONCURRENTLY) → init 1 instance trước. ([issue #2112](https://github.com/HKUDS/LightRAG/issues/2112))
- **PG không ổn định với file >10MB trên K8s** (primary-replica switchover không reconnect); fix PR #2562; dùng **PgBouncer port 6432**. ([issue #2561](https://github.com/HKUDS/LightRAG/issues/2561))
- **Postgres AGE rất chậm** (3-5 phút @3500 nodes) → khớp quyết định **PGTableGraphStorage (không AGE)** trong CLAUDE.md. ([issue #1277](https://github.com/HKUDS/LightRAG/issues/1277))
- PG write path đang hardening liên tục: PR #2742 (executemany KV upsert), PR #3169 (bound payload 16MiB/200 records). ([PR #3169](https://github.com/HKUDS/LightRAG/pull/3169))
- **Quan điểm**: "Single corpus Q&A + 1 provider → bỏ framework, provider SDK + vector client đủ, ship trong days"; orchestration overhead <4-10% latency, retrieval strategy quan trọng hơn framework. ([techsy](https://techsy.io/en/blog/best-rag-framework-2026))

---

## Phần 3. LightRAG 1.5.6 — Deploy production (checklist có citation)

### 3.1 Fact-check đối chiếu CLAUDE.md

- **lightrag-hku 1.5.6 = mới nhất** (publish 2026-08-06, Python ≥3.10); server: `pip install "lightrag-hku[api]"`. ([PyPI](https://pypi.org/project/lightrag-hku/))
- **PGTableGraphStorage CHÍNH THỨC trong 1.5.6** — release notes: "eliminates the dependency on Apache AGE... makes PostgreSQL the go-to all-in-one backend". ✅ Đúng quyết định đã chốt. ([v1.5.6 release](https://github.com/HKUDS/LightRAG/releases/tag/v1.5.6))
- **KHÔNG cần GPU** với API; **LiteLLM KHÔNG phải cách chuẩn** — dùng `LLM_BINDING=openai` + `LLM_BINDING_HOST` + `LLM_BINDING_API_KEY`. ([LightRAG-API-Server.md](https://github.com/HKUDS/LightRAG/blob/main/docs/LightRAG-API-Server.md))

### 3.2 Checklist 11 bước

1. **Pin version**: `pip install "lightrag-hku[api]"==1.5.6`.
2. **`.env` trong thư mục startup** (lightrag-server load mỗi lần start; env hệ thống ưu tiên hơn).
3. **LLM OpenAI-compatible (aibox)**: `LLM_BINDING=openai`, `LLM_MODEL=...`, `LLM_BINDING_HOST=<aibox /v1>`, `LLM_BINDING_API_KEY=...`; role-specific `EXTRACT_LLM_MODEL`/`KEYWORD_LLM_MODEL`/`QUERY_LLM_MODEL` (extract rẻ, query mạnh).
4. **Embedding LOCK dims**: `EMBEDDING_BINDING=openai`, `EMBEDDING_MODEL=text-embedding-v4`, `EMBEDDING_DIM=1024`, host aibox. ⚠️ "vector dimension phải định nghĩa lúc tạo bảng" — đổi = drop workspace + re-index TOÀN BỘ.
5. **Storage all-in-one PG**: `PGKVStorage` + `PGVectorStorage` + `PGTableGraphStorage` + `PGDocStatusStorage`.
6. **PG 14+ stock** (không AGE ext) + `CREATE EXTENSION vector;` (pgvector) — mixed vào image `pgvector/pgvector:pg18`.
7. **Env PG**: `POSTGRES_HOST/PORT/USER/PASSWORD/DATABASE`, `POSTGRES_WORKSPACE` (default `default`), `POSTGRES_MAX_CONNECTIONS=50` (**phải < PG max_connections**), SSL mode/cert.
8. **Tuning concurrency**: `MAX_ASYNC` (default 4), `MAX_PARALLEL_INSERT` (default 2, khuyến nghị ≈ MAX_ASYNC/3), `EMBEDDING_FUNC_MAX_ASYNC`, `EMBEDDING_BATCH_NUM`.
9. **Chạy**: `lightrag-server` (dev) HOẶC `lightrag-gunicorn --workers 4` (production multiprocess, **KHÔNG chạy Windows**); `--host 0.0.0.0 --port 9621 --timeout 150 --key <auth>`.
10. **Auth + reverse proxy**: `--key` cho auth; `LIGHTRAG_API_PREFIX` nếu multi-site sau nginx; `/health` check; rate limiting cho `/query` phải tự đặt ở proxy (LightRAG chỉ rate-limit login).
11. **Upgrade an toàn**: **"Stop every old writer before starting a new one"** — rolling restart với worker cũ còn chạy = failure case; không có data migration, sweep đầu tự reprocess doc treo.

Nguồn: [LightRAG-API-Server.md](https://github.com/HKUDS/LightRAG/blob/main/docs/LightRAG-API-Server.md) · [DockerDeployment.md](https://github.com/HKUDS/LightRAG/blob/main/docs/DockerDeployment.md) · [ProgramingWithCore.md](https://github.com/HKUDS/LightRAG/blob/main/docs/ProgramingWithCore.md) · [postgres_impl.py](https://github.com/HKUDS/LightRAG/blob/main/lightrag/kg/postgres_impl.py) · [k8s-deploy](https://github.com/HKUDS/LightRAG/tree/main/k8s-deploy)

### 3.3 Config PG chính xác (từ docs official + source)

```
LIGHTRAG_KV_STORAGE=PGKVStorage
LIGHTRAG_VECTOR_STORAGE=PGVectorStorage
LIGHTRAG_GRAPH_STORAGE=PGTableGraphStorage      # 1.5.6, KHÔNG cần AGE
LIGHTRAG_DOC_STATUS_STORAGE=PGDocStatusStorage
POSTGRES_HOST=...; POSTGRES_PORT=5432; POSTGRES_USER=...; POSTGRES_PASSWORD=...
POSTGRES_DATABASE=ai; POSTGRES_WORKSPACE=default
# Tuning (defaults postgres_impl.py)
POSTGRES_MAX_CONNECTIONS=50
POSTGRES_VECTOR_INDEX_TYPE=HNSW
POSTGRES_HNSW_M=16; POSTGRES_HNSW_EF=64
POSTGRES_CONNECTION_RETRIES=3; POSTGRES_CONNECTION_RETRY_BACKOFF=0.5; ..._MAX=60
POSTGRES_UPSERT_MAX_PAYLOAD_BYTES=16777216
POSTGRES_UPSERT_MAX_RECORDS_PER_BATCH=200
POSTGRES_DELETE_MAX_RECORDS_PER_BATCH=1000
```

> ⚠️ Chồng với [postgresql-lightrag-mlops.md](./postgresql-lightrag-mlops.md): 3 GUC tuning (maintenance_work_mem/work_mem/shared_buffers), bẫy ef_search bị PgBouncer transaction-mode nuốt, `MPI ≈ max_async_llm/3` — xem file đó cho chi tiết PG depth.

### 3.4 Bottlenecks + cách giải quyết

| Bottleneck | Bằng chứng | Giải pháp |
|---|---|---|
| **LLM concurrency thấp** (queue global, max_async 4) | issue #2264: 7h08m→1h45m nhờ tuning async; async=16 giảm 4h36m→11m | Tăng `MAX_ASYNC` theo capacity provider; monitor 429; ưu tiên query > merge > extract |
| **Embedding sync / batching** (merge re-embed ngay) | issue #1957 | `EMBEDDING_FUNC_MAX_ASYNC` + `EMBEDDING_BATCH_NUM` cao; deploy embedding local nếu API chậm |
| **Graph merge = bottleneck chính** (LLM call theo entity trùng) | issue #1957, #2425 | `FORCE_LLM_SUMMARY_ON_MERGE` default 8; tách file lớn → nhỏ; `MAX_SOURCE_IDS_PER_ENTITY/RELATION=300` |
| **NetworkX graph ops** (single-writer, reload full GraphML) | networkx_impl.py | ✅ **Dùng PGTableGraphStorage** — bỏ NetworkX hoàn toàn; batch ops sẵn (PR #2910) |
| **Concurrent insert race** (`ainsert` batch: "Document content not found") | issue #1968, #992 | Insert từng doc tuần tự / batch nhỏ; dùng server pipeline thay vì core; không dùng sync `insert()` trong async (deadlock) |
| **PG connection pool stacking** (pool riêng → too many connections) | PR #3103 review | Đã fix; kiểm tra `POSTGRES_MAX_CONNECTIONS` < PG max_connections |
| **JSON parse lỗi từ LLM** (400, không retry → chết pipeline) | issue #2794, PR #3144 | Nâng 1.5.6 (đã fix retry); `ENTITY_EXTRACTION_USE_JSON=true`; retry business-layer (PR #3242) |
| **LLM cache corrupted** (JSONDecodeError file cache) | issue #861, #2442 | Xóa `kv_store_llm_response_cache.json` khi hỏng; tool clear cache theo type |
| **Incremental update / xóa doc** (chunk + cache không dọn) | issue #2219, #2442 | Workflow: delete doc cũ → upload mới (cùng filename bị chặn nếu chưa delete); tách file nhỏ |

### 3.5 Serving / API đã verify

- **Endpoints**: `/query` (non-stream) + `/query/stream` (NDJSON, `include_references`, `include_chunk_content`, `only_need_context`); documents: `/documents`, `/documents/text`, `/documents/file`, `/documents/reprocess_failed`, `/documents/clear`; graphs `/graphs`; health `/health`; WebUI `/webui`. ([query_routes.py](https://github.com/HKUDS/LightRAG/blob/main/lightrag/api/routers/query_routes.py))
- **Ollama-compatible**: `/api/tags`, `/api/generate`, `/api/chat` — dùng cho Open WebUI; header `X-Accel-Buffering: no` cho nginx.
- **Concurrency**: mỗi worker gunicorn = 1 LightRAG instance (singleton, async); multi-worker + shared PG workspace hỗ trợ nhưng ingest phải theo pipeline scheduling protocol (single-writer invariant).

---

## Phần 4. 📘 Tài liệu chú tâm — MLOps best practices 2025-2026 cho RAG legal

> Đây là phần "những gì cần biết để MLOps tốt nhất và tối ưu nhất" — checklist 6 nhóm. [F] = fact có nguồn, [E] = estimate/khuyến nghị practice.

### 4.1 Lifecycle: CI/CD data + code + model

1. **[F] Version "cả RAG pipeline"** (chunking → embedding → retrieval → generation) chứ không phải 1 subsystem — chất lượng chunk/embedding ảnh hưởng output không thấy ở môi trường thấp. ([AWS SageMaker](https://aws.amazon.com/blogs/machine-learning/automate-advanced-agentic-rag-pipeline-with-amazon-sagemaker-ai/))
2. **[F] DVC (data) + MLflow (registry) + git commit hash** — chain: Production Model → MLflow Run → DVC commit → dataset; log `data_git_commit_id` mỗi run. ([AWS MLflow lineage](https://aws.amazon.com/blogs/machine-learning/end-to-end-lineage-with-dvc-and-amazon-sagemaker-ai-mlflow-apps/))
3. **[F] Golden-set regression = EVAL GATE trong CI, chặn merge khi regression**: mỗi PR eval golden set versioned vs baseline (MLflow tag `env=production`), block merge nếu category drop >0.05 hoặc overall <0.80; shadow 5% trước promote. ([LLM-Regression-Guard](https://github.com/prakhar-189/LLM-Regression-Guard))
4. **[F] Golden set immutable + versioned**; CI từ chối chạy eval nếu eval set thay đổi chưa commit. ([twilightcore](https://twilightcore.info/blog/cicd-for-ai-applications), [evidently](https://www.evidentlyai.com/llm-guide/rag-evaluation))
5. **[F] Tách regression theo layer** (retrieval recall@k / generation answer_similarity / system latency-cost-tokens) + confidence interval (paired bootstrap) — không so sánh 2 version trên population khác nhau. ([evalflow](https://dev.to/miftakhov/evalflow-a-regression-gate-for-rag-systems-in-ci-3919))
6. **[F] Deploy canary + auto-rollback trên SLO burn**: canary 10% → verify p95 latency <250ms, hallucination_rate <2% → tăng weight; GitOps + Argo Rollouts; feature flag cho instant rollback (giữ N-1). ([gitplumbers](https://gitplumbers.com/blog/the-rca-that-ate-our-weekend-data-lineage-for-ai-training-and-inference-that-act/)) — **cho RAG: đổi embedding/chunking = re-index → cần blue-green cho vector index** (chi tiết embedding migration trong [postgresql-lightrag-mlops.md](./postgresql-lightrag-mlops.md) §4).

### 4.2 RAG Evaluation

1. **[F] RAGAS faithfulness = claims được context hỗ trợ / tổng claims; không cần ground truth; LLM judge (mặc định) hoặc HHEM-2.1-Open (T5 classifier rẻ, "very efficient in production").** ([ragas faithfulness](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/))
2. **[F] Context Precision = mean precision@k (rank chunk liên quan lên đầu); Context Recall = claims retrieved được hỗ trợ (bắt buộc reference).** ([ragas precision](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/), [ragas recall](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/))
3. **[E] Golden set 100-200 câu, batch eval tuần; review thủ công 30 phút/tuần trace tệ nhất — HITL bắt edge case auto scoring bỏ sót.** ([talkingtech](https://talkingtech.io/rag-evaluation-and-observability-in-production-a-developers-guide/))
4. **[F] Ngưỡng CI tham khảo production**: faithfulness ≥0.80 (gate), answer_relevancy ≥0.75, context_recall ≥0.70, context_precision informational. **Legal set cao hơn** — xem 4.3. ([Claudient RAG-KB](https://github.com/Claudient/Claudient/blob/main/structures/rag-knowledge-base.md))
5. **[E] Legal: recall tối quan trọng hơn precision** ("missing a relevant authority worse than retrieving extra") NHƯNG "precision ở cảnh báo sai" cũng nguy hiểm; legal tools chuyên dụng (LexisNexis, Thomson Reuters) vẫn hallucinate 17-33%, failure mode chính = **misgrounding** (cite nguồn thật nhưng không hỗ trợ luận điểm). ([Stanford Law AI synthesis])
6. **[F] Legal hallucination cần structural check (entity + relation grounding), không chỉ semantic**: HalluGraph AUC 0.979 control / 0.89 generative legal; BERTScore gần chance 0.50-0.60 trên legal vì bỏ sót đổi entity "Plaintiff"→"Defendant", "2024"→"2025". ([arxiv 2512.01659](https://arxiv.org/html/2512.01659v1)) → **pattern cho layer anti-hallucination dự án: đối chiếu entity/điều luật/ngày trong trả lời với chunk nguồn.**

### 4.3 Monitoring & Observability

1. **[F] 4 telemetry layers bắt buộc: traces + metrics + eval scores (online+offline) + alerts** — thiếu 1 lớp = 1 class bug không phát hiện được. ([respan](https://www.respan.ai/articles/rag-observability))
2. **[F] 5 dashboards phủ ~90% debugging: traffic health / retrieval quality / generation quality / cost & latency / eval score trends.** ([respan](https://www.respan.ai/articles/rag-observability))
3. **[F] Online eval: sample 1-5% traffic, async (không block response), stratified (oversample high-stakes queries).** Confirmed regression alert: faithfulness 7-day rolling — **0.90 general chat / 0.96 cho regulated (legal)**; citation accuracy <0.92; cost/query >$0.40; retrieval latency p99 >800ms. ([respan](https://www.respan.ai/articles/rag-observability))
4. **[F] Observability overhead thực tế 15-30% latency nếu full-fidelity → tiered observability: full 7 ngày đầu, sau downsample thành aggregated metrics cho long-term.** ([talkingtech](https://talkingtech.io/rag-evaluation-and-observability-in-production-a-developers-guide/))
5. **[F] Chỉ 52% teams chạy offline eval, 37% online dù 89% có observability — "observability không có eval chỉ là log". Failed production traces = input tốt nhất cho offline eval (tự-healing loop).** ([langchain](https://www.langchain.com/resources/llm-monitoring-observability))
6. **[F] Embedding drift: classifier-based (ROC AUC ≥0.55) hơn PSI/KL trên high-dim; leading indicators: MRR -5% monitor / -10% investigate / -15% reindex; nearest-neighbor overlap 85-95% healthy, <70% degraded.** ⚠️ **Dự án: đổi embedding model = re-embed toàn bộ → track `embedding_model_version` trong metadata mỗi row.** ([evidently synthesis])

### 4.4 Cost Optimization (bảng lever)

| Kỹ thuật | Tiết kiệm | Nguồn | Áp dụng dự án |
|---|---|---|---|
| **Prompt caching** (system prompt tĩnh đầu, context động cuối; tránh timestamp/user-specific trong system prompt phá cache) | **41-80% API cost**; TTFT -13-31% | [arxiv 2601.06007](https://arxiv.org/abs/2601.06007v2) [F] | ✅ **Áp dụng ngay** — LightRAG system prompt/instruction ổn định, chunk cuối |
| **Model tiering / dynamic routing** (extract/rewrite rẻ, answer mạnh) | **40-60%** (RouteLLM: 95% GPT-4 quality với >85% cost cut) | [bigdataboutique](https://bigdataboutique.com/blog/llm-cost-optimization-techniques) [F/E] | ✅ Đúng kiến trúc EXTRACT (Haiku) vs QUERY (Sonnet) |
| **Batch API** (golden-set eval, re-embed, regression 6 tháng) | ~50% | [bigdataboutique](https://bigdataboutique.com/blog/llm-cost-optimization-techniques) [F] | ✅ Regression chạy batch |
| **Semantic caching** (query tương tự ≥0.95 → cached) | 90%+ hit [E vendor]; 68% fewer calls [F] | [frenxt](https://www.frenxt.com/research/how-to-reduce-llm-costs) [E] | ✅ Nên làm — mua giới hỏi lặp |
| **Rerank top 3-5 chunks thắng nhồi 20** | Giảm token/query đáng kể | [bigdataboutique](https://bigdataboutique.com/blog/llm-cost-optimization-techniques) [E] | ✅ Kết hợp max_total_tokens 8-12k |
| **Retrieval depth routing** (đơn giản → light, phức tạp → heavy) | 26% billed tokens; 34% latency | [arxiv 2606.02581](https://arxiv.org/html/2606.02581) [F] | ⚠️ Tầng 2 — LightRAG 5 modes, route theo intent |
| **Chunk-KV cache (vLLM)** | 51%/75% GPU compute | [arxiv 2502.15734](https://arxiv.org/html/2502.15734) [F] | ❌ Không áp dụng (dùng API) |
| **Prompt compression (CAPC)** | 49-90% | [arxiv 2607.15516](https://arxiv.org/html/2607.15516) [F] | ⚠️ Tầng 2 khi token lớn |

> ⚠️ RAG caveat: prefix caching kém hiệu quả với RAG (chunk order đổi theo query — exact prefix chỉ khớp 8% requests); vì vậy **system prompt tĩnh trước, context động sau** là bắt buộc. ([arxiv 2502.15734](https://arxiv.org/html/2502.15734))

### 4.5 Guardrails & Safety legal (tóm tắt — chi tiết ở [guardrails-roles-mlops-research.md](./guardrails-roles-mlops-research.md))

- **[F] Layered guardrails input + output + post-response; Bedrock contextual grounding threshold 0.7 (filters >75% hallucinated responses [vendor claim]).** ([AWS Bedrock Guardrails](https://aws.amazon.com/blogs/machine-learning/build-responsible-ai-applications-with-amazon-bedrock-guardrails/))
- **[F] Grounding threshold 0.70-0.85, escalate/halt khi dưới; confidence domain-calibrated 0.75-0.90 validated 500+ queries; HITL checkpoint cho high-stakes + audit log tamper-evident (EU AI Act Art. 11/12/14).** ([crprotocol CRP-SPEC-033](https://crprotocol.io/spec/CRP-SPEC-033-safety-control-plane/))
- **[F] Citation API: recall accuracy +15% [vendor]; dự án dùng aibox qwen (không Anthropic) → xây citation grounding riêng: span trích dẫn phải nằm trong chunk nguồn.** ([claude.com citations](https://claude.com/blog/introducing-citations-api))
- **[F] LLM-as-judge hallucination detection: prompt chia bước + bắt buộc quote context cho mỗi claim + structured output — prompt design quan trọng hơn model architecture.** ([datadog](https://www.datadoghq.com/blog/ai/llm-hallucination-detection/))

### 4.6 Security RAG production

- **[F] OWASP Top 10 LLM 2025**: LLM01 Prompt Injection (indirect qua chunk = đặc biệt rủi ro RAG), LLM02 Sensitive Info Disclosure, **LLM08 Vector & Embedding Weaknesses (Retrieval Poisoning — attacker nhúng doc độc)**, LLM09 Misinformation, LLM10 Unbounded Consumption (cost DoS). ([OWASP 2025](https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/))
- **[F] Mitigation retrieval poisoning: validate nguồn ingest (trusted providers), sanitize doc trước embed (bắt hidden text/formatting), permission-aware vector store, immutable retrieval logs, audit phát hiện doc retrieve bất thường.** ([OWASP synthesis])
- **[F] Least privilege + permission-aware retrieval** (user chỉ retrieve được data được phép; logical partition chống cross-tenant leakage) — khớp PG RLS đã chốt. ([OWASP](https://engagedscholarship.csuohio.edu/cgi/viewcontent.cgi?article=1548&context=enece_facpub))
- **[F] Secrets: env + vault + secret scanning CI; resilience: retries + circuit breakers + rate limiting + token budget.** ([production-rag-service](https://github.com/e1washere/production-rag-service))
- **[F] Trace lineage là security: stamp mọi artifact git_sha/data_version/template_version/model_version; OTel trace_id xuyên request → vector store → output.** ([gitplumbers](https://gitplumbers.com/blog/the-rca-that-ate-our-weekend-data-lineage-for-ai-training-and-inference-that-act/))

---

## Phần 5. Stack MLOps ĐỀ XUẤT cho rag-real-estate (tổng hợp)

**Context quyết định**: <10k docs + update 6 tháng/lần + LLM/embedding/rerank qua API aibox + LightRAG 1.5.6 + PG single-backend + FastAPI 1 trang. Không train model, không self-host GPU.

| Layer | Chọn | Lý do (nguồn) |
|---|---|---|
| Orchestrator RAG | **LightRAG 1.5.6** (đã lock ADR-001) | Incremental update; retrieval <100 tokens; PGTableGraphStorage official 1.5.6 |
| Vector + data | **PostgreSQL single-backend** (pgvector + PGTableGraphStorage) | <10k docs ≪ giới hạn pgvector; 0 infra mới; ACID metadata pháp lý ([tensoria](https://tensoria.fr/en/blog/vector-database-comparison)) |
| Embedding/Rerank/LLM | **API aibox + Anthropic** | GPU VN đắt; breakeven self-host >10M tokens ([pristren](https://pristren.com/blog/open-source-llm-production-guide/)) |
| Serving API | **FastAPI thuần + Docker Compose / 1 VPS** | "Đừng adopt platform" cho team nhỏ ([kodekloud](https://kodekloud.com/blog/top-mlops-tools/)) |
| Orchestration 6 tháng | **Script + cron/systemd** (Prefect nếu cần UI) | Airflow/Kubeflow overkill cho 2 job/năm |
| Monitoring + Eval | **Langfuse self-host** (tracing/cost) + **Evidently** (drift/CI eval) + **Prometheus/Grafana** (metrics) + **RAGAS** (golden set CI) | OSS full, self-host data residency ([respan](https://www.respan.ai/articles/rag-observability), [talkingtech](https://talkingtech.io/rag-evaluation-and-observability-in-production-a-developers-guide/)) |
| Registry | **KHÔNG cần MLflow MVP** — version prompt/chunking qua workspace + git | Không train model; thêm MLflow 3.x khi cần trace/eval chính thức ([gravitydevops](https://gravitydevops.com/best-mlops-tools-platforms-2026/)) |

**Lý do KHÔNG chọn managed cloud AI** (Vertex RAG Engine / Bedrock KB / Azure AI Search): $500-2.000+/tháng tầng MVP ([inventiple](https://www.inventiple.com/blog/rag-pipeline-cost-2026)), lock-in cloud, "black box" chunking/rerank ([forage.ai](https://forage.ai/blog/rag-as-a-service-platforms/)), data pháp lý nhạy cảm → giữ infra tự quản + data residency VN.

**Rủi ro cần tracking**: LightRAG PG write path đang hardening (theo dõi PR #3169/#2742); single-writer PG (init 1 instance, issue #2112); benchmark gate chuyển Neo4j khi >10k docs; PgBouncer nếu K8s + file >10MB (issue #2561).

**Thresholds tóm tắt cho dự án legal**:
- Faithfulness gate: **≥0.90-0.96** (regulated, không 0.80 default) ([respan](https://www.respan.ai/articles/rag-observability))
- Confidence: HIGH ≥2 nguồn + rerank ≥0.8 + grounding pass (ADR-001 giữ nguyên)
- Alert: faithfulness floor 0.96 7-day rolling; citation accuracy <0.92; cost/query >$0.40; p99 >800ms
- CI: PR = faithfulness + answer relevancy subset; nightly = full 4 metric; block merge khi regression >0.05

---

## Key Takeaways

1. **Hạ tầng A-Z tại ĐN 2026**: **FPT Cloud #1** (DC ĐN + GPU H100 $2.54/h rẻ nhất công khai + managed PG/K8s/Object Storage); **Viettel #1 budget MVP** (VPS tự quản PG ~235-315K, DC ĐN); VNG GreenNode = sovereign AI. AWS Local Zone HN không đủ (không GPU/RDS).
2. **Đừng adopt MLOps platform** cho dự án này — stack OSS tối giản (LightRAG server + PG + FastAPI + Langfuse + Evidently + Prometheus) đủ, đúng quy mô <10k docs.
3. **pgvector = vector DB đúng đắn** — dư sức scale, 0 infra mới, ACID với metadata pháp lý.
4. **Dùng API (aibox/Anthropic) thay vì self-host GPU tại VN** — GPU nội địa đắt, breakeven >10M tokens/tháng.
5. **3 lever cost**: prompt caching (41-80%) → model tiering (40-60%) → batch (~50%); rerank top 3-5.
6. **Legal MLops bắt buộc**: faithfulness ≥0.96, structural anti-hallucination (HalluGraph pattern — đối chiếu entity/điều luật/ngày), HITL high-stakes, audit log.
7. **⚠️ 2 verify bắt buộc trước khi dùng**: (a) giá cloud VN bằng quote vendor (AI-synthesized); (b) NĐ 13/2023 → Luật BV DLCN + NĐ 356/2025 từ 01/01/2026 (đơn nguồn).

## Methodology

Searched 4 sub-question song song (4 research agents, ~40+ queries, ~120 nguồn web): (1) cloud providers VN/ĐN + GPU + compliance; (2) MLOps platform landscape cho RAG (OSS vs managed, vector DB, inference, orchestrator); (3) LightRAG 1.5.6 production deploy (repo/docs/issues); (4) MLOps best practices 2025-2026 (lifecycle, eval, monitoring, cost, guardrails, security). Ưu tiên official docs/arxiv/GitHub > blog > vendor. Mọi số liệu giá VN đánh dấu ESTIMATE. Tổng hợp chồng với 4 research doc đã có trong `docs/research/`.

## Sources chính (đầy đủ xem trong từng phần)

1. [FPT GPU Container](https://factory.fpt.ai/gpu-container) — giá GPU rẻ nhất công khai VN
2. [FPT Cloud pricing](https://fptcloud.com/en/pricing/) — compute/managed services
3. [FPT DC Đà Nẵng](https://fpt.vn/tin-tuc/fpt-cat-noc-trung-tam-du-lieu-tai-da-nang-9618.html) — DC F-City hoàn thành 6/2024
4. [Viettel Cloud GPU](https://viettel-cloud.com.vn/cloud-gpu/) — GPU + giá
5. [VNG GPU Cloud](https://vngcloud.vn/en/product/gpu-cloud) — H100/GH200/L40S
6. [GreenNode MaaS pricing](https://docs.greennode.ai/ai-stack/model-as-a-service/model-pricing-list.md) — model as a service
7. [CMC RDS PostgreSQL](https://cmccloud.vn/dich-vu/relational-database-service) — PG 15/16/17 + PITR
8. [AWS Local Zones Hanoi](https://aws.amazon.com/about-aws/whats-new/2026/06/aws-local-zones-hanoi-vietnam/) — không GPU/RDS
9. [AWS Global Infrastructure](https://aws.amazon.com/about-aws/global-infrastructure/) — chưa có full region VN
10. [Nghị định 13/2023](https://vanban.chinhphu.vn/?docid=207759) — chuyển dữ liệu xuyên biên giới
11. [LightRAG API Server docs](https://github.com/HKUDS/LightRAG/blob/main/docs/LightRAG-API-Server.md) — deploy chuẩn + env
12. [LightRAG v1.5.6 release](https://github.com/HKUDS/LightRAG/releases/tag/v1.5.6) — PGTableGraphStorage official
13. [LightRAG postgres_impl.py](https://github.com/HKUDS/LightRAG/blob/main/lightrag/kg/postgres_impl.py) — config PG defaults
14. [LightRAG issue #2112](https://github.com/HKUDS/LightRAG/issues/2112) — PG deadlock init index
15. [kodekloud MLOps tools](https://kodekloud.com/blog/top-mlops-tools/) — "đừng adopt platform" cho team nhỏ
16. [Red Hat vLLM vs Ollama](https://developers.redhat.com/articles/2025/08/08/ollama-vs-vllm-deep-dive-performance-benchmarking) — benchmark 793 vs 41 tok/s
17. [tensoria vector DB comparison](https://tensoria.fr/en/blog/vector-database-comparison) — pgvector default <5M vectors
18. [bigdataboutique LLM cost](https://bigdataboutique.com/blog/llm-cost-optimization-techniques) — 3 lever cost
19. [arxiv 2601.06007](https://arxiv.org/abs/2601.06007v2) — prompt caching 41-80%
20. [arxiv 2512.01659](https://arxiv.org/html/2512.01659v1) — HalluGraph legal hallucination
21. [respan RAG observability](https://www.respan.ai/articles/rag-observability) — thresholds + dashboards
22. [OWASP Top 10 LLM 2025](https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/) — LLM08 retrieval poisoning
23. [inventiple RAG cost](https://www.inventiple.com/blog/rag-pipeline-cost-2026) — build vs buy crossover
24. [pristren OSS LLM production](https://pristren.com/blog/open-source-llm-production-guide/) — breakeven API vs self-host
25. [RunPod pricing](https://www.runpod.io/pricing) — so sánh GPU quốc tế
