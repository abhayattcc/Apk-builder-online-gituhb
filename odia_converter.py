import re
import fitz  # PyMuPDF, installed via: pip install PyMuPDF

# The character mapping from the original Akruti/Sarala HTML script
# Note: I removed the mappings where an exact space " " triggered a letter (like "ଞ୍ଚ") 
# as that was likely an invisible character encoding artifact in the HTML and would corrupt real spaces.
AKRUTI_MAPPING = [
    (" û", " ।"), ("ö", " ।"), ("÷÷÷", ""),
    ("£", "୍ମ"), ("à", "୍ମ"), ("á", "୍ମୃ"),
    ("â", "୍ର"), ("ã", "୍ର"), ("ä", "୍ଲ"),
    ("å", "୍ଭ"), ("æ", "୍ଳ"), ("ç", "୍ୱ"),
    ("è", "୍ସ"), ("ý", "୍ୟ"), ("¥", "୍ୟ"),
    ("ó", "ିଁ"), ("Iß", "ୱ"), ("Wÿ", "ଡ଼"),
    ("Xÿ", "ଢ଼"), ("Pÿ", "ଚ"), ("[ô", "ଥି"),
    ("]ô", "ଧି"), ("Lô", "ଖି"), ("cô", "ତ୍ମ"),
    ("_ô", "ତ୍ପ"), ("û", "ା"), ("ò", "ି"),
    ("ú", "ୀ"), ("ê", "ୁ"), ("ë", "ୁ"),
    ("ì", "ୂ"), ("í", "ୂ"), ("é", "ୃ"),
    ("ñ", "ଁ"), ("õ", "ଂ"), ("ü", "ଃ"),
    ("þ", "୍"), ("¨", "୍‌"), ("1", "୧"),
    ("2", "୨"), ("3", "୩"), ("4", "୪"),
    ("5", "୫"), ("6", "୬"), ("7", "୭"),
    ("8", "୮"), ("9", "୯"), ("0", "୦"),
    ("#", "୰"), ("$", "ଽ"), ("&", "ଌ"),
    ("*", "ଞ୍ଚ"), ("î", "୍ରୁ"), ("ï", "୍ରୂ"),
    ("Ð", "କ୍ଷ୍ଣ"), ("Ñ", "୍କ"), ("Ò", "୍ଖ"),
    ("Ó", "୍ଗ"), ("Ô", "୍ଚ"), ("Õ", "୍ଜ"),
    ("Ö", "୍ଟ"), ("×", "୍ଠ"), ("Ø", "୍ଡ"),
    ("Ù", "୍ଣ"), ("Ú", "୍ଥ"), ("Û", "୍ଧ"),
    ("Ü", "୍ନ"), ("Ý", "୍ପ"), ("Þ", "୍ଫ"),
    ("ß", "୍ୱ"), ("<", "ଣ୍ଟ"), ("…", "ଟ୍ଟ"),
    ("μ", "ମ୍ପ"), ("µ", "ମ୍ପ"), ("¶", "ମ୍ଫ"),
    ("‰", "ଣ୍ଣ"), ("Š", "ଣ୍ଡ"), ("Œ", "ଣ୍ଠ"),
    ("™", "ତ୍ମ"), ("š", "ତ୍ପ"), ("›", "ତ୍ସ"),
    ("œ", "ତ୍ସ୍ନ"), ("Ÿ", "ଦ୍ଦ"), ("{", "ଜ୍ଜ"),
    ("|", "ଜ୍ଝ"), ("}", "କ୍ର"), ("¡", "ଦ୍ଧ"),
    ("¢", "ଦ୍ଘ"), ("¤", "ଧ୍ୟ"), ("¦", "ନ୍ଦ"),
    ("§", "ନ୍ଧ"), ("©", "ତ୍ତ"), ("ª", "ନ୍ତ୍ର"),
    ("«", "ନ୍ତ"), ("¬", "ଞ୍ଜ"), ("ƒ", "ଞ୍ଝ"),
    ("®", "ପ୍ପ"), ("¯", "ପ୍ତ"), ("°", "ପ୍ସ"),
    ("±", "ବ୍ଦ"), ("²", "ବ୍ଧ"), ("´", "ମ୍ବ"),
    ("¸", "ମ୍ଭ"), (" ̧", "ମ୍ଭ"), ("̧", "ମ୍ଭ"),
    ("¹", "ମ୍ମ"), ("º", "ଲ୍କ"), ("»", "ଲ୍ଗ"),
    ("¼", "ଶ୍ଛ"), ("½", "ଶ୍ଚ"), ("¾", "ଷ୍ଣ"),
    ("¿", "ଷ୍ପ"), ("À", "ଷ୍ଫ"), ("Á", "ଷ୍ଟ"),
    ("Â", "ଷ୍ଠ"), ("Ã", "ଷ୍କ"), ("Ä", "ସ୍କ"),
    ("Å", "ସ୍ଖ"), ("Æ", "ସ୍ପ"), ("Ç", "ସ୍ଫ"),
    ("È", "ସ୍ତ୍ର"), ("É", "ସ୍ତ"), ("Ê", "ସ୍ୱ"),
    ("Ë", "ଳ୍କ"), ("Ì", "ଳ୍ପ"), ("Í", "ଳ୍ଫ"),
    ("Î", "ତ୍ଥ"), ("Ï", "ଳ୍ଳ"), ("@ା", "ଆ"),
    ("@", "ଅ"), ("A", "ଇ"), ("B", "ଈ"),
    ("C", "ଉ"), ("D", "ଊ"), ("E", "ଋ"),
    ("F", "ୠ"), ("G", "ଏ"), ("H", "ଐ"),
    ("I", "ଓ"), ("J", "ଔ"), ("K", "କ"),
    ("L", "ଖ"), ("M", "ଗ"), ("N", "ଘ"),
    ("O", "ଙ"), ("P", "ଚ"), ("Q", "ଛ"),
    ("R", "ଜ"), ("S", "ଝ"), ("T", "ଞ"),
    ("U", "ଟ"), ("V", "ଠ"), ("W", "ଡ"),
    ("X", "ଢ"), ("Y", "ଣ"), ("Z", "ତ"),
    ("[", "ଥ"), ("\\", "ଦ"), ("]", "ଧ"),
    ("^", "ନ"), ("~", "ଯ"), ("_", "ପ"),
    ("`", "ଫ"), ("a", "ବ"), ("b", "ଭ"),
    ("c", "ମ"), ("d", "ୟ"), ("e", "ର"),
    ("f", "ଲ"), ("g", "ଶ"), ("h", "ଷ"),
    ("i", "ସ"), ("j", "ହ"), ("k", "ଳ"),
    ("l", "କ୍ଷ"), ("m", "ଜ୍ଞ"), ("n", "ଦ୍ଭ"),
    ("o", "କ୍ଟ"), ("p", "କ୍ଟ୍ର"), ("q", "କ୍ତ"),
    ("r", "କ୍ସ"), ("s", "ଗ୍ଦ"), ("t", "ଗ୍ଧ"),
    ("u", "ଙ୍କ"), ("v", "ଙ୍ଖ"), ("w", "ଙ୍ଗ"),
    ("x", "ଙ୍ଘ"), ("y", "ଚ୍ଚ"), ("z", "ଚ୍ଛ"),
    (" ̄", "ପ୍ତ"), (" ́", "ମ୍ବ"), ("‹", "ଣ୍ଢ"),
    ("ଏø", " ଐ"), ("୍ଯ", "୍ୟ"), (" ̈", "୍‍"),
    ("ଅା", "ଆ")
]

