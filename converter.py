import glob
import ocrmypdf
import os

def process_pdfs():
    # Find all PDFs in the current directory
    for pdf_file in glob.glob("*.pdf"):
        # Skip files that have already been processed
        if not pdf_file.endswith("_ocr.pdf"):
            output_file = f"{os.path.splitext(pdf_file)[0]}_ocr.pdf"
            
            # Skip if the OCR version already exists
            if os.path.exists(output_file):
                continue
                
            print(f"Starting OCR on: {pdf_file} -> {output_file}")
            
            try:
                # Run OCR with Odia language (ori)
                # force_ocr=True ensures text is extracted even if some vector text exists
                # optimize=1 compresses the output to manage file size
                ocrmypdf.ocr(
                    input_file=pdf_file,
                    output_file=output_file,
                    language="ori",
                    force_ocr=True,
                    optimize=1
                )
                print(f"Successfully created: {output_file}")
            except Exception as e:
                print(f"Failed to process {pdf_file}. Error: {e}")

if __name__ == "__main__":
    process_pdfs()
