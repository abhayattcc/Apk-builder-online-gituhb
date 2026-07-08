import re
import os
import glob
import fitz  # PyMuPDF, install via: pip install PyMuPDF

# ====================================================
# EXACT Array from convert-1-2.html
# ====================================================
RAW_TEXT_ARRAY = [
    " û", " ।", "ö" , " ।", "÷÷÷", "",
    "£" , "୍ମ", "à" , "୍ମ", "á" , "୍ମୃ",
    "â" , "୍ର", "ã" , "୍ର", "ä" , "୍ଲ",
    "å" , "୍ଭ", "æ" , "୍ଳ", "ç" , "୍ୱ",
    "è" , "୍ସ", "ý", "୍ୟ", "¥", "୍ୟ",
    "ó", "ିଁ", "Iß" , "ୱ", "Wÿ" , "ଡ଼",
    "Xÿ" , "ଢ଼", "Pÿ" , "ଚ", "[ô" , "ଥି",
    "]ô" , "ଧି", "Lô" , "ଖି", "cô", "ତ୍ମ",
    "_ô", "ତ୍ପ", "û" , "ା", "ò" , "ି",
    "ú" , "ୀ", "ê" , "ୁ", "ë" , "ୁ",
    "ì" , "ୂ", "í" ,  "ୂ", "é" , "ୃ",
    "ñ", "ଁ", "õ", "ଂ", "ü", "ଃ",
    "þ", "୍", "¨", "୍‌", "1" , "୧",
    "2" , "୨", "3" , "୩", "4" , "୪",
    "5" , "୫", "6" , "୬", "7" , "୭",
    "8" , "୮", "9" , "୯", "0" , "୦",
    "#" , "୰", "$" , "ଽ", "&" , "ଌ",
    "*", "ଞ୍ଚ", " ", "ଞ୍ଚ", "î", "୍ରୁ", 
    "ï", "୍ରୂ", "Ð", "କ୍ଷ୍ଣ", "Ñ", "୍କ", 
    "Ò", "୍ଖ", "Ó", "୍ଗ", "Ô", "୍ଚ", 
    "Õ", "୍ଜ", "Ö", "୍ଟ", "×", "୍ଠ", 
    "Ø", "୍ଡ", "Ù", "୍ଣ", "Ú", "୍ଥ", 
    "Û", "୍ଧ", "Ü", "୍ନ", "Ý", "୍ପ", 
    "Þ", "୍ଫ", "ß", "୍ୱ", "<", "ଣ୍ଟ", 
    " ", "ଣ୍ଟ", "…", "ଟ୍ଟ", "μ", "ମ୍ପ", 
    "µ", "ମ୍ପ", "¶", "ମ୍ଫ", "‰", "ଣ୍ଣ", 
    "Š", "ଣ୍ଡ", "Œ", "ଣ୍ଠ", "™", "ତ୍ମ", 
    "š", "ତ୍ପ", "›", "ତ୍ସ", "œ", "ତ୍ସ୍ନ", 
    "Ÿ", "ଦ୍ଦ", "{", "ଜ୍ଜ", "|", "ଜ୍ଝ", 
    "}", "କ୍ର", "¡", "ଦ୍ଧ", "¢", "ଦ୍ଘ", 
    "¤", "ଧ୍ୟ", "¦", "ନ୍ଦ", "§", "ନ୍ଧ", 
    "©", "ତ୍ତ", " ", "ତ୍ତ", "ª", "ନ୍ତ୍ର", 
    "«", "ନ୍ତ", "¬", "ଞ୍ଜ", "ƒ", "ଞ୍ଝ", 
    "®", "ପ୍ପ", "¯", "ପ୍ତ", "°", "ପ୍ସ", 
    "±", "ବ୍ଦ", "²", "ବ୍ଧ", "´", "ମ୍ବ", 
    "¸", "ମ୍ଭ", " ̧", "ମ୍ଭ", "̧", "ମ୍ଭ", 
    "¹", "ମ୍ମ", "º", "ଲ୍କ", "»", "ଲ୍ଗ", 
    "¼", "ଶ୍ଛ", "½", "ଶ୍ଚ", "¾", "ଷ୍ଣ", 
    "¿", "ଷ୍ପ", "À", "ଷ୍ଫ", "Á", "ଷ୍ଟ", 
    "Â", "ଷ୍ଠ", "Ã", "ଷ୍କ", "Ä", "ସ୍କ", 
    "Å", "ସ୍ଖ", "Æ", "ସ୍ପ", "Ç", "ସ୍ଫ", 
    "È", "ସ୍ତ୍ର", "É", "ସ୍ତ", "Ê", "ସ୍ୱ", 
    "Ë", "ଳ୍କ", "Ì", "ଳ୍ପ", "Í", "ଳ୍ଫ", 
    "Î", "ତ୍ଥ", " ", "ତ୍ଥ", "Ï", "ଳ୍ଳ", 
    "@ା", "ଆ", "@", "ଅ", "A", "ଇ", 
    "B", "ଈ", "C", "ଉ", "D", "ଊ", 
    "E", "ଋ", "F", "ୠ", "G", "ଏ", 
    "H", "ଐ", "I", "ଓ", "J", "ଔ", 
    "K", "କ", "L", "ଖ", "M", "ଗ", 
    "N", "ଘ", "O", "ଙ", "P", "ଚ", 
    "Q", "ଛ", "R", "ଜ", "S", "ଝ", 
    "T", "ଞ", "U", "ଟ", "V", "ଠ", 
    "W", "ଡ", "X", "ଢ", "Y", "ଣ", 
    "Z", "ତ", "[", "ଥ", "\\", "ଦ", 
    "]", "ଧ", "^", "ନ", "~", "ଯ", 
    "_", "ପ", "`", "ଫ", "a", "ବ", 
    "b", "ଭ", "c", "ମ", "d", "ୟ", 
    "e", "ର", "f", "ଲ", "g", "ଶ", 
    "h", "ଷ", "i", "ସ", "j", "ହ", 
    "k", "ଳ", "l", "କ୍ଷ", "m", "ଜ୍ଞ", 
    "n", "ଦ୍ଭ", "o", "କ୍ଟ", "p", "କ୍ଟ୍ର", 
    "q", "କ୍ତ", "r", "କ୍ସ", "s", "ଗ୍ଦ", 
    "t", "ଗ୍ଧ", "u", "ଙ୍କ", "v", "ଙ୍ଖ", 
    "w", "ଙ୍ଗ", "x", "ଙ୍ଘ", "y", "ଚ୍ଚ", 
    "z", "ଚ୍ଛ", " ̄", "ପ୍ତ", " ́", "ମ୍ବ", 
    "‹", "ଣ୍ଢ", "ଏø", " ଐ", "୍ଯ", "୍ୟ", 
    " ̈", "୍‍", "ଅା", "ଆ"
]

