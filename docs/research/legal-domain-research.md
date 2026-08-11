# Nghiên cứu Domain Nghiệp vụ: RAG Pháp lý Bất động sản "Đất cầm" (VN)

*Ngày: 2026-08-09 | Loại: Research domain (không code) | Nguồn: deep-research skill (web search đối chiếu nhiều nguồn luật, công ty luật, cơ quan nhà nước)*
*Mục đích: model hóa domain → taxonomy + golden set + hướng dẫn ingest cho MVP RAG pháp lý bất động sản*

---

## 0. Tóm tắt điều hành (Executive Summary)

- **"Đất cầm" = 2 trường hợp pháp lý hoàn toàn khác nhau**: (1) **thế chấp ngân hàng** — hợp pháp, được Luật Đất đai 2024 + BLDS 2015 quy định rõ, có quy trình mua bán chuẩn (thỏa thuận 3 bên → giải chấp → công chứng → sang tên); (2) **cầm cố tư nhân/giấy tay** — **KHÔNG được luật ghi nhận** (Luật Đất đai không liệt kê "cầm cố" là quyền của người sử dụng đất; tòa án nhiều bản án tuyên hợp đồng cầm cố QSDĐ vô hiệu theo Điều 123 BLDS). Đây là điểm mấu chốt: chatbot phải PHÂN BIỆT được hai khái niệm này, không gộp chung.
- **Khung pháp lý nền đã đổi toàn bộ từ 2024**: Luật Đất đai 2024 (31/2024/QH15), Luật Kinh doanh BĐS 2023 (29/2023/QH15, hiệu lực 01/08/2024), Luật Nhà ở 2023, Nghị định 101/2024/NĐ-CP (sổ đỏ/sổ hồng), Nghị định 96/2024/NĐ-CP. Metadata `effective_date`/`status` là BẮT BUỘC để không trả văn bản hết hiệu lực (Luật Đất đai 2013 phải đánh dấu "hết hiệu lực").
- **Rủi ro cao nhất trong domain**: (a) giao giá trị tiền đặt cọc/thanh toán, (b) giải chấp/trả nợ ngân hàng, (c) giấy tay/ủy quyền không công chứng, (d) tranh chấp/kê biên/ngăn chặn. Mọi câu trả lời đụng các keyword này → human review bắt buộc.

Nguồn chính: [1] Sở Tư pháp Thừa Thiên Huế — điều kiện giao dịch QSDĐ theo Luật Đất đai 2024; [2] Thư viện Pháp luật — Điều 45/27 Luật Đất đai 2024; [3] Y&P Law Firm — quy trình mua bán đất thế chấp; [4] Luật Thiên Mã — thủ tục bán nhà đang thế chấp; [5] Luật Nguyên Khanh — cầm cố nhà đất giấy viết tay; [6] Luật Việt Nam — cầm cố sổ đỏ; [7] Thư viện Bản án — bản án cầm cố QSDĐ vô hiệu; [8] Cổng DVC Quốc gia + NĐ 96/2024 — hồ sơ chuyển nhượng dự án; [9] Luật Kinh doanh BĐS 2023 — Điều 40/61; [10] NĐ 101/2024 — đăng ký/cấp sổ đỏ.

---

## 1. Taxonomy tài liệu pháp lý "Đất cầm"

### 1.1 Sơ đồ cây taxonomy (3 cấp)

