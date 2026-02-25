#scripts testing file 
from pdf2image import convert_from_path

User_CV = 'Dummy_CV_as_PDF.pdf'
output_folder = "converted_images"
pages = convert_from_path(User_CV)

import os
os.makedirs(output_folder, exist_ok=True)

for i, page in enumerate(pages):
    image_path = os.path.join(output_folder, f"page_{i+1}.png")
    page.save(image_path, "PNG")
