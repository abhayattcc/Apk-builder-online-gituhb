import re
import os
import glob
import fitz  # PyMuPDF, install via: pip install PyMuPDF

# ====================================================
# Corrected Akruti Array Mapping
# ====================================================
TEXT_ARRAY = [
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
    
    # --- THE SPACE LOGIC FIXES ---
    "*" , "ଞ୍ଚ", 
    "\x8d", "ଞ୍ଚ", # Fixed: Replaced literal space with correct Hex 0x8D
    
    "î" , "୍ରୁ", "ï" , "୍ରୂ", "Ð" , "କ୍ଷ୍ଣ", 
    "Ñ" , "୍କ", "Ò" , "୍ଖ", "Ó" , "୍ଗ", 
    "Ô" , "୍ଚ", "Õ" , "୍ଜ", "Ö" , "୍ଟ", 
    "×" , "୍ଠ", "Ø" , "୍ଡ", "Ù" , "୍ଣ", 
    "Ú" , "୍ଥ", "Û" , "୍ଧ", "Ü" , "୍ନ", 
    "Ý" , "୍ପ", "Þ" , "୍ଫ", "ß" , "୍ୱ", 
    
    "<" , "ଣ୍ଟ", 
    "\x8f", "ଣ୍ଟ", # Fixed: Replaced literal space with correct Hex 0x8F
    
    "…" , "ଟ୍ଟ", "μ" , "ମ୍ପ", "µ" , "ମ୍ପ", 
    "¶" , "ମ୍ଫ", "‰" , "ଣ୍ଣ", "Š" , "ଣ୍ଡ", 
    "Œ" , "ଣ୍ଠ", "™" , "ତ୍ମ", "š" , "ତ୍ପ", 
    "›" , "ତ୍ସ", "œ" , "ତ୍ସ୍ନ", "Ÿ" , "ଦ୍ଦ", 
    "{" , "ଜ୍ଜ", "|" , "ଜ୍ଝ", "}" , "କ୍ର", 
    "¡" , "ଦ୍ଧ", "¢" , "ଦ୍ଘ", "¤" , "ଧ୍ୟ", 
    "¦" , "ନ୍ଦ", "§" , "ନ୍ଧ", 
    
    "©" , "ତ୍ତ", 
    "\x90", "ତ୍ତ", # Fixed: Replaced literal space with correct Hex 0x90
    
    "ª" , "ନ୍ତ୍ର", "«" , "ନ୍ତ", "¬" , "ଞ୍ଜ", 
    "ƒ" , "ଞ୍ଝ", "®" , "ପ୍ପ", "¯" , "ପ୍ତ", 
    "°", "ପ୍ସ", "±" , "ବ୍ଦ", "²" , "ବ୍ଧ", 
    "´" , "ମ୍ବ", "¸" , "ମ୍ଭ", "¹" , "ମ୍ମ", 
    "º" , "ଲ୍କ", "»" , "ଲ୍ଗ", "¼" , "ଶ୍ଛ", 
    "½" , "ଶ୍ଚ", "¾" , "ଷ୍ଣ", "¿" , "ଷ୍ପ", 
    "À" , "ଷ୍ଫ", "Á" , "ଷ୍ଟ", "Â" , "ଷ୍ଠ", 
    "Ã" , "ଷ୍କ", "Ä" , "ସ୍କ", "Å" , "ସ୍ଖ", 
    "Æ" , "ସ୍ପ", "Ç" , "ସ୍ଫ", "È" , "ସ୍ତ୍ର", 
    "É" , "ସ୍ତ", "Ê" , "ସ୍ୱ", "Ë" , "ଳ୍କ", 
    "Ì" , "ଳ୍ପ", "Í" , "ଳ୍ଫ", 
    
    "Î" , "ତ୍ଥ", 
    "\x9d", "ତ୍ଥ", # Fixed: Replaced literal space with correct Hex 0x9D
    
    "Ï" , "ଳ୍ଳ", "@ା" , "ଆ", "@" , "ଅ", 
    "A" , "ଇ", "B" , "ଈ", "C" , "ଉ", 
    "D" , "ଊ", "E" , "ଋ", "F" , "ୠ", 
    "G" , "ଏ", "H" , "ଐ", "I" , "ଓ", 
    "J" , "ଔ", "K" , "କ", "L" , "ଖ", 
    "M" , "ଗ", "N" , "ଘ", "O" , "ଙ", 
    "P" , "ଚ", "Q" , "ଛ", "R" , "ଜ", 
    "S" , "ଝ", "T" , "ଞ", "U", "ଟ", 
    "V", "ଠ", "W", "ଡ", "X", "ଢ", 
    "Y", "ଣ", "Z" , "ତ", "[" , "ଥ", 
    "\\" , "ଦ", "]" , "ଧ", "^", "ନ", 
    "~" , "ଯ", "_" , "ପ", "`" , "ଫ", 
    "a" , "ବ", "b" , "ଭ", "c" , "ମ", 
    "d" , "ୟ", "e" , "ର", "f" , "ଲ", 
    "g" , "ଶ", "h" , "ଷ", "i" , "ସ", 
    "j" , "ହ", "k" , "ଳ", "l" , "କ୍ଷ", 
    "m" , "ଜ୍ଞ", "n" , "ଦ୍ଭ", "o" , "କ୍ଟ", 
    "p" , "କ୍ଟ୍ର", "q" , "କ୍ତ", "r" , "କ୍ସ", 
    "s" , "ଗ୍ଦ", "t" , "ଗ୍ଧ", "u" , "ଙ୍କ", 
    "v" , "ଙ୍ଖ", "w" , "ଙ୍ଗ", "x" , "ଙ୍ଘ", 
    "y" , "ଚ୍ଚ", "z" , "ଚ୍ଛ", 
    
    # --- PDF COMBINING MARK FIXES ---
    # In PDFs, characters are sometimes extracted as Space + a Unicode combining mark.
    " \u0304", "ପ୍ତ", # " ̄" (Space + Macron)
    " \u0301", "ମ୍ବ", # " ́" (Space + Acute)
    " \u0327", "ମ୍ଭ", # " ̧" (Space + Cedilla)
    " \u0308", "୍‍",  # " ̈" (Space + Diaeresis)
    "̧" , "ମ୍ଭ", 
    "‹", "ଣ୍ଢ", "ଏø", " ଐ", "୍ଯ" , "୍ୟ", 
    "ଅା", "ଆ" 
]

