
import re
import sys
import os
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfdevice import PDFTextDevice

# Auto-detect convert.html next to this script (works locally & on GitHub Actions)
HTML_SOURCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "convert.html")

# ---------------------------------------------------------------------------
# macOS Roman -> byte table (ported from convert.html)
# Used by decodeToOriginalAkruti() to detect & fix Mac Roman-decoded PDFs.
# ---------------------------------------------------------------------------
MAC_OS_ROMAN = [
    '\u00C4', '\u00C5', '\u00C7', '\u00C9', '\u00D1', '\u00D6', '\u00DC', '\u00E1',  # 128-135
    '\u00E0', '\u00E2', '\u00E4', '\u00E3', '\u00E5', '\u00E7', '\u00E9', '\u00E8',  # 136-143
    '\u00EA', '\u00EB', '\u00ED', '\u00EC', '\u00EE', '\u00EF', '\u00F1', '\u00F3',  # 144-151
    '\u00F2', '\u00F4', '\u00F6', '\u00F5', '\u00FA', '\u00F9', '\u00FB', '\u00FC',  # 152-159
    '\u2020', '\u00B0', '\u00A2', '\u00A3', '\u00A7', '\u2022', '\u00B6', '\u00DF',  # 160-167
    '\u00AE', '\u00A9', '\u2122', '\u00B4', '\u00A8', '\u2260', '\u00C6', '\u00D8',  # 168-175
    '\u221E', '\u00B1', '\u2264', '\u2265', '\u00A5', '\u00B5', '\u2202', '\u2211',  # 176-183
    '\u220F', '\u03C0', '\u222B', '\u00AA', '\u00BA', '\u03A9', '\u00E6', '\u00F8',  # 184-191
    '\u00BF', '\u00A1', '\u00AC', '\u221A', '\u0192', '\u2248', '\u2206', '\u00AB',  # 192-199
    '\u00BB', '\u2026', '\u00A0', '\u00C0', '\u00C3', '\u00D5', '\u0152', '\u0153',  # 200-207
    '\u2013', '\u2014', '\u201C', '\u201D', '\u2018', '\u2019', '\u00F7', '\u25CA',  # 208-215
    '\u00FF', '\u0178', '\u2044', '\u20AC', '\u2039', '\u203A', '\uFB01', '\uFB02',  # 216-223
    '\u2021', '\u00B7', '\u201A', '\u201E', '\u2030', '\u00C2', '\u00CA', '\u00C1',  # 224-231
    '\u00CB', '\u00C8', '\u00CD', '\u00CE', '\u00CF', '\u00CC', '\u00D3', '\u00D4',  # 232-239
    '\uF8FF', '\u00D2', '\u00DA', '\u00DB', '\u00D9', '\u0131', '\u02C6', '\u02DC',  # 240-247
    '\u00AF', '\u02D8', '\u02D9', '\u02DA', '\u00B8', '\u02DD', '\u02DB', '\u02C7'  # 248-255
]

# Build reverse map: mac roman unicode char -> original byte char (via latin-1)
DECODE_MAP = {}
for _i, _ch in enumerate(MAC_OS_ROMAN):
    DECODE_MAP[_ch] = chr(_i + 128)
DECODE_MAP['\u03BC'] = chr(181)  # mu -> 0xB5


def decode_to_original_akruti(text: str) -> str:
    """
    Port of decodeToOriginalAkruti() from convert.html.
    Detects whether the text was decoded via WinAnsi (correct) or
    Mac Roman (wrong), and fixes it back if needed.
    """
    win_ansi_score = len(re.findall(r'[ûôöÿ]', text))
    mac_roman_score = len(re.findall(r'[\u02DB\u0131\u02C6\u02C7\uFB01\uFB02]', text))

    if win_ansi_score >= mac_roman_score and win_ansi_score > 0:
        return text  # Already healthy WinAnsi Akruti — do nothing

    if mac_roman_score > 0:
        fixed = []
        for ch in text:
            fixed.append(DECODE_MAP.get(ch, ch))
        return "".join(fixed)

    return text


