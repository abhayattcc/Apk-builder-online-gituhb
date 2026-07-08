import re
import os
import glob
import fitz  # PyMuPDF

# ====================================================
# 100% Exact Array from convert-1-2.html
# ====================================================
TEXT_ARRAY = [
    " û", " ।", # purnacheda
    "ö" , " ।" , # purnacheda
    "÷÷÷", "", #
    # double accented - AkrutiOriSarala
    "£" , "୍ମ" , # ma phala
    "à" , "୍ମ" , # ma phala
    "á" , "୍ମୃ" , # (halanta)m-Rû
    "â" , "୍ର" , # ra
    "ã" , "୍ର" , # reph
    "ä" , "୍ଲ" , # la phala
    "å" , "୍ଭ" , # halanta- bha
    "æ" , "୍ଳ" , # halanta-La
    "ç" , "୍ୱ" , # ba phala
    "è" , "୍ସ" , # halanta-sa
    "ý", "୍ୟ" , # ja phala
    "¥", "୍ୟ" , # ja phala
    "ó", "ିଁ" , # i kara

    "Iß" , "ୱ", #wa
    "Wÿ" , "ଡ଼" , # Da with bindu
    "Xÿ" , "ଢ଼" , # Dha with bindu
    "Pÿ" , "ଚ" , # c
    "[ô" , "ଥି" , # thi
    "]ô" , "ଧି" , # dhi
    "Lô" , "ଖି" , # khi
    "cô", "ତ୍ମ" , # tma
    "_ô", "ତ୍ପ" , # tma

    "û" , "ା" , # aa kara
    "ò" , "ି" , # i kara
    "ú" , "ୀ" , # dirgha i kara
    "ê" , "ୁ" , # u kara
    "ë" , "ୁ" , # u kara
    "ì" , "ୂ" , # dirgha i kara
    "í" ,  "ୂ" , # dirgha u kara
    "é" , "ୃ" , # ru kara

    "ñ", "ଁ" , # chandrabindu
    "õ", "ଂ" , # anuswara
    "ü", "ଃ" , # bisarga
    "þ", "୍" , #halanta
    "¨", "୍‌" , # halanta with zero width non-joiner
    "1" , "୧" , # Numeric 1
    "2" , "୨" , # Numeric 2
    "3" , "୩" , # Numeric 3
    "4" , "୪" , # Numeric 4
    "5" , "୫" , # Numeric 5
    "6" , "୬" , # Numeric 6
    "7" , "୭" , # Numeric 7
    "8" , "୮" , # Numeric 8
    "9" , "୯" , # Numeric 9
    "0" , "୦" , # Numeric 10
    "#" , "୰" , # late
    "$" , "ଽ" , 
    "&" , "ଌ" , # lu
    "*" , "ଞ୍ଚ" , # nc
    " " ,  "ଞ୍ଚ" , # nc
    "î" , "୍ରୁ" , # halanta-r-u
    "ï" , "୍ରୂ" , # halanta-r-dirgha u

    "Ð" , "କ୍ଷ୍ଣ" , # khya-N
    "Ñ" , "୍କ" ,  # halanta-k
    "Ò" , "୍ଖ" , # halanta-kh
    "Ó" , "୍ଗ" , # halanta-g
    "Ô" , "୍ଚ" , # halanta-c
    "Õ" , "୍ଜ" , # halanta-j
    "Ö" , "୍ଟ" , # halanta-T
    "×" , "୍ଠ" , # halanta-Th
    "Ø" , "୍ଡ" , # halanta-D
    "Ù" , "୍ଣ" , # halanta-N
    "Ú" , "୍ଥ" , # halanta-th
    "Û" , "୍ଧ" , # halanta-dh
    "Ü" , "୍ନ" , # halanta-n
    "Ý" , "୍ପ" , # halanta-p
    "Þ" , "୍ଫ" , # halanta-ph
    "ß" , "୍ୱ" , # halanta-b

    "<" , "ଣ୍ଟ" , # NT
    " " , "ଣ୍ଟ" , # NT
    "…" , "ଟ୍ଟ" , # TT
    "μ" , "ମ୍ପ" , # mp
    "µ" , "ମ୍ପ" , # mp
    "¶" , "ମ୍ଫ" , # mph
    "‰" , "ଣ୍ଣ" , # NN
    "Š" , "ଣ୍ଡ" , # ND

    "Œ" , "ଣ୍ଠ" , # NTh
    "™" , "ତ୍ମ" , # tm
    "š" , "ତ୍ପ" , # tp
    "›" , "ତ୍ସ" , # ts
    "œ" , "ତ୍ସ୍ନ" , # t-s-n
    "Ÿ" , "ଦ୍ଦ" , # d-dh

    "{" , "ଜ୍ଜ" , # jj
    "|" , "ଜ୍ଝ" , # j-jh
    "}" , "କ୍ର" , # kr

    "¡" , "ଦ୍ଧ" , # d-dh
    "¢" , "ଦ୍ଘ" , # d-gh
    "¤" , "ଧ୍ୟ" , # dhya
    "¦" , "ନ୍ଦ" , # nd
    "§" , "ନ୍ଧ" , # ndh
    "©" , "ତ୍ତ" , # tt
    " " , "ତ୍ତ" , # tt
    "ª" , "ନ୍ତ୍ର" , # ntr (jantra)
    "«" , "ନ୍ତ" , # nt
    "¬" , "ଞ୍ଜ" , # nj
    "ƒ" , "ଞ୍ଝ" , # njh
    "®" , "ପ୍ପ" , # pp
    "¯" , "ପ୍ତ" , # pt

    "°", "ପ୍ସ" , # ps
    "±" , "ବ୍ଦ" , # bd
    "²" , "ବ୍ଧ" , # bdh
    "´" , "ମ୍ବ" , # mb
    "¸" , "ମ୍ଭ" , # mbh
    " ̧" , "ମ୍ଭ", # ***mbha
    "̧" , "ମ୍ଭ", # mbha
    "¹" , "ମ୍ମ" , # mm
    "º" , "ଲ୍କ" , # lk
    "»" , "ଲ୍ଗ" , # lg
    "¼" , "ଶ୍ଛ" , # Nch
    "½" , "ଶ୍ଚ" , # S-ch (talabya sa - ca)
    "¾" , "ଷ୍ଣ" , # sh-N (murdhanya sa - Na)
    "¿" , "ଷ୍ପ" , # sh-p (murdhanya sa - pa)

    "À" , "ଷ୍ଫ" , # sh-ph (murdhanya sa - pha)
    "Á" , "ଷ୍ଟ" , # sh-T (murdhanya sa - Ta)
    "Â" , "ଷ୍ଠ" , # sh-Th (murdhanya sa - Tha)
    "Ã" , "ଷ୍କ" , # sh-k (murdhanya sa - ka)
    "Ä" , "ସ୍କ" , # s-k
    "Å" , "ସ୍ଖ" , # sh-kh
    "Æ" , "ସ୍ପ" , # sp
    "Ç" , "ସ୍ଫ" , # sph
    "È" , "ସ୍ତ୍ର" , # str
    "É" , "ସ୍ତ" , # st
    "Ê" , "ସ୍ୱ" , # sb
    "Ë" , "ଳ୍କ" , # lk
    "Ì" , "ଳ୍ପ" , # Lp
    "Í" , "ଳ୍ଫ" , # Lph
    "Î" , "ତ୍ଥ" , # t-th
    " " , "ତ୍ଥ" , # t-th
    "Ï" , "ଳ୍ଳ" , # L-L

    "@ା" , "ଆ" , # aa
    "@" , "ଅ" , # a
    "A" , "ଇ" , # i
    "B" , "ଈ" , # dirgha i
    "C" , "ଉ" , # u
    "D" , "ଊ" , # dirgha u
    "E" , "ଋ" , # R
    "F" , "ୠ" , # RR
    "G" , "ଏ" , # e
    "H" , "ଐ" , # ai
    "I" , "ଓ" , # o
    "J" , "ଔ" , # au 

    "K" , "କ" , # k
    "L" , "ଖ" , # kh
    "M" , "ଗ" , # g
    "N" , "ଘ" , # gh
    "O" , "ଙ" ,

    "P" , "ଚ",  # c
    "Q" , "ଛ", # ch
    "R" , "ଜ", # j
    "S" , "ଝ", # jh
    "T" , "ଞ", # Nya

    "U", "ଟ" , # T
    "V", "ଠ" , # Th
    "W", "ଡ" , # D
    "X", "ଢ" , # Dh
    "Y", "ଣ" , # N
    "Z" , "ତ" , # t
    "[" , "ଥ" , # th
    "\\" , "ଦ" , # d
    "]" , "ଧ" , # dh
    "^", "ନ" , # n
    "~" , "ଯ" , # y
    "_" , "ପ", # p
    "`" , "ଫ", # ph
    "a" , "ବ", # b
    "b" , "ଭ", # bh
    "c" , "ମ", # m
    "d" , "ୟ" , # y
    "e" , "ର" , # r
    "f" , "ଲ" , # l
    "g" , "ଶ" , # S (talabya sa)
    "h" , "ଷ" , # sh (murdhanya sa)
    "i" , "ସ" , # s
    "j" , "ହ" , # h
    "k" , "ଳ" , # L
    "l" , "କ୍ଷ" , # ksh
    "m" , "ଜ୍ଞ" , # gya
    "n" , "ଦ୍ଭ" , # d-bh
    "o" , "କ୍ଟ" , # kT
    "p" , "କ୍ଟ୍ର" , # kTr
    "q" , "କ୍ତ" , # kt
    "r" , "କ୍ସ" , # ks
    "s" , "ଗ୍ଦ" , # gd
    "t" , "ଗ୍ଧ" , # gdh
    "u" , "ଙ୍କ" , 
    "v" , "ଙ୍ଖ" ,
    "w" , "ଙ୍ଗ" ,
    "x" , "ଙ୍ଘ" ,
    "y" , "ଚ୍ଚ" ,
    "z" , "ଚ୍ଛ" ,
    " ̄", "ପ୍ତ",
    " ́", "ମ୍ବ",
    "‹", "ଣ୍ଢ" , # ndha
    "ଏø", " ଐ", # ai
    "୍ଯ" , "୍ୟ", # ja phala
    " ̈", "୍‍", # halanta with ZWJ
    "ଅା", "ଆ" # aa
]