```
DOMAIN: Pháp lý BĐS "đất cầm" (mua giới)
│
├── [T1] THẾ CHẤP NGÂN HÀNG (bất động sản đang thế chấp tổ chức tín dụng)
│   ├── T1.1 Hợp đồng & văn bản tín dụng
│   │   ├── Hợp đồng tín dụng (vay vốn)
│   │   ├── Hợp đồng thế chấp QSDĐ / nhà đất (công chứng)
│   │   ├── Hợp đồng bảo đảm (nếu thế chấp tài sản gắn liền đất)
│   │   └── Phụ lục hợp đồng, sửa đổi bổ sung
│   ├── T1.2 Giấy tờ xác nhận dư nợ & trạng thái khoản vay
│   │   ├── Văn bản xác nhận dư nợ (gốc + lãi + phạt trả trước hạn)
│   │   ├── Giấy xác nhận tình trạng khoản vay / bảng kê lịch sử trả nợ
│   │   └── Thông báo thu nợ / gia hạn nợ / chuyển nợ quá hạn
│   ├── T1.3 Giải chấp & xóa đăng ký
│   │   ├── Thông báo giải chấp (ngân hàng phát hành sau khi tất toán)
│   │   ├── Văn bản đồng ý xóa thế chấp của ngân hàng
│   │   ├── Phiếu yêu cầu xóa đăng ký thế chấp (Văn phòng đăng ký đất đai)
│   │   └── Giấy xác nhận đã xóa đăng ký biện pháp bảo đảm
│   ├── T1.4 Thỏa thuận phối hợp 3 bên & cơ chế thanh toán
│   │   ├── Thỏa thuận 3 bên (mua – bán – ngân hàng)
│   │   ├── Hợp đồng cam kết mua bán tài sản thế chấp
│   │   ├── Hợp đồng ủy quyền toàn diện (công chứng) — người mua thay bên bán làm thủ tục
│   │   └── Giấy tờ tài khoản phong tỏa / dịch vụ ký quỹ (escrow)
│   └── T1.5 Đăng ký giao dịch bảo đảm
│       ├── Giấy chứng nhận đăng ký biện pháp bảo đảm (NĐ 99/2022/NĐ-CP)
│       └── Tra cứu thông tin thế chấp trên hệ thống đăng ký bảo đảm
│
├── [T2] CẦM CỐ TƯ NHÂN & GIẤY TỜ TAY (rủi ro pháp lý cao)
│   ├── T2.1 Hợp đồng đặt cọc
│   │   ├── Hợp đồng đặt cọc (công chứng — khuyến nghị)
│   │   ├── Giấy đặt cọc viết tay (giá trị pháp lý thấp, khó chứng minh)
│   │   └── Biên nhận tiền đặt cọc / chuyển khoản
│   ├── T2.2 Hợp đồng cầm cố / "cố đất" (ví dụ: hợp đồng cố đất, cầm cố sổ đỏ)
│   │   └── ⚠️ HỢP ĐỒNG CẦM CỐ QSDĐ THƯỜNG VÔ HIỆU (xem §1.2 ghi chú pháp lý)
│   ├── T2.3 Giấy tờ vay nợ tư nhân
│   │   ├── Giấy vay tiền / khế ước vay
│   │   ├── Giấy cam kết trả nợ bằng đất
│   │   └── Giấy ủy quyền (không công chứng) — rủi ro giả tạo
│   └── T2.4 Giấy tờ nhận dạng & chứng minh
│       ├── Bản sao sổ đỏ / GCN QSDĐ
│       ├── CCCD, sổ hộ khẩu, giấy xác nhận tình trạng hôn nhân
│       └── Giấy tờ chứng minh quan hệ (vợ chồng, gia đình)
│
├── [T3] HỒ SƠ DỰ ÁN & PHÁP LÝ THỬA ĐẤT
│   ├── T3.1 Giấy tờ về quyền sử dụng đất (sổ đỏ/sổ hồng)
│   │   ├── GCN QSDĐ (sổ đỏ — mẫu cũ)
│   │   ├── GCN QSH nhà ở & QSDĐ (sổ hồng)
│   │   ├── GCN QSDĐ, QSH nhà ở và tài sản gắn liền với đất (mẫu từ 10/12/2009)
│   │   └── Trích lục bản đồ / sơ đồ thửa đất
│   ├── T3.2 Quy hoạch & kế hoạch sử dụng đất
│   │   ├── Quy hoạch sử dụng đất cấp tỉnh/huyện
│   │   ├── Quy hoạch chi tiết / quy hoạch tổng mặt bằng dự án
│   │   ├── Quy hoạch đô thị và nông thôn (Luật 57/2024/QH15)
│   │   └── Văn bản phê duyệt quy hoạch
│   ├── T3.3 Quyết định & văn bản giao đất
│   │   ├── Quyết định giao đất / cho thuê đất (có thu tiền / không thu tiền)
│   │   ├── Quyết định cho phép chuyển mục đích sử dụng đất
│   │   ├── Biên bản bàn giao đất thực địa
│   │   └── Quyết định chủ trương đầu tư / chấp thuận chủ đầu tư
│   ├── T3.4 Xây dựng & nghiệm thu
│   │   ├── Giấy phép xây dựng
│   │   ├── Thông báo khởi công xây dựng
│   │   ├── Biên bản nghiệm thu hoàn thành hạ tầng kỹ thuật / phần móng
│   │   └── Báo cáo quá trình thực hiện dự án
│   ├── T3.5 Tài chính đất đai
│   │   ├── Xác nhận hoàn thành nghĩa vụ tài chính về đất đai (thuế, tiền SDĐ)
│   │   ├── Chứng từ nộp tiền sử dụng đất / thuế đất
│   │   └── Thông báo nộp lệ phí trước bạ, thuế TNCN
│   └── T3.6 Hồ sơ thủ tục biến động
│       ├── Đơn đăng ký biến động đất đai (Mẫu 11/ĐK — NĐ 101/2024)
│       ├── Hợp đồng chuyển nhượng QSDĐ (công chứng)
│       ├── Đơn đề nghị tách thửa / hợp thửa (Mẫu 01/ĐK)
│       └── Văn bản thỏa thuận phân chia di sản thừa kế (nếu có)
│
├── [T4] VĂN BẢN PHÁP LUẬT NỀN (quy phạm pháp luật)
│   ├── T4.1 Luật (Quốc hội)
│   │   ├── Luật Đất đai 2024 (31/2024/QH15) — hiệu lực 01/01/2025 (một số điều 01/08/2024)
│   │   ├── Bộ luật Dân sự 2015 (91/2015/QH13) — Điều 309-321 (cầm cố/thế chấp), Điều 328 (đặt cọc)
│   │   ├── Luật Kinh doanh BĐS 2023 (29/2023/QH15) — hiệu lực 01/08/2024
│   │   ├── Luật Nhà ở 2023 (27/2023/QH15) — hiệu lực 01/08/2024
│   │   ├── Luật Công chứng 2014 (sửa đổi, bổ sung 2018)
│   │   ├── Luật Quy hoạch đô thị và nông thôn 2024 (57/2024/QH15)
│   │   └── Luật Các tổ chức tín dụng (sửa đổi 2024 — 32/2024/QH15)
│   ├── T4.2 Nghị định (Chính phủ)
│   │   ├── NĐ 101/2024/NĐ-CP — đăng ký, cấp GCN QSDĐ (sổ đỏ/sổ hồng)
│   │   ├── NĐ 96/2024/NĐ-CP — chi tiết Luật Kinh doanh BĐS
│   │   ├── NĐ 99/2022/NĐ-CP — đăng ký biện pháp bảo đảm
│   │   ├── NĐ 102/2017/NĐ-CP — đăng ký bảo đảm bằng QSDĐ, nhà ở
│   │   └── NĐ 102/2024/NĐ-CP — bồi thường, hỗ trợ, tái định cư khi thu hồi đất
│   ├── T4.3 Thông tư (Bộ, ngành)
│   │   ├── TT 04/2024/TT-BXD — chương trình khung đào tạo môi giới BĐS
│   │   └── Thông tư của Bộ TN&MT về hồ sơ địa chính
│   └── T4.4 Bản án / quyết định tham khảo (án lệ thực tiễn)
│       ├── Bản án về tranh chấp hợp đồng cầm cố QSDĐ (vô hiệu)
│       ├── Bản án tranh chấp đặt cọc mua đất
│       └── Quyết định của Tòa án về giải quyết tranh chấp đất đai
```

