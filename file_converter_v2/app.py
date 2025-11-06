import os
from flask import Flask, render_template, request, send_file
from PIL import Image
from pdf2image import convert_from_bytes
import io # Used for in-memory file handling
import zipfile # Used to send multiple JPGs back

app = Flask(__name__)

# --- Helper Functions (The "Magic") ---

def convert_jpg_to_pdf(image_files):
    """Converts one or MORE JPG image files to a SINGLE PDF."""
    
    pil_images = []
    for image_file in image_files:
        image = Image.open(image_file)
        # Ensure image is in RGB mode (PDFs don't like some modes)
        if image.mode == 'RGBA' or image.mode == 'P':
            image = image.convert('RGB')
        pil_images.append(image)

    # Check if we have any images
    if not pil_images:
        return None # No images to convert

    # Create a PDF in memory
    pdf_buffer = io.BytesIO()
    
    # Save the first image, and append the rest
    pil_images[0].save(
        pdf_buffer, 
        format='PDF', 
        save_all=True, 
        append_images=pil_images[1:] # Add all other images
    )
    
    pdf_buffer.seek(0) # Rewind the buffer to the beginning
    return pdf_buffer

def convert_pdf_to_jpgs(pdf_file):
    """Converts a PDF (which could have many pages) into a list of JPG images."""
    # Read the PDF file's bytes
    pdf_bytes = pdf_file.read()
    
    # This is where Poppler is used. 
    images = convert_from_bytes(pdf_bytes)
    
    # Create a zip file in memory to hold the images
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zf:
        for i, image in enumerate(images):
            # Save each image to a temporary in-memory buffer
            img_buffer = io.BytesIO()
            image.save(img_buffer, format='JPEG')
            img_buffer.seek(0)
            # Add the image to the zip file
            zf.writestr(f'page_{i+1}.jpg', img_buffer.read())
            
    zip_buffer.seek(0)
    return zip_buffer

# --- Flask Routes (The "Web Server") ---

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert():
    """Handles the file upload and conversion logic."""
    
    # THIS IS THE CHANGE: Use .getlist() to get multiple files
    files = request.files.getlist('file')
    
    if not files or files[0].filename == '':
        return "No selected file", 400
        
    conversion_type = request.form['conversion_type']

    if conversion_type == 'jpg_to_pdf':
        try:
            # Pass the whole list of files to the function
            pdf_buffer = convert_jpg_to_pdf(files)
            if pdf_buffer:
                return send_file(
                    pdf_buffer,
                    as_attachment=True,
                    download_name='converted.pdf',
                    mimetype='application/pdf'
                )
            else:
                return "No valid JPG images found", 400
        except Exception as e:
            return f"Error during JPG to PDF conversion: {e}", 500

    elif conversion_type == 'pdf_to_jpg':
        try:
            # PDF to JPG only ever takes one file
            if len(files) > 1:
                return "Please upload only one PDF for PDF-to-JPG conversion.", 400
                
            zip_buffer = convert_pdf_to_jpgs(files[0])
            return send_file(
                zip_buffer,
                as_attachment=True,
                download_name='converted_images.zip',
                mimetype='application/zip'
            )
        except Exception as e:
            # This is often where the Poppler error will show up
            return f"Error during PDF to JPG conversion: {e}.", 500

    return "Invalid conversion type", 400

# This runs the app
if __name__ == '__main__':
    app.run(debug=True)