# ====================================================
# Text Conversion Engine
# ====================================================
def convert_to_unicode_odia(input_str):
    if not input_str:
        return input_str
        
    modified_substring = input_str

    if modified_substring != "":
        # 1. Base Array Replacements (mimicking the exact JS While-Loop behavior)
        for i in range(0, len(TEXT_ARRAY) - 1, 2):
            target = TEXT_ARRAY[i]
            replacement = TEXT_ARRAY[i + 1]
            while target in modified_substring:
                modified_substring = modified_substring.replace(target, replacement)
                
        # 2. Re-order Maatraas (e, ai, o, au)
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
# PDF Extractor
# ====================================================
def process_pdf(pdf_path, output_txt_path):
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Failed to open PDF {pdf_path}: {e}")
        return

    converted_pages = []
    
    for i in range(len(doc)):
        page = doc.load_page(i)
        
        # We extract block-by-block to preserve the visual reading order
        blocks = page.get_text("blocks")
        blocks.sort(key=lambda b: (b[1], b[0]))
        
        page_text = ""
        for b in blocks:
            text = b[4]
            page_text += text + "\n"
        
        converted = convert_to_unicode_odia(page_text)
        converted_pages.append(converted.strip())

    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write("\n\n--- Page Break ---\n\n".join(converted_pages))
    
    print(f"✅ Successfully converted: {output_txt_path}")

# Auto-run for all PDFs in the folder
if __name__ == "__main__":
    for pdf_file in glob.glob('*.pdf'):
        txt_name = pdf_file.replace('.pdf', '.txt')
        process_pdf(pdf_file, txt_name)