### 1.2 Ghi chú pháp lý quan trọng (ảnh hưởng taxonomy & retrieval)

1. **Cầm cố QSDĐ KHÔNG được pháp luật ghi nhận**: Điều 27 Luật Đất đai 2024 chỉ liệt kê chuyển đổi, chuyển nhượng, cho thuê, cho thuê lại, thừa kế, tặng cho, **thế chấp**, góp vốn — **không có "cầm cố"**. Do đó hợp đồng cầm cố QSDĐ bị tòa án tuyên **vô hiệu** (Điều 123 BLDS — vi phạm điều cấm). Khi ingest, nhóm T2.2 phải được gắn tag `legal_invalid_risk=high` và mọi câu trả lời về "cầm cố đất" phải cảnh báo rủi ro vô hiệu.
2. **Sổ đỏ không phải tài sản**, không thể "cầm cố sổ đỏ" — GCN chỉ là chứng thư pháp lý (khoản 21 Điều 3 Luật Đất đai 2024). Người dân chỉ được **thế chấp** (đăng ký tại cơ quan đăng ký đất đai), không được cầm cố.
3. **Hợp đồng thế chấp bắt buộc công chứng/chứng thực** (khoản 3 Điều 27 Luật Đất đai 2024) và **bắt buộc đăng ký biện pháp bảo đảm** (NĐ 99/2022) để có hiệu lực đối kháng bên thứ ba.
4. **Điều kiện chuyển nhượng QSDĐ** (Điều 45 Luật Đất đai 2024): có GCN; đất không tranh chấp (hoặc đã giải quyết); không bị kê biên; trong thời hạn sử dụng; không bị áp dụng biện pháp khẩn cấp tạm thời. → Đây là **checklist thẩm định** mà mọi mua giới phải chạy.
5. **Bán tài sản đang thế chấp**: Điều 320 BLDS cấm bên thế chấp bán tài sản; Điều 321.5 mở ngoại lệ **nếu được bên nhận thế chấp đồng ý bằng văn bản** → giao dịch không có văn bản đồng ý của ngân hàng có nguy cơ vô hiệu.
6. **Đặt cọc** (Điều 328 BLDS): không bắt buộc công chứng, nhưng giấy tay rất khó chứng minh khi tranh chấp → khuyến nghị luôn công chứng.

### 1.3 Bảng metadata gắn cho tài liệu (đề xuất scheme)

| Field | Ví dụ | Bắt buộc | Ghi chú ingest |
|---|---|---|---|
| `doc_id` | `LDD-2024-31-Đ27` | ✅ | ID ổn định; dùng cho citation/source tracking |
| `title` | "Luật Đất đai 2024" | ✅ | |
| `doc_type` | `law / decree / circular / contract / certificate / decision / court_judgment / internal` | ✅ | Phân loại taxonomy (T1–T4) |
| `category` | `T1.3.giai_chap` | ✅ | Gắn nhánh taxonomy |
| `effective_date` | `2025-01-01` | ✅ | **BẮT BUỘC** — filter query theo hiệu lực |
| `status` | `in_effect / expired / amended / temp_invalid` | ✅ | Luật Đất đai 2013 → `expired` |
| `issuer` | `Quốc hội` / `Chính phủ` / `Bộ TN&MT` / `Ngân hàng X` | ✅ | |
| `document_number` | `31/2024/QH15` | nên có | Tìm kiếm bằng số hiệu |
| `applicable_region` | `toàn quốc` / `tỉnh` / `dự án cụ thể` | nên có | Quy hoạch/tờ trình theo địa phương |
| `related_entities` | Số thửa, tên dự án, ngân hàng, tên bên | ✅ | Nuôi entity cho LightRAG low-level |
| `high_stakes` | `true/false` | ✅ | Kích hoạt human review (xem §4) |
| `source_file` | `pdf/2024/Luat_Dat_dai_2024.pdf` | ✅ | Truy xuất bản gốc |
| `ingested_at` | `2026-08-09` | ✅ | Audit + incremental update |

---

## 2. Quy trình nghiệp vụ mua giới "đất cầm" (end-to-end)

### 2.1 Chuỗi 7 bước (đã đối chiếu nhiều nguồn công ty luật)

```
B0. Tiếp cận & khai thác khách
  → B1. Thẩm định pháp lý sơ bộ
    → B2. Thỏa thuận & Đặt cọc
      → B3. Thỏa thuận 3 bên + Thanh toán giải chấp
        → B4. Công chứng hợp đồng chuyển nhượng
          → B5. Nộp thuế/phí + Sang tên (đăng ký biến động)
            → B6. Bàn giao & Giải ngân ký quỹ (nếu có)
```

