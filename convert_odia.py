"""
Akruti/Sarala-encoded PDF -> Unicode Odia converter.
Exactly ported from the JavaScript logic in convert.html (Structure Preservation + English Isolation).
"""
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
# macOS Roman -> byte table (Needed for corrupted PDF encodings)
# ---------------------------------------------------------------------------
MAC_OS_ROMAN = [
    '\u00C4', '\u00C5', '\u00C7', '\u00C9', '\u00D1', '\u00D6', '\u00DC', '\u00E1',
    '\u00E0', '\u00E2', '\u00E4', '\u00E3', '\u00E5', '\u00E7', '\u00E9', '\u00E8',
    '\u00EA', '\u00EB', '\u00ED', '\u00EC', '\u00EE', '\u00EF', '\u00F1', '\u00F3',
    '\u00F2', '\u00F4', '\u00F6', '\u00F5', '\u00FA', '\u00F9', '\u00FB', '\u00FC',
    '\u2020', '\u00B0', '\u00A2', '\u00A3', '\u00A7', '\u2022', '\u00B6', '\u00DF',
    '\u00AE', '\u00A9', '\u2122', '\u00B4', '\u00A8', '\u2260', '\u00C6', '\u00D8',
    '\u221E', '\u00B1', '\u2264', '\u2265', '\u00A5', '\u00B5', '\u2202', '\u2211',
    '\u220F', '\u03C0', '\u222B', '\u00AA', '\u00BA', '\u03A9', '\u00E6', '\u00F8',
    '\u00BF', '\u00A1', '\u00AC', '\u221A', '\u0192', '\u2248', '\u2206', '\u00AB',
    '\u00BB', '\u2026', '\u00A0', '\u00C0', '\u00C3', '\u00D5', '\u0152', '\u0153',
    '\u2013', '\u2014', '\u201C', '\u201D', '\u2018', '\u2019', '\u00F7', '\u25CA',
    '\u00FF', '\u0178', '\u2044', '\u20AC', '\u2039', '\u203A', '\uFB01', '\uFB02',
    '\u2021', '\u00B7', '\u201A', '\u201E', '\u2030', '\u00C2', '\u00CA', '\u00C1',
    '\u00CB', '\u00C8', '\u00CD', '\u00CE', '\u00CF', '\u00CC', '\u00D3', '\u00D4',
    '\uF8FF', '\u00D2', '\u00DA', '\u00DB', '\u00D9', '\u0131', '\u02C6', '\u02DC',
    '\u00AF', '\u02D8', '\u02D9', '\u02DA', '\u00B8', '\u02DD', '\u02DB', '\u02C7'
]

DECODE_MAP = {}
for _i, _ch in enumerate(MAC_OS_ROMAN):
    DECODE_MAP[_ch] = chr(_i + 128)
DECODE_MAP['\u03BC'] = chr(181)

def decode_to_original_akruti(text: str) -> str:
    win_ansi_score = len(re.findall(r'[ûôöÿ]', text))
    mac_roman_score = len(re.findall(r'[\u02DB\u0131\u02C6\u02C7\uFB01\uFB02]', text))
    if win_ansi_score >= mac_roman_score and win_ansi_score > 0:
        return text
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

def _build_byte_decode_table():
    table = {}
    for b in range(256):
        try:
            table[b] = bytes([b]).decode("cp1252")
        except UnicodeDecodeError:
            table[b] = chr(b)
    return table

BYTE_DECODE_TABLE = _build_byte_decode_table()