# ====================================================
# Build Reverse Pairs (Unicode -> Akruti) identical to JS
# ====================================================
def build_reverse_pairs():
    seen = {}
    pairs = []
    for i in range(0, len(TEXT_ARRAY) - 1, 2):
        akruti = TEXT_ARRAY[i]
        unicode_val = TEXT_ARRAY[i + 1]
        if not unicode_val:
            continue
        if unicode_val in seen:
            continue
        seen[unicode_val] = True
        pairs.extend([unicode_val, akruti])
        
    entries = []
    for j in range(0, len(pairs) - 1, 2):
        entries.append((pairs[j], pairs[j + 1]))
        
    # Sort so longer Unicode strings are replaced before shorter ones
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
        # Exact While-loop replacement implementation
        for i in range(0, len(TEXT_ARRAY) - 1, 2):
            target = TEXT_ARRAY[i]
            replacement = TEXT_ARRAY[i + 1]
            while target in modified_substring:
                modified_substring = modified_substring.replace(target, replacement)
                
        # Regex mappings for adjusting position of e, ai, o, and au maatraas
        modified_substring = re.sub(r'([ù])([କଖଗଘଙଚଛଜଝଞଟଠଡଡ଼ଢଢ଼ଣତଥଦଧନପଫବଭମଯୟରଲବୱଶଷସହକ୍ଷଡ଼ଳ])', r'\2\1', modified_substring)
        modified_substring = re.sub(r'([ù])([୍])([କଖଗଘଚଛଜଝଟଠଡଡ଼ଢଢ଼ଣତଥନପଫବଭମୟରଲବୱଶଷସହକ୍ଷଡ଼ଳ])', r'\2\3\1', modified_substring)
        modified_substring = re.sub(r'([ù])([୍])([କଖଗଘଚଛଜଝଟଠଡଡ଼ଢଢ଼ଣତଥନପଫବଭମୟରଲବୱଶଷସହକ୍ଷଡ଼ଳ])', r'\2\3\1', modified_substring)
        modified_substring = modified_substring.replace("ùø", "ୌ")
        modified_substring = modified_substring.replace("ùା", "ୋ")
        modified_substring = modified_substring.replace("ù÷", "ୈ")
        modified_substring = modified_substring.replace("ù", "େ")

        # Regex mappings for adjusting position of reph (half r)
        reph_chars = r'[କଖଗଘଚଛଜଝଟଠଡଡ଼ଢଢ଼ଣତଥଦଧନପଫବଭମଯରଲଳଵଶଷସହକ୍ଷଜ୍ଞୟ]'
        matras = r'[ାିୀୁୂୃେୈୋୌଂଁ]'
        modified_substring = re.sub(rf'({reph_chars})({matras}*)à', r'ð\1\2', modified_substring)
        modified_substring = re.sub(rf'({reph_chars})({matras}*)ð', r'ð\1\2', modified_substring)
        modified_substring = re.sub(rf'({reph_chars})([୍])à', r'ð\1\2', modified_substring)
        modified_substring = re.sub(rf'({reph_chars})([୍])ð', r'ð\1\2', modified_substring)
        modified_substring = modified_substring.replace("ð", "ର୍")
        modified_substring = re.sub(r'([ଂଁ])([ାିୀୁୂୃେୈୋୌ])', r'\2\1', modified_substring)

        # Fix matra before halanta
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
# PDF Extractor
# ====================================================
def process_pdf(pdf_path, output_txt_path, direction="toUnicode"):
    print(f"Opening {pdf_path}...")
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Failed to open PDF: {e}")
        return

    converted_pages = []
    
    for i in range(len(doc)):
        page = doc.load_page(i)
        
        # Uses PyMuPDF's natural text block layout processing
        page_text = page.get_text("text")
        
        if direction == "toAkruti":
            converted = convert_to_akruti(page_text)
        else:
            converted = convert_to_unicode_odia(page_text)
            
        converted_pages.append(converted.strip())
        print(f"Processed page {i+1} / {len(doc)}")

    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write("\n\n--- Page Break ---\n\n".join(converted_pages))
    
    print(f"\n✅ Successfully converted and saved to: {output_txt_path}")

if __name__ == "__main__":
    # If run directly on the machine/repo, this scans and processes any local PDFs
    for pdf_file in glob.glob('*.pdf'):
        txt_name = pdf_file.replace('.pdf', '.txt')
        process_pdf(pdf_file, txt_name)
