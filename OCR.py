#--------------------------------------------------------------------------
# Image Preprocessing
#-------------------------------------------------------------------------
    #CONVERTING the User CV  to images for better handling in the OCR phase 
#-------------------------------------------------------------------------

from pdf2image import convert_from_path


User_CV = 'CV_.pdf'
#output_folder = "converted_images"
pages = convert_from_path(User_CV)

  # THE variable `pages` is a list of image objects corresponding to each page of the PDF. 

#--------------------------------------------------------------------
# Saving the converted images to a folder for later use in OCR processing.
#import os
#os.makedirs(output_folder, exist_ok=True)

#for i, page in enumerate(pages):
#    image_path = os.path.join(output_folder, f"page_{i+1}.png")
#    page.save(image_path, "PNG")

#---------------------------------------------------------------------
   

import cv2
import numpy as np

def deskew(image):    
    
    # this function is used to correct the orientation of the image 
    # by calculating the angle of skew and rotating it accordingly.

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bitwise_not(gray)
    coords = np.column_stack(np.where(gray > 0))
    angle = cv2.minAreaRect(coords)[-1]
    
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    return rotated




#------------------------------------
#Running OCR using pytesseract
#------------------------------------

import pytesseract

def extract_text_from_image(pages):
    text = pytesseract.image_to_string(pages)
    return text


print(extract_text_from_image(pages[0]))  
# This will print the extracted text from the first page of the PDF. 