# ---------------------------------------------------------------------------
# ConvertToUnicodeOdia — 100% exact translation of the JavaScript Logic
# ---------------------------------------------------------------------------
def convert_legacy_to_unicode(s: str, skip_english=True) -> str:
    if not s:
        return s

    protected_tokens = {}
    token_counter = 0

    def repl_explicit(m):
        nonlocal token_counter
        key = chr(0xE100 + token_counter)
        token_counter += 1
        protected_tokens[key] = m.group(1)
        return key

    # 1. Protect English text automatically identified and tagged during PDF Extraction
    s = re.sub(r'\uE001([\s\S]*?)\uE002', repl_explicit, s)

    # 2. Protect user-bracketed English text
    if skip_english:
        def repl_bracket(m):
            nonlocal token_counter
            content = m.group(2)
            if re.search(r'[A-Za-z]', content):
                key = chr(0xE100 + token_counter)
                token_counter += 1
                protected_tokens[key] = m.group(0)
                return key
            return m.group(0)
        s = re.sub(r'([\(\[\{<])([A-Za-z0-9\s\-_.,:;"\']+)([\)\]\}>])', repl_bracket, s)

    # 3. Base dictionary array substitution
    for k, v in TEXT_ARRAY:
        if k == "":
            continue
        s = s.replace(k, v)

    # 4. Regex Group Reordering
    CONS = "କଖଗଘଙଚଛଜଝଞଟଠଡଡ଼ଢଢ଼ଣତଥଦଧନପଫବଭମଯୟରଲଳଵୱଶଷସହକ୍ଷଜ୍ଞ"
    MATRAS = "ାିୀୁୂୃେୈୋୌଂଁ଼"
    CLUSTER = rf"(?:[{CONS}]୍)*[{CONS}]଼?"

    s = re.sub(rf"([ù])({CLUSTER})", r"\2\1", s)
    s = s.replace("ùø", "ୌ")
    s = s.replace("ùା", "ୋ")
    s = s.replace("ù÷", "ୈ")
    s = s.replace("ù", "େ")
    s = re.sub(rf"({CLUSTER})([{MATRAS}]*)ð", r"ð\1\2", s)
    s = s.replace("ð", "ର୍")
    s = re.sub(r"([ଂଁ])([ାିୀୁୂୃେୈୋୌ])", r"\2\1", s)
    s = re.sub(rf"([{MATRAS}])([୍][{CONS}])", r"\2\1", s)
    s = re.sub(rf"([{MATRAS}])([୍][{CONS}])", r"\2\1", s)

    # 5. Restore Protected English Tokens
    for key, val in protected_tokens.items():
        s = s.replace(key, val)

    return s

# ---------------------------------------------------------------------------
# PDF glyph extractor mapped to specific JS PDF.js font matching rules
# ---------------------------------------------------------------------------
class _RawGlyph:
    __slots__ = ("x", "y", "font", "code", "width")
    def __init__(self, x, y, font, code, width):
        self.x, self.y, self.font, self.code, self.width = x, y, font, code, width

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
                            try:
                                w = font.char_width(code)
                            except Exception:
                                w = 0.5
                            char_width = (w * textstate.fontsize + textstate.charspace) * textstate.scaling / 100.0
                            glyphs.append(_RawGlyph(x, y, font.fontname, code, char_width))
                            x += char_width
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

def glyphs_to_text(glyphs, skip_english=True):
    if not glyphs:
        return ""

    # Sort matching JS logic (Group by Y with 6 point tolerance, then sort by X)
    glyphs_sorted = sorted(glyphs, key=lambda g: (-g.y, g.x))
    lines = []
    current_line = []
    current_y = None
    
    for g in glyphs_sorted:
        if current_y is None or abs(g.y - current_y) <= 6.0:
            current_line.append(g)
            current_y = g.y if current_y is None else current_y
        else:
            lines.append(current_line)
            current_line = [g]
            current_y = g.y
    if current_line:
        lines.append(current_line)

    page_text = ""
    for line in lines:
        line_sorted = sorted(line, key=lambda g: g.x)
        last_x = None
        last_width = None
        
        for g in line_sorted:
            font_lower = g.font.lower() if g.font else ""
            
            # Smart English Detection (Mimics JS regex)
            is_explicit_english = bool(re.search(r'arial|times|helvetica|calibri|cambria|roboto|tahoma|verdana|segoe|georgia', font_lower))
            is_akruti = bool(re.search(r'akruti|sarala|odia|orissa|kalinga', font_lower))
            
            if 0 <= g.code <= 255:
                char = BYTE_DECODE_TABLE.get(g.code, chr(g.code))
            else:
                char = chr(g.code)

            if skip_english and is_explicit_english and not is_akruti and char.strip() != "":
                if re.search(r'[A-Za-z]', char):
                    char = f"\uE001{char}\uE002"
            
            if last_x is not None:
                gap = g.x - (last_x + last_width)
                if gap > 5:
                    page_text += " "
                    
            page_text += char
            last_x = g.x
            last_width = g.width
            
        page_text += "\n"
        
    page_text = decode_to_original_akruti(page_text)
    return convert_legacy_to_unicode(page_text, skip_english=skip_english)

def convert_pdf(pdf_path, page_range=None, progress=True):
    total_pages = get_page_count(pdf_path)
    if page_range is None:
        page_range = range(total_pages)
    out = []
    for pno in page_range:
        glyphs = extract_page_glyphs(pdf_path, pno)
        page_text = glyphs_to_text(glyphs, skip_english=True)
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
