#  SecBoard\SecBoard\app_suib\utils.py
# import pdfplumber
# from docx import Document
# from .models import AccessAssets


# def extract_text_from_file(file_path):
#     file_extension = file_path.split('.')[-1].lower()
#     if file_extension == 'pdf':
#         return extract_text_from_pdf(file_path)
#     elif file_extension in ['doc', 'docx']:
#         return extract_text_from_word(file_path)
#     elif file_extension == 'txt':
#         try:
#             with open(file_path, 'r', encoding='utf-8') as file:
#                 return file.read()
#         except FileNotFoundError:
#             print(f"File not found: {file_path}")
#             return ""  # Return an empty string or handle the error as needed
#     else:
#         return ''

# def extract_text_from_pdf(file_path):
#     try:
#         with pdfplumber.open(file_path) as pdf:
#             text = "".join(page.extract_text() for page in pdf.pages)
#         return text
#     except Exception as e:
#         return f"Error reading PDF file: {str(e)}"

# def extract_text_from_word(file_path):
#     try:
#         doc = Document(file_path)
#         return "\n".join(paragraph.text for paragraph in doc.paragraphs)
#     except Exception as e:
#         return f"Error reading Word file: {str(e)}"


