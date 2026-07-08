"""
Akruti/Sarala-encoded PDF -> Unicode Odia converter.

Core fix over the previous browser-based tool:
  1. Reads the PDF's actual embedded glyph codes (raw 8-bit codes per the
     font's own encoding), instead of trusting pdf.js/pdfminer's guessed
     Unicode-lookalike substitution characters.
  2. Decodes those raw byte codes with CP1252 (the codepage the legacy
     Akruti/Sarala font keyboards were built against) to recover the
     original legacy Odia text exactly as it was typed.
  3. Detects, per PDF font, whether that font is a genuine Latin/English
     font (e.g. headings in English, page numbers) vs an Akruti-Odia glyph
     font, and only converts the latter -- this prevents English headings
     like "(HEREDITY AND EVOLUTION)" from being mangled into Odia glyphs.
  4. Reconstructs proper reading order per line using x/y glyph positions
     (necessary because Akruti text is stored as visually-ordered glyphs,
     not logically-ordered Unicode).
  5. Runs the legacy->Unicode substitution table (ported faithfully from
     convert-1-2.html) plus the matra/reph reordering rules needed to turn
     visual glyph order into correct logical Unicode Odia order.
"""
import re
import sys
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfdevice import PDFTextDevice

HTML_SOURCE = "/mnt/user-data/uploads/convert-1-2.html"


def _unescape_js_string(s: str) -> str:
    """Unescape a JS double-quoted string literal's contents (e.g. \\\\ -> \\)."""
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == "\\":
                out.append("\\")
                i += 2
                continue
            elif nxt == '"':
                out.append('"')
                i += 2
                continue
            elif nxt == "n":
                out.append("\n")
                i += 2
                continue
            elif nxt == "t":
                out.append("\t")
                i += 2
                continue
            else:
                out.append(nxt)
                i += 2
                continue
        out.append(c)
        i += 1
    return "".join(out)


def load_text_array(html_path=HTML_SOURCE):
    html = open(html_path, encoding="utf-8").read()
    m = re.search(r"const text_array = \[(.*?)\];", html, re.S)
    if not m:
        raise RuntimeError("Could not find text_array in " + html_path)
    items = re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))
    items = [_unescape_js_string(it) for it in items]
    pairs = []
    for i in range(0, len(items) - 1, 2):
        pairs.append((items[i], items[i + 1]))
    return pairs


TEXT_ARRAY = load_text_array()

# ---------------------------------------------------------------------------
# Byte -> character decode table used for the legacy Akruti/Sarala font bytes.
#
# The legacy table's keys are mostly CP1252 characters (Windows-1252), but
# CP1252 leaves five byte slots undefined: 0x81, 0x8D, 0x8F, 0x90, 0x9D.
# The original Akruti font keyboard used those slots too (for extra
# conjuncts), and the existing conversion table encodes them as their raw
# Latin-1 codepoint (e.g. byte 0x8F -> U+008F) rather than a CP1252 mapping.
# Blindly decoding as CP1252 turns those bytes into the U+FFFD replacement
# character ("leaked"/mangled glyphs) since Python's cp1252 codec has no
# mapping for them. We patch a decode table that uses CP1252 everywhere it
# is defined, and falls back to the raw Latin-1 codepoint for the 5 gaps.
# ---------------------------------------------------------------------------
def _build_byte_decode_table():
    table = {}
    for b in range(256):
        try:
            table[b] = bytes([b]).decode("cp1252")
        except UnicodeDecodeError:
            table[b] = chr(b)  # CP1252 gap -> raw Latin-1 codepoint passthrough
    return table


BYTE_DECODE_TABLE = _build_byte_decode_table()


def decode_legacy_bytes(raw: bytes) -> str:
    return "".join(BYTE_DECODE_TABLE[b] for b in raw)

CONSONANTS_1 = "କଖଗଘଙଚଛଜଝଞଟଠଡଡ଼ଢଢ଼ଣତଥଦଧନପଫବଭମଯୟରଲବୱଶଷସହକ୍ଷଡ଼ଳ"
CONSONANTS_2 = "କଖଗଘଚଛଜଝଟଠଡଡ଼ଢଢ଼ଣତଥନପଫବଭମୟରଲବୱଶଷସହକ୍ଷଡ଼ଳ"
CONSONANTS_3 = "କଖଗଘଚଛଜଝଟଠଡଡ଼ଢଢ଼ଣତଥଦଧନପଫବଭମଯରଲଳଵଶଷସହକ୍ଷଜ୍ଞୟ"
CONSONANTS_4 = "କଖଗଘଙଚଛଜଝଞଟଠଡଡ଼ଢଢ଼ଣତଥଦଧନପଫବଭମଯୟରଲଳଵଶଷସହ"
MATRAS = "ାିୀୁୂୃେୈୋୌଂଁ"