def convert_akruti_to_unicode(text):
    if not text:
        return ""
    
    modified_string = text

    # 1. Base symbol replacements
    for akruti, unicode_val in AKRUTI_MAPPING:
        modified_string = modified_string.replace(akruti, unicode_val)

    # 2. Adjust position of e, ai, o and au maatraas
    c1 = r'[କଖଗଘଙଚଛଜଝଞଟଠଡଡ଼ଢଢ଼ଣତଥଦଧନପଫବଭମଯୟରଲବୱଶଷସହକ୍ଷଡ଼ଳ]'
    c2 = r'[କଖଗଘଚଛଜଝଟଠଡଡ଼ଢଢ଼ଣତଥନପଫବଭମୟରଲବୱଶଷସହକ୍ଷଡ଼ଳ]'
    
    modified_string = re.sub(rf'([ù])({c1})', r'\2\1', modified_string)
    # Applied twice in JS to handle clusters properly
    modified_string = re.sub(rf'([ù])([୍])({c2})', r'\2\3\1', modified_string)
    modified_string = re.sub(rf'([ù])([୍])({c2})', r'\2\3\1', modified_string)
    
    modified_string = modified_string.replace("ùø", "ୌ")
    modified_string = modified_string.replace("ùା", "ୋ")
    modified_string = modified_string.replace("ù÷", "ୈ")
    modified_string = modified_string.replace("ù", "େ")

    # 3. Adjust position of reph (half r)
    reph_chars = r'[କଖଗଘଚଛଜଝଟଠଡଡ଼ଢଢ଼ଣତଥଦଧନପଫବଭମଯରଲଳଵଶଷସହକ୍ଷଜ୍ଞୟ]'
    matras = r'[ାିୀୁୂୃେୈୋୌଂଁ]'
    
    modified_string = re.sub(rf'({reph_chars})({matras}*)à', r'ð\1\2', modified_string)
    modified_string = re.sub(rf'({reph_chars})({matras}*)ð', r'ð\1\2', modified_string)
    modified_string = re.sub(rf'({reph_chars})([୍])à', r'ð\1\2', modified_string)
    modified_string = re.sub(rf'({reph_chars})([୍])ð', r'ð\1\2', modified_string)
    modified_string = modified_string.replace("ð", "ର୍")
    
    modified_string = re.sub(r'([ଂଁ])([ାିୀୁୂୃେୈୋୌ])', r'\2\1', modified_string)

    # 4. Fix vowel signs ending up before halanta+consonant phala clusters
    phala_cluster = r'[୍][କଖଗଘଙଚଛଜଝଞଟଠଡଡ଼ଢଢ଼ଣତଥଦଧନପଫବଭମଯୟରଲଳଵଶଷସହ]'
    modified_string = re.sub(rf'([ାିୀୁୂୃେୈୋୌଂଁ])({phala_cluster})', r'\2\1', modified_string)

    return modified_string

