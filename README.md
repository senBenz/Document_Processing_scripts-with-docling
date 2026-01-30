# Docling (Python) — Quick Guide for Document Parsing / Conversion

Docling is an open-source document processing toolkit that helps you **parse and convert** many file types (especially PDFs) into a **unified structured representation** (`DoclingDocument`) and then **export** it to formats like **Markdown, HTML, DocTags, and JSON**.

---

## Why Docling is useful (especially for CV parsing)
When building a CV processing pipeline, you usually need to:
1. Read CV files (PDF/DOCX/image)
2. Extract text + layout (reading order, tables, sections)
3. Export to a developer-friendly format (Markdown/JSON)
4. Apply custom logic (skills, experience, education → structured JSON)

Docling focuses on **steps 1–3**, handling complex document layouts so your code can stay focused on **business logic**.

---

## Key features
- Supports **PDF, DOCX, PPTX, XLSX, HTML**, images (PNG/TIFF/JPEG…)
- Advanced PDF understanding: layout, tables, reading order, code blocks
- Unified internal format: **`DoclingDocument`**
- Export formats: **Markdown, HTML, DocTags, lossless JSON**
- Optional OCR support for scanned documents
- CLI + Python API
- Integrates well with RAG / agent ecosystems (LangChain, LlamaIndex, etc.)

---

## ⚠️ Memory usage & execution considerations (important)
Docling performs **layout analysis, OCR, and document understanding**, which can be **memory-intensive**, especially when:

- Processing **large PDFs**
- Handling **many documents in batch**
- Using **OCR pipelines**
- Combining Docling with **large language models (LLMs)**
- Running parallel conversions

### Recommendations
-  **Local execution** is fine for:
  - Small batches
  - Development & testing
  - Lightweight CV parsing

-  **Cloud execution is recommended** for:
  - Massive CV datasets
  - High-throughput pipelines
  - OCR + LLM workflows
  - Multi-tenant ATS / SaaS systems

Typical cloud setups include:
- Dockerized Docling services
- Execution on **AWS EC2 / ECS / EKS**
- Memory-optimized instances
- Async or queue-based processing (e.g., job per CV)

This approach avoids local memory saturation and improves **scalability, reliability, and throughput**.

---

## Installation
```bash
pip install docling

```


AUTHOR : 

SAAD AAQIL . By community For community ❤️
