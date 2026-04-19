#!/usr/bin/env python3
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
from rag import VectorDatabase, ChatClient

load_dotenv('key.env')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Loading Vector Database...")
vector_db = VectorDatabase("./chroma_db", GEMINI_API_KEY)
chat_client = ChatClient(vector_db)
print("Database loaded. Ready for queries!")


class ChatRequest(BaseModel):
    query: str

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        bot_answer = chat_client.generate_answer(request.query)
        return {"answer": bot_answer}
    except Exception as e:
        return {"answer": f"Sorry, an error occurred: {str(e)}"}