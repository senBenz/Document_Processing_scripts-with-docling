from __future__ import annotations

"""OCR pipeline for CV PDFs."""

import argparse
import json
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np
import pytesseract
from pdf2image import convert_from_path


# ----------------------------
# Preprocessing
# ----------------------------

def preprocess_image(pil_image) -> np.ndarray:
    img = np.array(pil_image)

    if img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 3)

    thr = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        2,
    )

    return thr


def deskew(binary_img: np.ndarray) -> np.ndarray:
    if binary_img.ndim != 2:
        raise ValueError("deskew() expects a single-channel image")

    inv = cv2.bitwise_not(binary_img)
    coords = np.column_stack(np.where(inv > 0))

    if coords.size == 0:
        return binary_img

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    (h, w) = binary_img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)

    rotated = cv2.warpAffine(
        binary_img,
        M,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )

    return rotated


# ----------------------------
# OCR structures
# ----------------------------

@dataclass
class OCRWord:
    text: str
    conf: int
    page: int
    block: int
    par: int
    line: int
    word: int
    left: int
    top: int
    width: int
    height: int


@dataclass
class OCRLine:
    text: str
    conf_avg: float
    page: int
    block: int
    par: int
    line: int
    left: int
    top: int
    width: int
    height: int
    is_heading_candidate: bool


def _looks_like_heading(line_text: str) -> bool:
    s = line_text.strip()
    if not s:
        return False

    tokens = re.findall(r"[\wÀ-ÿ]+", s)
    if len(tokens) > 7:
        return False

    if s[-1] in ".,;":
        return False

    letters = [c for c in s if c.isalpha()]
    if letters:
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if upper_ratio > 0.75:
            return True

    if tokens and all(t[0].isupper() for t in tokens if t):
        return True

    return False


def extract_structured_ocr(
    pdf_path: str,
    lang: str = "eng+fra",
    dpi: int = 300,
    min_conf: int = 60,
    poppler_path: str | None = None,
) -> Tuple[str, Dict[str, Any]]:

    pages = convert_from_path(pdf_path, dpi=dpi, poppler_path=poppler_path)

    all_words: List[OCRWord] = []
    all_lines: List[OCRLine] = []

    for page_idx, page in enumerate(pages, start=1):
        img = preprocess_image(page)
        img = deskew(img)

        data = pytesseract.image_to_data(
            img,
            lang=lang,
            output_type=pytesseract.Output.DICT,
        )

        n = len(data.get("text", []))
        for i in range(n):
            raw = (data["text"][i] or "").strip()
            if not raw:
                continue

            try:
                conf = int(float(data["conf"][i]))
            except Exception:
                conf = -1

            if conf < min_conf:
                continue

            all_words.append(
                OCRWord(
                    text=raw,
                    conf=conf,
                    page=page_idx,
                    block=int(data["block_num"][i]),
                    par=int(data["par_num"][i]),
                    line=int(data["line_num"][i]),
                    word=int(data["word_num"][i]),
                    left=int(data["left"][i]),
                    top=int(data["top"][i]),
                    width=int(data["width"][i]),
                    height=int(data["height"][i]),
                )
            )

    all_words.sort(key=lambda w: (w.page, w.block, w.par, w.line, w.word))

    line_map: Dict[Tuple[int, int, int, int], List[OCRWord]] = {}
    for w in all_words:
        key = (w.page, w.block, w.par, w.line)
        line_map.setdefault(key, []).append(w)

    full_text_lines: List[str] = []

    for (page, block, par, line_no), words in sorted(line_map.items()):
        parts: List[str] = []
        for w in words:
            if not parts:
                parts.append(w.text)
                continue

            if re.match(r"^[\]\)\}\,\.;:\?!]$", w.text):
                parts[-1] = parts[-1] + w.text
            else:
                parts.append(w.text)

        line_text = " ".join(parts).strip()
        if not line_text:
            continue

        confs = [w.conf for w in words]
        conf_avg = float(sum(confs)) / float(len(confs)) if confs else 0.0

        left = min(w.left for w in words)
        top = min(w.top for w in words)
        right = max(w.left + w.width for w in words)
        bottom = max(w.top + w.height for w in words)

        is_heading = _looks_like_heading(line_text)

        all_lines.append(
            OCRLine(
                text=line_text,
                conf_avg=conf_avg,
                page=page,
                block=block,
                par=par,
                line=line_no,
                left=int(left),
                top=int(top),
                width=int(right - left),
                height=int(bottom - top),
                is_heading_candidate=is_heading,
            )
        )

        full_text_lines.append(line_text)

    full_text = "\n".join(full_text_lines).strip()

    payload: Dict[str, Any] = {
        "pdf": pdf_path,
        "lang": lang,
        "dpi": dpi,
        "min_conf": min_conf,
        "stats": {
            "pages": len(pages),
            "words": len(all_words),
            "lines": len(all_lines),
        },
        "text": full_text,
        "lines": [asdict(l) for l in all_lines],
        "words": [asdict(w) for w in all_words],
    }

    return full_text, payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract structured OCR from a CV PDF")
    parser.add_argument("--pdf", default="CV_.pdf")
    parser.add_argument("--out", default=None)
    parser.add_argument("--lang", default="eng+fra")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--min-conf", type=int, default=60)
    parser.add_argument("--poppler-path", default=None)
    args = parser.parse_args()

    text, payload = extract_structured_ocr(
        pdf_path=args.pdf,
        lang=args.lang,
        dpi=args.dpi,
        min_conf=args.min_conf,
        poppler_path=args.poppler_path,
    )

    print(text)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()