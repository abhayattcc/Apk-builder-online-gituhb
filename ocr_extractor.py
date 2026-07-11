"""
PDF OCR Text Extractor using Google Cloud Vision API
=====================================================
Supports multilingual OCR including mixed-language content.
Example: "abhaya is ଭଲ बचा हे ।" — English + Odia + Hindi all detected.

Usage:
    python ocr_extractor.py input.pdf
    python ocr_extractor.py input.pdf --output result.txt
    python ocr_extractor.py input.pdf --dpi 300 --output result.txt
"""

import argparse
import base64
import io
import json
import os
import sys
import time
from pathlib import Path

# ── Third-party imports ──────────────────────────────────────────────────────
try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("❌ PyMuPDF not found. Run:  pip install pymupdf")

try:
    from google.cloud import vision
except ImportError:
    sys.exit("❌ google-cloud-vision not found. Run:  pip install google-cloud-vision")


# ═════════════════════════════════════════════════════════════════════════════
#  Configuration
# ═════════════════════════════════════════════════════════════════════════════

DEFAULT_DPI   = 300          # Higher DPI → better accuracy on small fonts
MAX_RETRIES   = 3            # Retry on transient Vision API errors
RETRY_DELAY   = 2.0          # Seconds between retries
SEPARATOR     = "─" * 72     # Visual separator in output


# ═════════════════════════════════════════════════════════════════════════════
#  Google Cloud Vision helpers
# ═════════════════════════════════════════════════════════════════════════════

def build_vision_client() -> vision.ImageAnnotatorClient:
    """
    Build a Vision API client.
    Credentials are resolved in this order (standard Google ADC chain):
      1. GOOGLE_APPLICATION_CREDENTIALS env var (path to service-account JSON)
      2. gcloud application-default login
      3. Metadata server (when running on GCP)
    """
    return vision.ImageAnnotatorClient()


def ocr_image_bytes(client: vision.ImageAnnotatorClient, image_bytes: bytes) -> dict:
    """
    Send raw image bytes to Cloud Vision TEXT_DETECTION.

    Returns a dict with:
        full_text  – complete extracted string
        languages  – list of detected language codes with confidence
        blocks     – raw TextAnnotation blocks for debugging
    """
    image   = vision.Image(content=image_bytes)
    request = vision.AnnotateImageRequest(
        image=image,
        features=[
            vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION),
        ],
        image_context=vision.ImageContext(
            # Hint: empty list = auto-detect all languages
            language_hints=[],
        ),
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.annotate_image(request=request)
            break
        except Exception as exc:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"Vision API failed after {MAX_RETRIES} attempts: {exc}") from exc
            print(f"  ⚠  Attempt {attempt} failed ({exc}), retrying …", file=sys.stderr)
            time.sleep(RETRY_DELAY * attempt)

    if response.error.message:
        raise RuntimeError(f"Vision API error: {response.error.message}")

    annotation  = response.full_text_annotation
    full_text   = annotation.text if annotation else ""

    # Collect detected languages from every page block
    langs: dict[str, float] = {}
    if annotation:
        for page in annotation.pages:
            for prop in page.property.detected_languages:
                code  = prop.language_code or "und"
                conf  = prop.confidence or 0.0
                langs[code] = max(langs.get(code, 0.0), conf)

    return {
        "full_text" : full_text,
        "languages" : sorted(langs.items(), key=lambda x: -x[1]),
        "blocks"    : annotation.pages if annotation else [],
    }


# ═════════════════════════════════════════════════════════════════════════════
#  PDF → image conversion
# ═════════════════════════════════════════════════════════════════════════════

def pdf_to_images(pdf_path: str, dpi: int) -> list[bytes]:
    """
    Render every PDF page to a PNG image in memory using PyMuPDF.
    Returns a list of raw PNG bytes, one per page.
    """
    doc    = fitz.open(pdf_path)
    matrix = fitz.Matrix(dpi / 72, dpi / 72)   # 72 pt/inch is PDF base resolution
    images = []

    for page_num, page in enumerate(doc, start=1):
        print(f"  📄 Rendering page {page_num}/{len(doc)} …", flush=True)
        pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB, alpha=False)
        images.append(pix.tobytes("png"))

    doc.close()
    return images


# ═════════════════════════════════════════════════════════════════════════════
#  Main extraction pipeline
# ═════════════════════════════════════════════════════════════════════════════