def convert_legacy_to_unicode(s: str) -> str:
    """Faithful port of convertToUnicodeOdia() from convert-1-2.html."""
    if not s:
        return s
    for k, v in TEXT_ARRAY:
        if k == "":
            continue
        while k in s:
            s = s.replace(k, v)

    s = re.sub(r"([ù])([" + CONSONANTS_1 + "])", r"\2\1", s)
    s = re.sub(r"([ù])([୍])([" + CONSONANTS_2 + "])", r"\2\3\1", s)
    s = re.sub(r"([ù])([୍])([" + CONSONANTS_2 + "])", r"\2\3\1", s)
    s = s.replace("ùø", "ୌ")
    s = s.replace("ùା", "ୋ")
    s = s.replace("ù÷", "ୈ")
    s = s.replace("ù", "େ")

    s = re.sub(r"([" + CONSONANTS_3 + "])([" + MATRAS + r"]*)à", r"ð\1\2", s)
    s = re.sub(r"([" + CONSONANTS_3 + "])([" + MATRAS + r"]*)ð", r"ð\1\2", s)
    s = re.sub(r"([" + CONSONANTS_3 + "])([୍])à", r"ð\1\2", s)
    s = re.sub(r"([" + CONSONANTS_3 + "])([୍])ð", r"ð\1\2", s)
    s = s.replace("ð", "ର୍")
    s = re.sub(r"([ଂଁ])([ାିୀୁୂୃେୈୋୌ])", r"\2\1", s)

    s = re.sub(r"([ାିୀୁୂୃେୈୋୌଂଁ])([୍][" + CONSONANTS_4 + "])", r"\2\1", s)
    return s


class _RawGlyph:
    __slots__ = ("x", "y", "font", "code")

    def __init__(self, x, y, font, code):
        self.x, self.y, self.font, self.code = x, y, font, code


def extract_page_glyphs(pdf_path, page_index):
    glyphs = []

    class _Device(PDFTextDevice):
        def render_string(self, textstate, seq, ncs, graphicstate):
            font = textstate.font
            m = textstate.matrix
            x, y = m[4], m[5]
            for obj in seq:
                if isinstance(obj, bytes):
                    for code in font.decode(obj):
                        if isinstance(code, int):
                            glyphs.append(_RawGlyph(x, y, font.fontname, code))
                            try:
                                w = font.char_width(code)
                            except Exception:
                                w = 0.5
                            x += (w * textstate.fontsize + textstate.charspace) * textstate.scaling / 100.0
                    textstate.linematrix = (x, y)
                elif isinstance(obj, (int, float)):
                    x -= obj / 1000.0 * textstate.fontsize * textstate.scaling / 100.0

    with open(pdf_path, "rb") as f:
        parser = PDFParser(f)
        doc = PDFDocument(parser)
        rsrcmgr = PDFResourceManager()
        device = _Device(rsrcmgr)
        interp = PDFPageInterpreter(rsrcmgr, device)
        for i, page in enumerate(PDFPage.create_pages(doc)):
            if i == page_index:
                interp.process_page(page)
                break
            if i > page_index:
                break
    return glyphs


def get_page_count(pdf_path):
    with open(pdf_path, "rb") as f:
        parser = PDFParser(f)
        doc = PDFDocument(parser)
        return sum(1 for _ in PDFPage.create_pages(doc))


def classify_fonts(glyphs, ascii_threshold=0.97):
    from collections import defaultdict
    codes_by_font = defaultdict(list)
    for g in glyphs:
        codes_by_font[g.font].append(g.code)

    latin_fonts = set()
    for font, codes in codes_by_font.items():
        if not codes:
            continue
        ascii_ratio = sum(1 for c in codes if 32 <= c < 127) / len(codes)
        if ascii_ratio >= ascii_threshold:
            latin_fonts.add(font)
    return latin_fonts


def glyphs_to_text(glyphs, latin_fonts, y_tolerance=2.0):
    if not glyphs:
        return ""

    glyphs_sorted = sorted(glyphs, key=lambda g: (-g.y, g.x))
    lines = []
    current_line = []
    current_y = None
    for g in glyphs_sorted:
        if current_y is None or abs(g.y - current_y) <= y_tolerance:
            current_line.append(g)
            current_y = g.y if current_y is None else current_y
        else:
            lines.append(current_line)
            current_line = [g]
            current_y = g.y
    if current_line:
        lines.append(current_line)

    out_lines = []
    for line in lines:
        line_sorted = sorted(line, key=lambda g: g.x)
        runs = []
        cur_kind = None
        cur_bytes = []
        for g in line_sorted:
            kind = "latin" if g.font in latin_fonts else "odia"
            if kind != cur_kind and cur_bytes:
                runs.append((cur_kind, cur_bytes))
                cur_bytes = []
            cur_kind = kind
            cur_bytes.append(g.code)
        if cur_bytes:
            runs.append((cur_kind, cur_bytes))

        pieces = []
        for kind, codes in runs:
            raw = bytes(c for c in codes if 0 <= c <= 255)
            if kind == "odia":
                text = decode_legacy_bytes(raw)
                text = convert_legacy_to_unicode(text)
            else:
                text = raw.decode("cp1252", errors="replace")
            pieces.append(text)
        out_lines.append("".join(pieces))

    return "\n".join(out_lines)


def convert_pdf(pdf_path, page_range=None, progress=True):
    total_pages = get_page_count(pdf_path)
    if page_range is None:
        page_range = range(total_pages)
    out = []
    for pno in page_range:
        glyphs = extract_page_glyphs(pdf_path, pno)
        latin_fonts = classify_fonts(glyphs)
        page_text = glyphs_to_text(glyphs, latin_fonts)
        out.append(page_text)
        if progress and pno % 10 == 0:
            print(f"  processed page {pno + 1}/{total_pages}", file=sys.stderr)
    return "\n\n".join(out)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-o", "--output", default="output_unicode.txt")
    ap.add_argument("--start", type=int, default=None)
    ap.add_argument("--end", type=int, default=None)
    args = ap.parse_args()

    pr = None
    if args.start is not None or args.end is not None:
        pr = range(args.start or 0, args.end or get_page_count(args.pdf))

    text = convert_pdf(args.pdf, page_range=pr)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(text)
    print("Wrote", args.output)
