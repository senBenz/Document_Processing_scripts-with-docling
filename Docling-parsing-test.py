from docling.document_converter import DocumentConverter

source = "Dummy_CV_as_DOCX.docx"
converter = DocumentConverter()
doc = converter.convert(source).document
print(doc.export_to_markdown())
 
