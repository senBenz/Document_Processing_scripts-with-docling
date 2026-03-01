#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse

# Import your OCR function directly (preferred) instead of subprocess
from OCR import extract_structured_ocr

app = FastAPI(title="CV Processing API", version="1.0")

DEFAULT_SCHEMA = {
    "personal": {"name": "", "location": "", "phone": "", "email": "", "links": []},
    "summary": "",
    "skills": {"technical": [], "soft": [], "languages": []},
    "experience": [],
    "education": [],
    "projects": [],
}

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3:latest"


def build_compact_input(ocr_payload: Dict[str, Any], max_lines: int = 600) -> str:
    lines = ocr_payload.get("lines", [])
    if not isinstance(lines, list):
        lines = []
    lines = lines[:max_lines]

    out = []
    for l in lines:
        text = (l.get("text") or "").strip()
        if not text:
            continue
        if l.get("is_heading_candidate"):
            out.append(f"[H] {text}")
        else:
            out.append(text)

    if not out:
        txt = (ocr_payload.get("text") or "").strip()
        return txt[:12000]

    return "\n".join(out)


def call_ollama(compact_text: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    system_msg = (
        "You are a CV parsing engine. Output ONLY valid JSON. "
        "No explanations. No markdown. Do not invent missing data."
    )

    user_msg = (
        "Extract the CV into this schema exactly:\n\n"
        f"{json.dumps(schema, ensure_ascii=False)}\n\n"
        "Rules:\n"
        "- If missing, use empty strings or empty arrays.\n"
        "- Do not invent data.\n"
        "- Copy dates exactly as written.\n"
        "- Output ONLY JSON.\n\n"
        "OCR LINES (lines starting with [H] are likely section headers):\n"
        f"{compact_text}"
    )

    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
    }

    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=180)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Ollama error: {r.text}")

    data = r.json()
    content = data.get("message", {}).get("content", "")
    if not content:
        raise HTTPException(status_code=502, detail="Ollama returned empty content")

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # return raw content to debug
        raise HTTPException(
            status_code=502,
            detail={"error": "Invalid JSON returned by LLM", "raw": content[:4000]},
        )


@app.get("/health")
def health():
    # quick check if Ollama is reachable
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        ok = r.status_code == 200
    except Exception:
        ok = False
    return {"ok": True, "ollama_reachable": ok, "model": OLLAMA_MODEL}


@app.post("/parse-cv")
async def parse_cv(
    file: UploadFile = File(...),
    lang: str = "eng+fra",
    dpi: int = 300,
    min_conf: int = 60,
    max_lines: int = 600,
):
    """
    Upload a PDF CV -> returns structured JSON from Llama3 via Ollama.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    with tempfile.TemporaryDirectory() as td:
        pdf_path = Path(td) / "cv.pdf"
        pdf_path.write_bytes(await file.read())

        # 1) OCR
        text, ocr_payload = extract_structured_ocr(
            pdf_path=str(pdf_path),
            lang=lang,
            dpi=dpi,
            min_conf=min_conf,
            poppler_path=None,
        )

        # 2) Build compact input
        compact = build_compact_input(ocr_payload, max_lines=max_lines)

        # 3) LLM -> JSON
        cv_json = call_ollama(compact, DEFAULT_SCHEMA)

        return JSONResponse(
            content={
                "cv": cv_json,
                "meta": {
                    "ocr_stats": ocr_payload.get("stats", {}),
                    "lang": lang,
                    "dpi": dpi,
                    "min_conf": min_conf,
                    "model": OLLAMA_MODEL,
                },
            }
        )


@app.post("/parse-cv/save")
async def parse_cv_and_save(
    file: UploadFile = File(...),
    out_dir: str = "runs",
    lang: str = "eng+fra",
    dpi: int = 300,
    min_conf: int = 60,
    max_lines: int = 600,
):
    """
    Same as /parse-cv but also saves artifacts to disk:
    - ocr_output.json
    - cv_structured.json
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    run_dir = Path(out_dir) / Path(file.filename).stem
    run_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = run_dir / "input.pdf"
    pdf_path.write_bytes(await file.read())

    text, ocr_payload = extract_structured_ocr(
        pdf_path=str(pdf_path),
        lang=lang,
        dpi=dpi,
        min_conf=min_conf,
        poppler_path=None,
    )

    (run_dir / "ocr_output.json").write_text(
        json.dumps(ocr_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    compact = build_compact_input(ocr_payload, max_lines=max_lines)
    cv_json = call_ollama(compact, DEFAULT_SCHEMA)

    (run_dir / "cv_structured.json").write_text(
        json.dumps(cv_json, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "saved_to": str(run_dir),
        "cv": cv_json,
        "meta": {"ocr_stats": ocr_payload.get("stats", {}), "model": OLLAMA_MODEL},
    }