import glob
import os
import cv2
import numpy as np
from pdf2image import convert_from_path
import pytesseract

def preprocess_image_for_ocr(pil_image):
    # Convert PIL Image to OpenCV format (NumPy array)
    open_cv_image = np.array(pil_image)
    
    # Convert RGB to BGR (OpenCV's default color format)
    if len(open_cv_image.shape) == 3 and open_cv_image.shape[2] == 3:
        open_cv_image = open_cv_image[:, :, ::-1].copy()
    
    # 1. Convert to Grayscale
    gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
    
    # 2. Apply Otsu's Thresholding (Binarization)
    # This turns the image into pure black and white, removing shadows and noise
    _, binary_image = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return binary_image

def process_pdfs():
    for pdf_file in glob.glob("*.pdf"):
        output_file = f"{os.path.splitext(pdf_file)[0]}_ocr.txt"
        
        if os.path.exists(output_file):
            continue
            
        print(f"Starting advanced OCR on: {pdf_file} -> {output_file}")
        
        try:
            images = convert_from_path(pdf_file, dpi=300) # High DPI for better accuracy
            full_text = ""
            
            for i, image in enumerate(images):
                print(f"  Preprocessing and reading page {i + 1}...")
                
                # Clean the image using OpenCV before passing to Tesseract
                clean_image = preprocess_image_for_ocr(image)
                
                # Extract text using BOTH Odia and English best models
                # psm 3 is standard page segmentation, good for blocks of text
                page_text = pytesseract.image_to_string(
                    clean_image, 
                    lang="ori+eng", 
                    config="--psm 3"
                )
                
                full_text += f"--- Page {i + 1} ---\n{page_text}\n\n"
            
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(full_text)
                
            print(f"Successfully created: {output_file}")
            
        except Exception as e:
            print(f"Failed to process {pdf_file}. Error: {e}")

if __name__ == "__main__":
    process_pdfs()
