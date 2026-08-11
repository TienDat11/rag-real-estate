# Data Contract — Khung dữ liệu cần chuẩn bị (trước khi có dữ liệu thật)

> Mục đích: liệt kê NGAY các fields bắt buộc cho từng loại dữ liệu, để người chuẩn bị
> (bạn / đội kinh doanh) đi thu thập đúng những gì hệ thống cần — không cần source thật
> cũng bắt đầu được vì schema đã "ngon lành" từ đầu (`db/schema.sql`).
> Ngày: 2026-08-10 | MVP 2 tuần (chỉ user query, chưa admin)

## 1. Ba loại dữ liệu (field `kind` trong bảng `documents`)

| `kind` | Ý nghĩa | Nhịp cập nhật | Ví dụ |
|---|---|---|---|
| `legal` | Văn bản pháp luật, quy hoạch, hồ sơ pháp lý dự án | Chậm (~6 tháng/lần) | Luật Đất đai 2024, quyết định quy hoạch, giấy phép dự án |
| `price` | Bảng giá, bảng thanh toán, chính sách chiết khấu | NHANH (theo chiến dịch) | Bảng giá tòa A đợt 3/2026 |
| `project` | Hồ sơ tổng quan dự án (tiện ích, vị trí, tiến độ) | Trung bình | Brochure dự án, mặt bằng tổng thể |

## 2. Fields bắt buộc cho MỌI tài liệu (không thiếu được)

| Field | Ví dụ hợp lệ | Bắt buộc? | Ghi chú |
|---|---|---|---|
| `doc_id` | `price-tower-a-2026q3` | ✅ | ID ổn định, đặt theo quy ước `loại-tên-đợt` |
| `kind` | `legal` / `price` / `project` | ✅ | Chọn 1 trong 3 |
| `title` | "Bảng giá tòa A đợt mở bán 3/2026" | ✅ | Tên hiển thị cho người dùng |
| `source_file` | `bang-gia-toa-A-2026Q3.pdf` | ✅ | File gốc |
| `effective_date` | `2026-03-01` | ✅ | Ngày bắt đầu có hiệu lực |
| `expiry_date` | `2026-06-30` | (trống = còn hiệu lực) | Ngày hết hiệu lực — **bắt buộc với bảng giá** |
| `status` | `published` | ✅ (mặc định) | MVP chỉ dùng `published` / `expired` |
| `content` | Nội dung text | ✅ | Trích từ file gốc (script ingest tự làm) |

## 3. Fields metadata theo loại (JSON trong cột `metadata`)

### 3.1. `legal` — văn bản pháp luật
```json
{
  "document_number": "45/2013/QH13",
  "document_type": "luat",
  "issuer": "Quốc hội",
  "issue_date": "2013-06-29",
  "related_docs": ["ldd-2003", "nghi-dinh-43"],
  "keywords": ["quy hoạch", "sử dụng đất"]
}
```

### 3.2. `price` — bảng giá / bảng thanh toán
```json
{
  "project": "Dự án Tower A",
  "campaign": "Đợt mở bán 3/2026",
  "currency": "VND",
  "price_structure": "tran/goc",
  "items": [
    { "unit": "A10-01", "floor": 10, "area_m2": 85.5, "price_vnd": 2850000000, "price_m2": 33333333 },
    { "unit": "A10-02", "floor": 10, "area_m2": 72.0, "price_vnd": 2400000000, "price_m2": 33333333 }
  ],
  "payment_terms": { "deposit_pct": 10, "installments": 6, "note": "Chiết khấu 2% thanh toán sớm" }
}
```

### 3.3. `project` — hồ sơ dự án
```json
{
  "project_name": "Tower A",
  "location": "Quận Liên Chiểu, Đà Nẵng",
  "developer": "Công ty X",
  "total_units": 200,
  "handover_date": "2027-12-31",
  "amenities": ["hồ bơi", "gym", "khu trẻ em"],
  "legal_status": "đã có sổ hồng"
}
```

## 4. Checklist chuẩn bị dữ liệu (để bạn giao việc)

- [ ] Liệt kê 1-2 dự án đầu tiên (tên, vị trí, chủ đầu tư)
- [ ] Thu thập tài liệu pháp lý của dự án (giấy phép, quy hoạch, hồ sơ pháp lý)
- [ ] Thu thập văn bản luật nền (Luật Đất đai 2024, Luật KDBĐS 2023...)
- [ ] Xin **bảng giá mới nhất** từ phòng kinh doanh (ghi rõ ngày hiệu lực)
- [ ] Xác nhận **ai chịu trách nhiệm nạp giá mới** khi đổi chiến dịch
- [ ] Chuẩn bị file gốc dạng PDF/Word/Excel (không cần làm sạch — script ingest xử lý)
- [ ] **(FINAL PLAN v2 — hạn: trước Ngày 3 implement, data owner)** Bảng giá mẫu **2 campaign version** (≥20 căn, 2-3 dự án, giá trải ~1-10 tỷ) để test freshness + as-of
- [ ] **(FINAL PLAN v2 — hạn: trước Ngày 3 implement, data owner)** **Chính sách vay** theo căn/đợt: `deposit_pct` (vd 20/25/30%), `term_months` (vd 120/180/240), `interest_rate_pct` (vd 7.8-8.5%/năm; ghi rõ NULL nếu chưa có) — tối thiểu 2 policy trên 1 căn mẫu (ngân hàng A vs B) + 1 policy 0% + 1 căn KHÔNG có policy (test edge cases §3.4 plan)

## 5. Quy tắc cập nhật (đã thống nhất)

- **Giá mới**: insert dòng `documents` mới (version 2) + đánh dòng cũ `status='expired'` — KHÔNG xóa lịch sử.
- **Pháp lý hết hiệu lực**: đánh `status='expired'` + set `expiry_date` — tự động bị loại khỏi truy vấn.
- **Sai sót**: sửa file gốc → nạp lại (version mới), không sửa trực tiếp dữ liệu cũ.
