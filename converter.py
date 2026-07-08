import glob
import os
from pdf2image import convert_from_path
import pytesseract

def process_pdfs():
    # Find all PDFs in the current directory
    for pdf_file in glob.glob("*.pdf"):
        # Create output filename with .txt extension
        output_file = f"{os.path.splitext(pdf_file)[0]}_ocr.txt"
        
        # Skip if the OCR text file already exists
        if os.path.exists(output_file):
            continue
            
        print(f"Starting text extraction on: {pdf_file} -> {output_file}")
        
        try:
            # Convert PDF pages into images
            # This is necessary because Tesseract extracts text from images
            images = convert_from_path(pdf_file)
            full_text = ""
            
            # Run OCR on each page using Odia language (ori)
            for i, image in enumerate(images):
                print(f"  Processing page {i + 1}...")
                page_text = pytesseract.image_to_string(image, lang="ori")
                full_text += f"--- Page {i + 1} ---\n{page_text}\n\n"
            
            # Save the extracted text to a .txt file (utf-8 is crucial for Odia script)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(full_text)
                
            print(f"Successfully created: {output_file}")
            
        except Exception as e:
            print(f"Failed to process {pdf_file}. Error: {e}")

if __name__ == "__main__":
    process_pdfs()