### 2.2 Chi tiết từng bước — tài liệu cần tra & câu hỏi điển hình

| # | Bước | Việc mua giới làm | Tài liệu cần tra cứu (nhánh taxonomy) | Câu hỏi chat điển hình |
|---|---|---|---|---|
| **B0** | Tiếp cận khách | Nghe nhu cầu (mua đất thế chấp, đất cầm cố, mua dự án), hẹn làm hồ sơ | (chưa cần tài liệu) | "Khách muốn mua đất đang thế chấp thì cần chuẩn bị những gì?" |
| **B1** | Thẩm định pháp lý | Kiểm tra sổ đỏ, quy hoạch, thế chấp, tranh chấp, kê biên, người đứng tên, hôn nhân | T3.1 (sổ đỏ), T3.2 (quy hoạch), T1.5 (đăng ký bảo đảm), T1.2 (xác nhận dư nợ), T2.4 (CCCD/giấy hôn nhân) | "Điều kiện để đất chuyển nhượng được theo Luật Đất đai 2024 là gì?"; "Làm sao biết đất đang bị thế chấp hay kê biên?"; "Đất dính quy hoạch thì có mua được không?" |
| **B2** | Đặt cọc | Soạn/ký hợp đồng đặt cọc (nên công chứng), ghi rõ tình trạng thế chấp, giao tiền cọc | T2.1 (hợp đồng đặt cọc), T4.1 BLDS Điều 328 | "Hợp đồng đặt cọc viết tay có giá trị không?"; "Đặt cọc mua đất đang thế chấp cần ghi những gì để an toàn?"; "Mất cọc khi bên bán không bán nữa thì xử lý sao?" |
| **B3** | Thỏa thuận 3 bên + Giải chấp | Làm việc với ngân hàng: xác nhận dư nợ, thỏa thuận 3 bên, chuyển tiền tất toán vào tài khoản phong tỏa, nhận thông báo giải chấp + sổ đỏ gốc | T1.4 (thỏa thuận 3 bên, ủy quyền), T1.2 (xác nhận dư nợ), T1.3 (giải chấp), T1.5 (đăng ký bảo đảm) | "Quy trình giải chấp sổ đỏ sau khi trả nợ là bao lâu?"; "Bên mua có được nộp tiền thay bên bán để giải chấp không?"; "Thỏa thuận 3 bên cần những nội dung gì?"; "Tài khoản phong tỏa là gì, vì sao phải dùng?" |
| **B4** | Công chứng chuyển nhượng | Sau khi đã xóa thế chấp, ký hợp đồng chuyển nhượng QSDĐ tại Văn phòng công chứng | T3.6 (hợp đồng chuyển nhượng), T4.1 (Luật Công chứng), T1.3 (giấy xóa thế chấp) | "Sau khi giải chấp, ký công chứng chuyển nhượng cần giấy tờ gì?"; "Hợp đồng chuyển nhượng QSDĐ có bắt buộc công chứng không?" |
| **B5** | Thuế + Sang tên | Kê khai TNCN (2%) + lệ phí trước bạ (0,5%), nộp hồ sơ đăng ký biến động tại Văn phòng đăng ký đất đai | T3.5 (tài chính đất đai), T3.6 (đơn ĐK biến động Mẫu 11/ĐK), T4.2 (NĐ 101/2024) | "Thuế khi mua bán đất là bao nhiêu, ai chịu?"; "Sang tên sổ đỏ mất bao lâu?"; "Hồ sơ đăng ký biến động gồm những gì?" |
| **B6** | Bàn giao & thanh toán cuối | Giao sổ đỏ mới, bàn giao đất/giấy tờ, giải ngân ký quỹ cho bên bán | T3.6 (sổ mới), T1.4 (escrow/ký quỹ) | "Sau khi sang tên xong, thanh toán nốt tiền cho bên bán thế nào cho an toàn?" |

### 2.3 Hai lộ trình pháp lý khác nhau (quan trọng để phân loại query)

- **Lộ trình A — Đất thế chấp ngân hàng (hợp pháp)**: tuân theo §2.2. Điểm mấu chốt: phải có văn bản đồng ý của ngân hàng (Điều 321.5 BLDS), tiền đi qua tài khoản phong tỏa, sổ đỏ chỉ xóa thế chấp sau khi tất toán.
- **Lộ trình B — Đất cầm cố tư nhân/giấy tay (rủi ro cao)**: hợp đồng cầm cố QSDĐ thường vô hiệu → tranh chấp phổ biến. Chat phải chuyển hướng: cảnh báo rủi ro, khuyên công chứng, đối chiếu bản án. **KHÔNG được khẳng định "giao dịch an toàn"**.

---

## 3. Golden set seed — 30 câu hỏi tiếng Việt (seed cho `eval/golden_set.json`)

Phân loại RAG: **L** = local (entity chi tiết), **G/H** = global/hybrid (tổng quan, chéo văn bản), **P** = quy trình tình huống.