def process_pdf(pdf_path, output_txt_path):
    print(f"Opening {pdf_path}...")
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Failed to open PDF: {e}")
        return

    converted_pages = []
    
    for i in range(len(doc)):
        page = doc.load_page(i)
        
        # We extract raw text block by block to maintain reading order and "book-like" layout
        blocks = page.get_text("blocks")
        blocks.sort(key=lambda b: (b[1], b[0]))  # Sort by Y-coordinate, then X-coordinate
        
        page_text = ""
        for b in blocks:
            text = b[4]
            page_text += text + "\n"
        
        # Convert legacy text to Unicode
        unicode_text = convert_akruti_to_unicode(page_text)
        converted_pages.append(unicode_text.strip())
        print(f"Processed page {i+1} / {len(doc)}")

    # Save to standard Unicode UTF-8 text file
    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write("\n\n--- Page Break ---\n\n".join(converted_pages))
    
    print(f"\n✅ Successfully converted and saved to: {output_txt_path}")

# ==========================================
# Run the Code Here
# ==========================================
if __name__ == "__main__":
    # Change these filenames to match your files!
    input_pdf = "your_legacy_book.pdf" 
    output_text = "converted_odia_book.txt"
    
    # process_pdf(input_pdf, output_text) # UNCOMMENT this line to run on your files
    
    # Quick Sample Test
    sample_akruti = "Kûü _ûLôKê @ାସ"
    print(f"Sample Input (Legacy): {sample_akruti}")
    print(f"Sample Output (Unicode): {convert_akruti_to_unicode(sample_akruti)}")
