#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import requests


DEFAULT_SCHEMA = {
    "personal": {"name": "", "location": "", "phone": "", "email": "", "links": []},
    "summary": "",
    "skills": {"technical": [], "soft": [], "languages": []},
    "experience": [],
    "education": [],
    "projects": [],
}


def run_ocr(ocr_py: Path, pdf_path: Path, ocr_out: Path) -> None:
    """Run OCR.py and write ocr_out JSON."""
    cmd = [
        sys.executable,  # same python running pipeline.py
        str(ocr_py),
        "--pdf",
        str(pdf_path),
        "--out",
        str(ocr_out),
    ]
    print(f"[OCR] Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def build_compact_input(ocr_payload: Dict[str, Any], max_lines: int = 600) -> str:
    """
    Build compact input for the LLM.
    We use lines with [H] heading hints to improve section extraction.
    """
    lines = ocr_payload.get("lines", [])
    if not isinstance(lines, list):
        lines = []

    # Keep only the first N lines (avoid very long context for small models)
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

    # Fallback to raw text if lines are missing
    if not out:
        txt = (ocr_payload.get("text") or "").strip()
        return txt[:12000]  # cap

    return "\n".join(out)


def call_ollama_cv_parser(
    ollama_url: str,
    model: str,
    compact_text: str,
    schema: Dict[str, Any],
    timeout_s: int = 180,
) -> Dict[str, Any]:
    """
    Call Ollama /api/chat using JSON mode.
    Returns parsed JSON dict.
    """
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
        "model": model,
        "stream": False,
        "format": "json",  # IMPORTANT: forces JSON output
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
    }

    print(f"[LLM] POST {ollama_url}/api/chat (model={model})")
    r = requests.post(f"{ollama_url}/api/chat", json=payload, timeout=timeout_s)
    r.raise_for_status()
    data = r.json()

    # Ollama returns the JSON as a string in data["message"]["content"]
    content = data.get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("Ollama returned empty content.")

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        # Helpful debug: save raw response
        raise RuntimeError(
            f"LLM did not return valid JSON. Error: {e}\n--- RAW CONTENT START ---\n{content}\n--- RAW CONTENT END ---"
        )


def main() -> None:
    p = argparse.ArgumentParser(description="Full pipeline: OCR -> Ollama -> structured CV JSON")
    p.add_argument("--pdf", required=True, help="Path to CV PDF")
    p.add_argument("--ocr-py", default="OCR.py", help="Path to OCR.py")
    p.add_argument("--ocr-out", default="ocr_output.json", help="Where OCR JSON is written")
    p.add_argument("--cv-out", default="cv_structured.json", help="Where structured CV JSON is written")
    p.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama base URL")
    p.add_argument("--model", default="llama3:latest", help="Ollama model name")
    p.add_argument("--max-lines", type=int, default=600, help="Max OCR lines to send to LLM")
    args = p.parse_args()

    pdf_path = Path(args.pdf).expanduser().resolve()
    ocr_py = Path(args.ocr_py).expanduser().resolve()
    ocr_out = Path(args.ocr_out).expanduser().resolve()
    cv_out = Path(args.cv_out).expanduser().resolve()

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if not ocr_py.exists():
        raise FileNotFoundError(f"OCR.py not found: {ocr_py}")

    # 1) OCR
    run_ocr(ocr_py=ocr_py, pdf_path=pdf_path, ocr_out=ocr_out)

    # 2) Read OCR output
    ocr_payload = json.loads(ocr_out.read_text(encoding="utf-8"))
    compact = build_compact_input(ocr_payload, max_lines=args.max_lines)

    # 3) Call Ollama to extract structured JSON
    cv_json = call_ollama_cv_parser(
        ollama_url=args.ollama_url,
        model=args.model,
        compact_text=compact,
        schema=DEFAULT_SCHEMA,
    )

    # 4) Save final output
    cv_out.write_text(json.dumps(cv_json, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Wrote: {cv_out}")

    # 5) Print key summary
    personal = cv_json.get("personal", {})
    print("\n=== Extracted (preview) ===")
    print("Name:", personal.get("name", ""))
    print("Email:", personal.get("email", ""))
    print("Phone:", personal.get("phone", ""))
    print("Location:", personal.get("location", ""))
    print("Skills(technical):", len(cv_json.get("skills", {}).get("technical", [])))
    print("Experience entries:", len(cv_json.get("experience", [])))
    print("Education entries:", len(cv_json.get("education", [])))
    print("Projects entries:", len(cv_json.get("projects", [])))


if __name__ == "__main__":
    main()