| # | Loại | Câu hỏi (tự nhiên) | Intent | Tài liệu kỳ vọng | Đáp án chuẩn (ngắn) |
|---|---|---|---|---|---|
| 1 | L | Theo Luật Đất đai 2024, đất muốn chuyển nhượng phải đáp ứng những điều kiện gì? | Tra điều kiện chuyển nhượng | Điều 45 Luật Đất đai 2024 | Có GCN; không tranh chấp (hoặc đã giải quyết); không bị kê biên; trong thời hạn SDĐ; không bị biện pháp khẩn cấp tạm thời |
| 2 | L | Hợp đồng thế chấp quyền sử dụng đất có bắt buộc công chứng không? | Tra thủ tục công chứng | Khoản 3 Điều 27 Luật Đất đai 2024 | Có, hợp đồng thế chấp QSDĐ phải công chứng/chứng thực và đăng ký biện pháp bảo đảm |
| 3 | L | Bên thế chấp có được bán đất đang thế chấp ngân hàng không? | Tra quyền của bên thế chấp | Điều 320, 321 BLDS 2015 | Không được tự ý bán; chỉ được bán nếu được ngân hàng đồng ý bằng văn bản (Điều 321.5) |
| 4 | L | Đặt cọc theo Bộ luật Dân sự là gì, giấy đặt cọc viết tay có giá trị không? | Tra chế định đặt cọc | Điều 328 BLDS 2015 | Đặt cọc là giao tiền/tài sản để bảo đảm giao kết hợp đồng; viết tay có giá trị nhưng khó chứng minh, nên công chứng |
| 5 | L | Lệ phí trước bạ khi mua bán nhà đất là bao nhiêu phần trăm? | Tra thuế phí | NĐ về lệ phí trước bạ (0,5%) | 0,5% giá trị tài sản (bên mua nộp) |
| 6 | L | Thuế thu nhập cá nhân khi chuyển nhượng nhà đất là bao nhiêu? | Tra thuế phí | Luật Thuế TNCN (2% giá chuyển nhượng) | 2% giá trị chuyển nhượng (bên bán nộp, thường thỏa thuận) |
| 7 | L | Sang tên sổ đỏ (đăng ký biến động) mất bao lâu? | Tra thời gian thủ tục | NĐ 101/2024, Điều 22 (≤10 ngày làm việc) | Không quá 10 ngày làm việc kể từ khi nhận đủ hồ sơ hợp lệ |
| 8 | L | Giấy chứng nhận (sổ đỏ) có được cầm cố không? | Tra bản chất GCN | Khoản 21 Điều 3 Luật Đất đai 2024; Điều 309 BLDS | Không; sổ đỏ là chứng thư pháp lý, không phải tài sản → không cầm cố được, chỉ thế chấp |
| 9 | L | Hợp đồng chuyển nhượng quyền sử dụng đất có bắt buộc công chứng không? | Tra thủ tục công chứng | Khoản 3 Điều 27 Luật Đất đai 2024 | Có, phải công chứng/chứng thực (trừ trường hợp đặc biệt theo điểm b) |
| 10 | L | Điều kiện để nhà ở hình thành trong tương lai được bán là gì? | Tra điều kiện kinh doanh | Điều 24 Luật Kinh doanh BĐS 2023 | Có giấy tờ về QSDĐ, GPXD, nghiệm thu phần móng (chung cư)... |
| 11 | G/H | Sự khác nhau giữa thế chấp và cầm cố quyền sử dụng đất là gì? | So sánh khái niệm chéo văn bản | Điều 309, 317 BLDS + Điều 27 Luật Đất đai 2024 | Thế chấp: không chuyển giao tài sản, có đăng ký, được phép; cầm cố: chuyển giao, **không được phép đối với QSDĐ → thường vô hiệu** |
| 12 | G/H | Quy trình mua bán đất đang thế chấp ngân hàng gồm những bước nào? | Tổng hợp quy trình | Nhiều văn bản (thỏa thuận 3 bên → giải chấp → công chứng → sang tên) | 6 bước: thẩm định → đặt cọc → thỏa thuận 3 bên + giải chấp → công chứng → thuế/sang tên → bàn giao |
| 13 | G/H | Những rủi ro pháp lý khi mua đất cầm cố bằng giấy tờ tay là gì? | Tổng quan rủi ro cầm cố tư nhân | Bản án cầm cố QSDĐ vô hiệu + Điều 123 BLDS | Hợp đồng cầm cố QSDĐ thường vô hiệu; khó chứng minh; tranh chấp kéo dài; mất tiền cọc |
| 14 | G/H | Điều kiện để chuyển nhượng một phần dự án bất động sản là gì? | Tra điều kiện dự án | Điều 40 Luật Kinh doanh BĐS 2023 | Đã chủ trương đầu tư, quy hoạch chi tiết, hoàn thành bồi thường, không tranh chấp/kê biên, đã giải chấp nếu thế chấp |
| 15 | G/H | Luật Đất đai 2024 có gì mới so với Luật Đất đai 2013 về điều kiện chuyển nhượng? | So sánh văn bản cũ/mới | Điều 45 (2024) vs Điều 188 (2013) | Bổ sung rõ "tranh chấp đã giải quyết có hiệu lực", "không áp dụng biện pháp khẩn cấp tạm thời"; điều kiện nhận chuyển nhượng riêng |
| 16 | G/H | Tài khoản phong tỏa / dịch vụ ký quỹ khi mua đất thế chấp hoạt động thế nào? | Tổng quan cơ chế thanh toán | Hợp đồng dịch vụ ngân hàng + thỏa thuận 3 bên | Tiền mua được giữ tại ngân hàng, chỉ giải ngân cho bên bán sau khi sang tên xong → bảo vệ bên mua |
| 17 | G/H | Giải chấp là gì, khi nào đất được xem là đã giải chấp? | Tra khái niệm giải chấp | NĐ 99/2022; thông báo giải chấp | Là xóa đăng ký thế chấp tại cơ quan đăng ký sau khi tất toán nợ; có văn bản xác nhận đã xóa |
| 18 | L | Người mua đất cần kiểm tra những gì trên sổ đỏ trước khi giao dịch? | Checklist thẩm định | T3.1; Điều 45 Luật Đất đai 2024 | Người đứng tên, diện tích, loại đất, thời hạn sử dụng, ghi chú thế chấp/hạn chế, sơ đồ thửa |
| 19 | P | Khách muốn mua đất đang thế chấp ngân hàng, bên bán không có tiền giải chấp — xử lý thế nào? | Tình huống quy trình | Quy trình 3 bên (§2.2 B3) | Dùng thỏa thuận 3 bên: bên mua nộp tiền tất toán vào tài khoản phong tỏa tại ngân hàng, ngân hàng giải chấp và giao sổ đỏ |
| 20 | P | Bên bán đưa giấy đặt cọc viết tay, khách hỏi có nên đặt cọc không? | Tình huống rủi ro | Điều 328 BLDS; §2.2 B2 | Nên công chứng hợp đồng đặt cọc; viết tay có giá trị nhưng rủi ro chứng minh cao; ghi rõ hiện trạng thế chấp |
| 21 | P | Khách muốn mua nền dự án đã có quyết định giao đất nhưng chưa có sổ đỏ — có giao dịch được không? | Tình huống dự án | Điều 24 Luật Kinh doanh BĐS 2023; Điều 45 Luật Đất đai | Được nếu đáp ứng điều kiện chuyển nhượng dự án/hạ tầng; nhưng phải kiểm tra tiến độ, giải chấp, hạ tầng |
| 22 | P | Đất đang bị kê biên thi hành án thì có mua bán được không? | Tình huống hạn chế giao dịch | Điều 45.1(c) Luật Đất đai 2024 | Không; QSDĐ bị kê biên không đủ điều kiện chuyển nhượng cho đến khi xử lý xong |
| 23 | P | Bên bán là vợ chồng nhưng chỉ một người ký hợp đồng — rủi ro gì? | Tình huống đồng sở hữu | T2.4; BLDS về tài sản chung | Rủi ro: tài sản chung vợ chồng cần cả hai đồng ý; hợp đồng có thể bị vô hiệu/vướng tranh chấp |
| 24 | P | Khách đã đặt cọc 500 triệu nhưng bên bán bán cho người khác — bồi thường thế nào? | Tình huống vi phạm đặt cọc | Điều 328.2 BLDS | Bên nhận cọc từ chối thực hiện phải trả lại cọc + phạt một khoản tương đương giá trị cọc |
| 25 | P | Sang tên xong rồi mới phát hiện đất dính quy hoạch — khách hỏi khiếu nại ai? | Tình huống quy hoạch | T3.2; Luật Quy hoạch 2024 | Kiểm tra quy hoạch TRƯỚC khi giao dịch; tranh chấp quy hoạch giải quyết theo khiếu nại hành chính; hợp đồng có thể bị tuyên vô hiệu nếu dối trá |
| 26 | P | Mua đất thông qua hợp đồng ủy quyền (không chuyển nhượng) có an toàn không? | Tình huống ủy quyền | BLDS về ủy quyền; thực tiễn bản án | Rủi ro: ủy quyền có thể bị hủy, người ủy quyền chết/tranh chấp; không phải chuyển quyền sở hữu → không nên thay thế hợp đồng chuyển nhượng |
| 27 | P | Khách mua đất cầm cố tư nhân, hiện người cầm cố cần chuộc lại — quy trình ra sao? | Tình huống chuộc cầm cố | Bản án cầm cố vô hiệu; Điều 123, 131 BLDS | Cảnh báo hợp đồng cầm cố QSDĐ vô hiệu; nên chuyển sang vay có thế chấp đăng ký hợp pháp; hoàn trả tiền + tài sản theo hậu quả vô hiệu |
| 28 | G/H | Những trường hợp nào không được nhận chuyển nhượng QSDĐ? | Tra điều cấm | Điều 191 + khoản 8 Điều 45 Luật Đất đai 2024 | Tổ chức, cá nhân không được nhận chuyển nhượng khi pháp luật không cho phép; đất rừng phòng hộ/đặc dụng hạn chế... |
| 29 | L | Môi giới bất động sản cần những điều kiện gì để hành nghề hợp pháp? | Tra điều kiện hành nghề | Điều 61 Luật Kinh doanh BĐS 2023 | Có chứng chỉ hành nghề môi giới; phải hành nghề trong doanh nghiệp kinh doanh dịch vụ BĐS (từ 01/08/2024) |
| 30 | L | Hợp đồng đặt cọc khi mua đất thế chấp cần ghi rõ những nội dung gì? | Tra nội dung hợp đồng | BLDS Điều 328; thực tiễn công chứng | Ghi rõ hiện trạng đang thế chấp tại ngân hàng nào, số nợ, mục đích tiền cọc, quy trình phối hợp rút sổ, phạt vi phạm |

