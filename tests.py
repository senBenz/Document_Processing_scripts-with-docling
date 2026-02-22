#scripts testing file 
from pdf2image import convert_from_path

User_CV = 'CV_.pdf'
pages = convert_from_path(User_CV)
