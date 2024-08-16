from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from PyPDF2 import PdfReader
import re
from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Access API key and Assistant ID from .env file
api_key = os.getenv("OPENAI_API_KEY")
assistant_id = os.getenv("ASSISTANT_ID")

if not api_key or not assistant_id:
    raise ValueError("API key or Assistant ID not set in .env file")

# Initialize OpenAI client with the API key
client = OpenAI(api_key=api_key)

# Define a Pydantic model for the chat request body
class ChatRequest(BaseModel):
    user_query: str
    documents_content: str

# Function to extract text from PDF
def extract_text_from_pdf(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

@app.get("/")
def read_root():
    return {"message": "Welcome to the FastAPI backend!"}

@app.post("/upload")
async def upload_files(file: UploadFile = File(...)):
    if file.filename.lower().endswith('.pdf'):
        try:
            file_content = extract_text_from_pdf(file.file)
            return JSONResponse(content={"message": "File uploaded and content extracted successfully.", "content": file_content[:1000]})
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to extract content: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

@app.post("/chat")
async def chat(request: ChatRequest):
    user_query = request.user_query.strip()
    documents_content = request.documents_content.strip()

    if not user_query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    if not documents_content:
        raise HTTPException(status_code=400, detail="No content has been provided. Please upload documents first.")

    try:
        # Create a thread for the user's query
        thread = client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": f"{user_query}\n\nDocuments:\n{documents_content}",
                }
            ]
        )

        # Run and poll the thread for a response
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id, assistant_id=assistant_id, timeout=300  # 5 minutes timeout
        )

        # Retrieve messages
        messages = list(client.beta.threads.messages.list(thread_id=thread.id, run_id=run.id))

        if not messages:
            raise HTTPException(status_code=500, detail="No response received. Please try again.")

        # Log raw messages for debugging
        print("Raw messages:", messages)

        # Extract the content from the response
        if messages and messages[0].content:
            content_blocks = messages[0].content
            if content_blocks and isinstance(content_blocks, list):
                # Extract the text value from each content block
                response_text = ""
                for block in content_blocks:
                    if hasattr(block, 'text') and hasattr(block.text, 'value'):
                        response_text += block.text.value
                # Clean up the response
                cleaned_response = re.sub(r'【\d+:\d+†source】', '', response_text)
                return {"response": cleaned_response}
            else:
                raise HTTPException(status_code=500, detail="Unexpected content format in the response.")
        else:
            raise HTTPException(status_code=500, detail="Response content is missing or malformed.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# Instructions to run the FastAPI app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, debug=True)