# THE FIX: Windows-1252 / ISO-8859-1 Raw Byte Interceptor
# When a PDF lacks font data, it extracts characters like "Š" as raw hex bytes (0x80 to 0x9F).
# This injects the exact byte representations into our translation array.
EXTRA_BYTE_MAPPINGS = [
    ("\x89", "ଣ୍ଣ"), ("\x8a", "ଣ୍ଡ"), ("\x8b", "ଣ୍ଢ"), ("\x8c", "ଣ୍ଠ"),
    ("\x83", "ଞ୍ଝ"), ("\x85", "ଟ୍ଟ"), ("\x99", "ତ୍ମ"), ("\x9a", "ତ୍ପ"),
    ("\x9b", "ତ୍ସ"), ("\x9c", "ତ୍ସ୍ନ"), ("\x9f", "ଦ୍ଦ"),
    ("\x8d", "ଞ୍ଚ"), ("\x8f", "ଣ୍ଟ"), ("\x90", "ତ୍ତ"), ("\x9d", "ତ୍ଥ")
]

# Clean up literal spaces and attach the byte fix
TEXT_ARRAY = []
for i in range(0, len(RAW_TEXT_ARRAY) - 1, 2):
    key = RAW_TEXT_ARRAY[i]
    val = RAW_TEXT_ARRAY[i+1]
    if key == " ": 
        continue # Ignore literal space mappings that destroy document spaces
    TEXT_ARRAY.extend([key, val])