# ---------------------------------------------------------------------------
# Load text_array from convert.html
# ---------------------------------------------------------------------------
def _unescape_js_string(s: str) -> str:
    """Unescape JS double-quoted string literal contents."""
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if   nxt == "\\": out.append("\\"); i += 2; continue
            elif nxt == '"':  out.append('"');  i += 2; continue
            elif nxt == "n":  out.append("\n"); i += 2; continue
            elif nxt == "t":  out.append("\t"); i += 2; continue
            elif nxt == "u" and i + 5 < len(s):
                hex4 = s[i+2:i+6]
                if all(c in '0123456789abcdefABCDEF' for c in hex4):
                    out.append(chr(int(hex4, 16))); i += 6; continue
            out.append(nxt); i += 2; continue
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
# Byte -> character decode table (CP1252 + Latin-1 fallback for 5 gap bytes)
# ---------------------------------------------------------------------------
def _build_byte_decode_table():
    table = {}
    for b in range(256):
        try:
            table[b] = bytes([b]).decode("cp1252")
        except UnicodeDecodeError:
            table[b] = chr(b)   # 0x81,0x8D,0x8F,0x90,0x9D -> raw Latin-1
    return table


BYTE_DECODE_TABLE = _build_byte_decode_table()


def decode_legacy_bytes(raw: bytes) -> str:
    return "".join(BYTE_DECODE_TABLE[b] for b in raw)


# ---------------------------------------------------------------------------
# convertToUnicodeOdia — ported from convert.html (cluster-regex version)
# ---------------------------------------------------------------------------
CONS    = "କଖଗଘଙଚଛଜଝଞଟଠଡଡ଼ଢଢ଼ଣତଥଦଧନପଫବଭମଯୟରଲଳଵୱଶଷସହକ୍ଷଜ୍ଞ"
MATRAS  = "ାିୀୁୂୃେୈୋୌଂଁ଼"
# A consonant cluster: one or more (C + virama) followed by a final consonant (optionally nukta)
CLUSTER = r"(?:[" + CONS + r"]୍)*[" + CONS + r"]଼?"


def convert_legacy_to_unicode(s: str) -> str:
    """Port of convertToUnicodeOdia() from convert.html."""
    if not s:
        return s

    # Run substitution table
    for k, v in TEXT_ARRAY:
        if k == "":
            continue
        while k in s:
            s = s.replace(k, v)

    # e-matra (ù) reordering: move ù after its consonant cluster
    s = re.sub(r"([ù])(" + CLUSTER + ")", r"\2\1", s)
    s = s.replace("ùø", "ୌ")
    s = s.replace("ùା", "ୋ")
    s = s.replace("ù÷", "ୈ")
    s = s.replace("ù",  "େ")

    # reph (ð) reordering: move ð before its consonant cluster+matras
    s = re.sub(r"(" + CLUSTER + r")([" + MATRAS + r"]*)ð", r"ð\1\2", s)
    s = s.replace("ð", "ର୍")

    # anusvara/chandrabindu before matra -> swap
    s = re.sub(r"([ଂଁ])([ାିୀୁୂୃେୈୋୌ])", r"\2\1", s)

    # matra before virama+consonant -> swap (twice for stacked clusters)
    s = re.sub(r"([" + MATRAS + r"])([୍][" + CONS + r"])", r"\2\1", s)
    s = re.sub(r"([" + MATRAS + r"])([୍][" + CONS + r"])", r"\2\1", s)

    return s


# ---------------------------------------------------------------------------
# PDF glyph extractor
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Font classification: Latin (English headings/numbers) vs Odia glyph font
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Reconstruct text lines from glyph positions and convert
# ---------------------------------------------------------------------------
def glyphs_to_text(glyphs, latin_fonts, y_tolerance=2.0):
    if not glyphs:
        return ""

    # Sort top-to-bottom, left-to-right
    glyphs_sorted = sorted(glyphs, key=lambda g: (-g.y, g.x))

    # Group into lines by y-position
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

        # Split into runs of same kind (latin vs odia)
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
                text = decode_to_original_akruti(text)   # fix Mac Roman if needed
                text = convert_legacy_to_unicode(text)
            else:
                text = raw.decode("cp1252", errors="replace")
            pieces.append(text)
        out_lines.append("".join(pieces))

    return "\n".join(out_lines)


# ---------------------------------------------------------------------------
# Main conversion entry point
# ---------------------------------------------------------------------------
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
    ap.add_argument("--end",   type=int, default=None)
    args = ap.parse_args()

    pr = None
    if args.start is not None or args.end is not None:
        pr = range(args.start or 0, args.end or get_page_count(args.pdf))

    text = convert_pdf(args.pdf, page_range=pr)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(text)
    print("Wrote", args.output)
PYEOF