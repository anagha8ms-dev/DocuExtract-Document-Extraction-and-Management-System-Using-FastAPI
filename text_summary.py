from summarizer import generate_summary

text = """
DocuExtract is an AI-powered document processing system.
It allows users to upload PDF documents and extract text.
The extracted information can be summarized using a local AI model.
The application uses FastAPI, Python and MySQL.
"""

result = generate_summary(text)

print("Generated Summary:")
print(result)