for byte_val, unicode_odia in EXTRA_BYTE_MAPPINGS:
    TEXT_ARRAY.extend([byte_val, unicode_odia])

# ====================================================
# Build Reverse Pairs (Unicode -> Akruti)
# ====================================================
def build_reverse_pairs():
    seen = {}
    pairs = []
    for i in range(0, len(TEXT_ARRAY) - 1, 2):
        akruti = TEXT_ARRAY[i]
        unicode_val = TEXT_ARRAY[i + 1]
        if not unicode_val or unicode_val in seen:
            continue
        seen[unicode_val] = True
        pairs.extend([unicode_val, akruti])
        
    entries = [(pairs[j], pairs[j + 1]) for j in range(0, len(pairs) - 1, 2)]
    entries.sort(key=lambda x: len(x[0]), reverse=True)
    
    ordered = []
    for e in entries:
        ordered.extend([e[0], e[1]])
    return ordered

REVERSE_PAIRS = build_reverse_pairs()

# ====================================================
# Akruti -> Unicode Odia Logic
# ====================================================
def convert_to_unicode_odia(input_str):
    if not input_str:
        return input_str
        
    modified_substring = input_str

    if modified_substring != "":
        # 1. Base Array Replacements
        for i in range(0, len(TEXT_ARRAY) - 1, 2):
            target = TEXT_ARRAY[i]
            replacement = TEXT_ARRAY[i + 1]
            while target in modified_substring:
                modified_substring = modified_substring.replace(target, replacement)
                
        # 2. Re-order Maatraas
        modified_substring = re.sub(r'([ù])([କଖଗଘଙଚଛଜଝଞଟଠଡଡ଼ଢଢ଼ଣତଥଦଧନପଫବଭମଯୟରଲବୱଶଷସହକ୍ଷଡ଼ଳ])', r'\2\1', modified_substring)
        modified_substring = re.sub(r'([ù])([୍])([କଖଗଘଚଛଜଝଟଠଡଡ଼ଢଢ଼ଣତଥନପଫବଭମୟରଲବୱଶଷସହକ୍ଷଡ଼ଳ])', r'\2\3\1', modified_substring)
        modified_substring = re.sub(r'([ù])([୍])([କଖଗଘଚଛଜଝଟଠଡଡ଼ଢଢ଼ଣତଥନପଫବଭମୟରଲବୱଶଷସହକ୍ଷଡ଼ଳ])', r'\2\3\1', modified_substring)
        modified_substring = modified_substring.replace("ùø", "ୌ")
        modified_substring = modified_substring.replace("ùା", "ୋ")
        modified_substring = modified_substring.replace("ù÷", "ୈ")
        modified_substring = modified_substring.replace("ù", "େ")

        # 3. Adjust Reph (half r)
        reph_chars = r'[କଖଗଘଚଛଜଝଟଠଡଡ଼ଢଢ଼ଣତଥଦଧନପଫବଭମଯରଲଳଵଶଷସହକ୍ଷଜ୍ଞୟ]'
        matras = r'[ାିୀୁୂୃେୈୋୌଂଁ]'
        modified_substring = re.sub(rf'({reph_chars})({matras}*)à', r'ð\1\2', modified_substring)
        modified_substring = re.sub(rf'({reph_chars})({matras}*)ð', r'ð\1\2', modified_substring)
        modified_substring = re.sub(rf'({reph_chars})([୍])à', r'ð\1\2', modified_substring)
        modified_substring = re.sub(rf'({reph_chars})([୍])ð', r'ð\1\2', modified_substring)
        modified_substring = modified_substring.replace("ð", "ର୍")
        modified_substring = re.sub(r'([ଂଁ])([ାିୀୁୂୃେୈୋୌ])', r'\2\1', modified_substring)

        # 4. Fix Matra before Halanta
        phala_cluster = r'[୍][କଖଗଘଙଚଛଜଝଞଟଠଡଡ଼ଢଢ଼ଣତଥଦଧନପଫବଭମଯୟରଲଳଵଶଷସହ]'
        modified_substring = re.sub(rf'([ାିୀୁୂୃେୈୋୌଂଁ])({phala_cluster})', r'\2\1', modified_substring)

    return modified_substring