> Phân bổ: **10 local (L) + 10 global/hybrid (G/H) + 10 quy trình tình huống (P)** = 30 câu. Đạt chuẩn 25-30 câu của plan. Khi chạy eval cần ghi thêm: `expected_source_ids` (điều luật cụ thể), `min_confidence` và `requires_human_review` (true/false).

---

## 4. Rủi ro pháp lý & anti-hallucination (high-stakes)

### 4.1 Vì sao high-stakes: legal LLM hallucinate ~1/6 (CLAUDE.md) — fake citation là nguy hiểm nhất

Nguyên tắc: mọi câu trả lời đụng **giá trị tiền / quyền lợi pháp lý / thủ tục bắt buộc** phải có ≥2 nguồn + citation grounding; nếu không đủ → LOW confidence → **human review bắt buộc**.

### 4.2 Keyword list để classify high-stakes (regex, tiếng Việt chuẩn hóa)

**Nhóm 1 — Giá trị & dòng tiền (mức rủi ro tối đa)**
`đặt cọc`, `tiền cọc`, `cọc`, `thanh toán`, `giá trị hợp đồng`, `tất toán`, `dư nợ`, `gốc`, `lãi suất`, `phạt trả trước hạn`, `trả nợ`, `phong tỏa`, `ký quỹ`, `escrow`, `bồi thường`, `phạt cọc`, `mất cọc`, `hoa hồng`, `thù lao môi giới`