def extract_text_from_pdf(pdf_path: str, dpi: int = DEFAULT_DPI) -> dict:
    """
    Full pipeline: PDF → page images → Cloud Vision OCR → structured result.

    Returns:
        {
            "pdf_path"      : str,
            "total_pages"   : int,
            "all_languages" : list of (code, confidence),
            "pages"         : [
                {
                    "page"      : int,
                    "text"      : str,
                    "languages" : list of (code, confidence),
                },
                …
            ],
            "full_text"     : str   # all pages joined
        }
    """
    print(f"\n{'═'*72}")
    print(f"  PDF OCR Extractor  –  Google Cloud Vision API")
    print(f"{'═'*72}")
    print(f"  File : {pdf_path}")
    print(f"  DPI  : {dpi}")
    print()

    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Step 1 – render pages
    print("🖼  Rendering PDF pages to images …")
    page_images = pdf_to_images(pdf_path, dpi)
    total       = len(page_images)
    print(f"  ✓ {total} page(s) rendered\n")

    # Step 2 – build Vision client
    print("🔑 Connecting to Google Cloud Vision …")
    client = build_vision_client()
    print("  ✓ Client ready\n")

    # Step 3 – OCR each page
    print("🔍 Running OCR …")
    pages_result : list[dict] = []
    lang_pool    : dict[str, float] = {}

    for idx, img_bytes in enumerate(page_images, start=1):
        print(f"  Page {idx}/{total} …", end=" ", flush=True)
        result = ocr_image_bytes(client, img_bytes)
        pages_result.append({
            "page"      : idx,
            "text"      : result["full_text"],
            "languages" : result["languages"],
        })

        # Accumulate language detections across all pages
        for code, conf in result["languages"]:
            lang_pool[code] = max(lang_pool.get(code, 0.0), conf)

        lang_str = ", ".join(f"{c}({v:.0%})" for c, v in result["languages"]) or "—"
        print(f"✓  [{lang_str}]")

    all_langs   = sorted(lang_pool.items(), key=lambda x: -x[1])
    joined_text = "\n\n".join(p["text"] for p in pages_result)

    print(f"\n  ✓ OCR complete  |  Languages detected: "
          f"{', '.join(c for c, _ in all_langs) or 'none'}\n")

    return {
        "pdf_path"      : pdf_path,
        "total_pages"   : total,
        "all_languages" : all_langs,
        "pages"         : pages_result,
        "full_text"     : joined_text,
    }


# ═════════════════════════════════════════════════════════════════════════════
#  Output formatting
# ═════════════════════════════════════════════════════════════════════════════

def format_report(result: dict) -> str:
    """
    Build a human-readable OCR report string from the extraction result.
    """
    lines = []

    lines.append("═" * 72)
    lines.append("  OCR EXTRACTION REPORT")
    lines.append("═" * 72)
    lines.append(f"  Source file  : {result['pdf_path']}")
    lines.append(f"  Total pages  : {result['total_pages']}")

    langs = result["all_languages"]
    if langs:
        lang_detail = "  |  ".join(f"{c} ({v:.0%})" for c, v in langs)
        lines.append(f"  Languages    : {lang_detail}")
    else:
        lines.append("  Languages    : (none detected)")

    lines.append("")

    for page in result["pages"]:
        lines.append(SEPARATOR)
        page_langs = ", ".join(f"{c}({v:.0%})" for c, v in page["languages"]) or "—"
        lines.append(f"  PAGE {page['page']}   [{page_langs}]")
        lines.append(SEPARATOR)
        text = page["text"].strip()
        lines.append(text if text else "(no text detected on this page)")
        lines.append("")

    lines.append("═" * 72)
    lines.append("  END OF REPORT")
    lines.append("═" * 72)

    return "\n".join(lines)


def save_outputs(result: dict, output_path: str) -> None:
    """
    Save both a formatted .txt report and a machine-readable .json file.
    """
    txt_path  = output_path
    json_path = str(Path(output_path).with_suffix(".json"))

    # ── Text report ──────────────────────────────────────────────────────────
    report = format_report(result)
    Path(txt_path).write_text(report, encoding="utf-8")
    print(f"📝 Text report  → {txt_path}")

    # ── JSON (serialise language tuples → lists) ──────────────────────────────
    serialisable = {
        "pdf_path"      : result["pdf_path"],
        "total_pages"   : result["total_pages"],
        "all_languages" : result["all_languages"],
        "full_text"     : result["full_text"],
        "pages"         : [
            {
                "page"      : p["page"],
                "text"      : p["text"],
                "languages" : p["languages"],
            }
            for p in result["pages"]
        ],
    }
    Path(json_path).write_text(
        json.dumps(serialisable, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"📦 JSON data    → {json_path}")


# ═════════════════════════════════════════════════════════════════════════════
#  CLI entry point
# ═════════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract text from a PDF using Google Cloud Vision OCR.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ocr_extractor.py scan.pdf
  python ocr_extractor.py scan.pdf --output results/output.txt
  python ocr_extractor.py scan.pdf --dpi 400 --output hi_res.txt

Environment:
  GOOGLE_APPLICATION_CREDENTIALS  Path to service-account JSON key file.
        """,
    )
    parser.add_argument("pdf", help="Path to the input PDF file")
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output .txt file path (default: <pdf_name>_ocr.txt beside the PDF)",
    )
    parser.add_argument(
        "--dpi", "-d",
        type=int,
        default=DEFAULT_DPI,
        help=f"Render resolution in DPI (default: {DEFAULT_DPI})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    pdf_path = args.pdf
    dpi      = args.dpi

    # Default output path: same directory as PDF, with _ocr.txt suffix
    if args.output:
        output_path = args.output
    else:
        stem        = Path(pdf_path).stem
        parent      = Path(pdf_path).parent
        output_path = str(parent / f"{stem}_ocr.txt")

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Run extraction
    result = extract_text_from_pdf(pdf_path=pdf_path, dpi=dpi)

    # Save outputs
    save_outputs(result, output_path)

    # Print summary to console
    print()
    print(format_report(result))


if __name__ == "__main__":
    main()