# ====================================================
# Unicode Odia -> Akruti Logic
# ====================================================
def convert_to_akruti(input_str):
    if not input_str:
        return input_str
    modified_substring = input_str
    if modified_substring != "":
        for i in range(0, len(REVERSE_PAIRS) - 1, 2):
            target = REVERSE_PAIRS[i]
            replacement = REVERSE_PAIRS[i + 1]
            while target in modified_substring:
                modified_substring = modified_substring.replace(target, replacement)
    return modified_substring

# ====================================================
# Font-Aware PDF Extractor With Line Rounding
# ====================================================
def process_pdf(pdf_path, output_txt_path, direction="toUnicode"):
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Failed to open PDF {pdf_path}: {e}")
        return

    converted_pages = []
    
    # Common English fonts to ignore during conversion
    ENGLISH_FONTS = [
        'arial', 'times', 'helvetica', 'calibri', 'courier', 
        'cambria', 'georgia', 'tahoma', 'verdana', 'segoe', 'roboto', 'symbol'
    ]
    # Known Legacy Odia Fonts
    LEGACY_FONTS = ['akruti', 'sarala', 'ori', 'padmini', 'kalinga', 'janaki', 'konark']
    
    for i in range(len(doc)):
        page = doc.load_page(i)
        page_dict = page.get_text("dict")
        if "blocks" not in page_dict:
            continue
            
        blocks = page_dict["blocks"]
        
        # Round the Y-coordinates slightly so text on the exact same visual line doesn't get split up
        blocks.sort(key=lambda b: (round(b.get("bbox", [0,0,0,0])[1] / 5), b.get("bbox", [0,0,0,0])[0]))
        
        page_text = ""
        for b in blocks:
            if b.get("type") == 0:  # Type 0 = Text Block
                for line in b["lines"]:
                    
                    # BUFFER: We glue separated spans together before converting
                    legacy_buffer = ""
                    
                    for span in line["spans"]:
                        raw_text = span["text"]
                        font_name = span["font"].lower()
                        
                        is_english = any(eng_font in font_name for eng_font in ENGLISH_FONTS)
                        is_legacy = any(leg_font in font_name for leg_font in LEGACY_FONTS)
                        
                        if is_english and not is_legacy:
                            if legacy_buffer:
                                if direction == "toAkruti":
                                    page_text += convert_to_akruti(legacy_buffer)
                                else:
                                    page_text += convert_to_unicode_odia(legacy_buffer)
                                legacy_buffer = ""
                            
                            page_text += raw_text
                        else:
                            legacy_buffer += raw_text
                            
                    if legacy_buffer:
                        if direction == "toAkruti":
                            page_text += convert_to_akruti(legacy_buffer)
                        else:
                            page_text += convert_to_unicode_odia(legacy_buffer)
                            
                    page_text += "\n"
                page_text += "\n"
        
        converted_pages.append(page_text.strip())
        print(f"Processed page {i+1} / {len(doc)}")

    # Save cleanly to text file
    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write("\n\n--- Page Break ---\n\n".join(converted_pages))
    
    print(f"✅ Successfully converted: {output_txt_path}")

# ====================================================
# Auto-Run Trigger
# ====================================================
if __name__ == "__main__":
    for pdf_file in glob.glob('*.pdf'):
        txt_name = pdf_file.replace('.pdf', '.txt')
        print(f"Starting conversion for: {pdf_file}")
        process_pdf(pdf_file, txt_name, direction="toUnicode")