**Nhóm 2 — Giải chấp & thế chấp (rủi ro pháp lý quy trình)**
`giải chấp`, `xóa thế chấp`, `xóa đăng ký`, `thông báo giải chấp`, `đồng ý của ngân hàng`, `thỏa thuận ba bên`, `3 bên`, `tài sản thế chấp`, `đăng ký biện pháp bảo đảm`, `sổ đỏ gốc`, `cầm sổ`, `chuộc sổ`

**Nhóm 3 — Tranh chấp & hạn chế quyền (rủi ro giao dịch chết)**
`tranh chấp`, `kê biên`, `thi hành án`, `ngăn chặn`, `khẩn cấp tạm thời`, `thu hồi đất`, `đình chỉ`, `cấm giao dịch`, `vô hiệu`, `hủy hợp đồng`, `khởi kiện`, `tòa án`, `bản án`, `án lệ`, `người thứ ba`, `đồng sở hữu`, `tài sản chung vợ chồng`, `di sản`, `thừa kế`

**Nhóm 4 — Ủy quyền & giấy tờ tay (rủi ro hình thức)**
`ủy quyền`, `giấy tay`, `viết tay`, `không công chứng`, `cầm cố`, `cố đất`, `cầm cố sổ đỏ`, `giấy vay`, `cam kết trả nợ bằng đất`, `Ủy quyền toàn diện`

**Nhóm 5 — Tính hiệu lực văn bản (rủi ro trả version hết hiệu lực)**
`luật đất đai 2013`, `luật đất đai 2024`, `hết hiệu lực`, `thay thế`, `hiệu lực`, `từ 01/08/2024`, `từ 01/01/2025`, `nghị định 43/2014` (cũ), `nghị định 101/2024` (mới)

### 4.3 Logic gợi ý cho tầng confidence

```
high_stakes = any(keyword in query OR in retrieved chunks)
if high_stakes:
    if confidence < HIGH (thiếu ≥2 nguồn / rerank <0.8 / grounding fail):
        → bắt buộc human review (review_queue)
    else:
        → trả lời kèm cảnh báo "đây là giao dịch rủi ro, cần xác minh với ngân hàng/công chứng viên"
else:
    → áp dụng confidence 3-tier thường (HIGH/MEDIUM/LOW)
```

### 4.4 Grounding bắt buộc cho domain legal

- Mọi con số pháp lý (2% TNCN, 0,5% trước bạ, 10 ngày sang tên, điều kiện Điều 45...) phải có span trích dẫn nằm trong chunk nguồn.
- Nếu query thuộc **Lộ trình B (cầm cố tư nhân)** → thêm class `warning` mặc định: "Giao dịch cầm cố QSDĐ không được pháp luật công nhận, có nguy cơ vô hiệu — nên tham vấn luật sư / công chứng viên."
- Không trả lời theo "kinh nghiệm dân gian" (vd: "cầm sổ đỏ ngân hàng tư nhân được" — sai pháp lý).

---

## 5. Khuyến nghị mở rộng (extensibility)

### 5.1 Taxonomy có kế thừa được không? — CÓ, với 3 nguyên tắc

1. **Phân tầng theo "vật thể pháp lý", không theo "kênh sản phẩm"**: taxonomy hiện tại phân theo BẢN CHẤT pháp lý (thế chấp / cầm cố / hồ sơ dự án / luật nền) — không theo "đất cầm" hay "nhà phố". Khi mở rộng sang chung cư/nhà phố/dự án lớn, ta chỉ THÊM nhánh con, không đập đi. Ví dụ:
   - Chung cư → nhánh mới `T3.7 Nhà chung cư` (hợp đồng mua bán căn hộ, biên bản bàn giao căn hộ, phí bảo trì 2%, sổ hồng chung cư, quy chế quản lý tòa nhà) + `T4.1` bổ sung Luật Nhà ở 2023 chi tiết.
   - Dự án lớn → tận dụng sẵn T3.2–T3.5 (quy hoạch, giao đất, GPXD, tài chính) — chỉ thêm chi tiết theo Luật Nhà ở / Luật Kinh doanh BĐS.
2. **Tách metadata loại tài sản** thành `property_type`: `dat_nong_nghiep / dat_o / nha_pho / chung_cu / du_an_future / du_an_completed`. Filter query theo property_type thay vì hardcode.
3. **Văn bản pháp luật nền (T4) là "shared layer"** — 1 bộ luật duy nhất phục vụ mọi loại BĐS, không nhân bản. Chỉ bổ sung luật mới (vd Luật Nhà ở chi tiết, Luật Xây dựng) khi mở rộng.

### 5.2 Lộ trình mở rộng đề xuất

| Phase | Loại BĐS | Nhánh taxonomy thêm | Luật bổ sung |
|---|---|---|---|
| MVP (nay) | Đất cầm (thế chấp NH + cầm cố tư nhân + hồ sơ dự án) | T1–T4 như §1 | Như §1.1 |
| Phase 2 | Nhà phố, đất ở có nhà | `T3.7 nhà ở`, chi tiết T3.1 sổ hồng nhà | Luật Nhà ở 2023 (chi tiết), NĐ 96/2024 |
| Phase 3 | Chung cư / căn hộ | `T3.8 chung cư` (hợp đồng mua bán căn hộ, phí bảo trì, nghiệm thu, quản lý tòa nhà) | Luật Nhà ở 2023, quy chế quản lý nhà chung cư |
| Phase 4 | Dự án lớn / khu đô thị | T3.2–T3.5 bổ sung hạ tầng xã hội, tiến độ, bảo lãnh | Luật Kinh doanh BĐS Điều 24-26, Luật Xây dựng |

### 5.3 Thiết kế để mở rộng ngay từ ingest (khuyến nghị cho team implement)

1. **Metadata schema đã có `property_type` + `category` tree** → thêm nhánh = thêm category con, KHÔNG cần re-embed toàn bộ (LightRAG incremental merge node/edge).
2. **Entity naming chuẩn** khi extract: luôn kèm loại (vd `[BĐS] KDC An Phú`, `[TCTD] Ngân hàng ACB`, `[VĂN BẢN] Luật Đất đai 2024`) → giảm nhầm lẫn entity trùng tên khi mở rộng.
3. **Golden set tăng dần theo phase**: seed 30 câu (MVP) → thêm 10-15 câu/phase. Mỗi câu gắn `taxonomy_tag` để đo coverage theo nhánh.
4. **Filter hiệu lực (effective_date/status) là bắt buộc từ đầu** — khi thêm văn bản mới (vd Luật Quy hoạch đô thị và nông thôn 2024 thay thế Luật Quy hoạch đô thị 2009), văn bản cũ tự bị downgrade, không cần đụng lại dữ liệu cũ.
5. **Không hardcode tên luật trong query LLM prompt** — dùng taxonomy tag làm context hint; khi mở rộng, chỉ cập nhật taxonomy file + prompt template 1 chỗ.

---

## 6. Nguồn (đối chiếu trong research)

1. Sở Tư pháp Thừa Thiên Huế — Điều kiện giao dịch dân sự liên quan QSDĐ theo Luật Đất đai 2024 (stp.hue.gov.vn)
2. Thư viện Pháp luật — Điều 45, 27, 168, 191 Luật Đất đai 2024 (thuvienphapluat.vn)
3. Y&P Law Firm — Quy trình chuẩn pháp lý mua bán nhà đất đang thế chấp tại ngân hàng (yplawfirm.vn)
4. Luật Thiên Mã — Thủ tục bán nhà đang cầm cố, thế chấp ngân hàng (luatthienma.com.vn)
5. PVcomBank — Hướng dẫn thủ tục mua nhà thế chấp ngân hàng (pvcombank.com.vn)
6. Luật Nguyên Khanh — Thủ tục mua bán nhà đất đang thế chấp; Giải quyết tranh chấp cầm cố nhà đất giấy viết tay (luatnguyenkhanh.vn)
7. Luật Việt Nam (LuatVietnam) — Người dân không được cầm cố Sổ đỏ (luatvietnam.vn)
8. Thư viện Bản án — Bản án 31/2020/DS-ST, 21/2017/DS-ST về tranh chấp hợp đồng cầm cố QSDĐ (vô hiệu) (thuvienphapluat.vn/banan)
9. Cổng Dịch vụ công Quốc gia — Hồ sơ chuyển nhượng dự án BĐS theo NĐ 96/2024/NĐ-CP (dichvucong.gov.vn)
10. Luật Kinh doanh BĐS 2023 (29/2023/QH15) — Điều 40, 61 (vanban.vcci.com.vn, luatvietnam.vn)
11. Nghị định 101/2024/NĐ-CP — Đăng ký, cấp GCN QSDĐ, sổ đỏ/sổ hồng (congbao.chinhphu.vn, thuvienphapluat.vn)
12. Nghị định 99/2022/NĐ-CP — Đăng ký biện pháp bảo đảm (congbao.chinhphu.vn)
13. Nghị định 96/2024/NĐ-CP — Chi tiết Luật Kinh doanh BĐS (thuvienphapluat.vn)
14. Thông tư 04/2024/TT-BXD — Chương trình khung đào tạo môi giới BĐS (luatvietnam.vn)
15. Trường ĐH Kinh tế Cần Thơ + CTELG — Điều kiện hành nghề môi giới BĐS từ 01/8/2024 (ctelg.ueh.edu.vn)
16. Tạp chí khoa học OU — Bàn về cầm cố tài sản là QSDĐ và nhà (journalofscience.ou.edu.vn)
17. LuatVietnam — Mẫu đơn đăng ký biến động đất đai (luatvietnam.vn)

---

*Confidence: High cho khung pháp lý nền (nhiều nguồn đối chiếu nhất quán); Medium cho quy trình thực tế (thay đổi theo ngân hàng). Các ví dụ tài liệu cụ thể trong mỗi nhóm taxonomy là template điển hình — khi ingest cần rà thực tế hồ sơ công ty cung cấp.*
