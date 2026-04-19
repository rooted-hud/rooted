#!/usr/bin/env python3
import os
import hashlib
import time
from urllib.parse import urlparse
from dotenv import load_dotenv
import google.genai as genai
import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from chunking import folder_to_chunks

load_dotenv('key.env')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not GEMINI_API_KEY:
    raise ValueError("Gemini API Key not provided.")

class GeminiEmbedding(EmbeddingFunction):
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.model_id = "models/gemini-embedding-001" 

    def __call__(self, input: Documents) -> Embeddings:
        response = self.client.models.embed_content(
            model=self.model_id,
            contents=input
        )
        return [item.values for item in response.embeddings]

class VectorDatabase:
    def __init__(self, path, api_key):
        self.db_path = path
        self.chroma_client = chromadb.PersistentClient(path=path)
        self.embedding_fn = GeminiEmbedding(api_key=api_key)
        self.main_collection = self.chroma_client.get_or_create_collection(
            name="main_collection", 
            embedding_function=self.embedding_fn
        )

    def _extract_metadata_from_url(self, url):
        """Automates Step 1: Finding metadata from the HUD URL structure."""
        if not url:
            return {"state": "National", "topic": "General"}
        
        path_parts = urlparse(url).path.split('/')
        metadata = {"state": "National", "topic": "General"}

        if 'states' in path_parts:
            idx = path_parts.index('states') + 1
            if idx < len(path_parts):
                metadata['state'] = path_parts[idx].upper()
        
        # Take the last part of the URL as a potential topic
        if len(path_parts) > 1:
            metadata['topic'] = path_parts[-1].replace('_', ' ').title()
            
        return metadata

    def add_documents(self, chunks: list):
        if len(chunks) == 0: return
        
        unique_chunks = {}
        for chunk in chunks:
            # 1. Enrich metadata from URL
            url = chunk.metadata.get("source_url", "")
            enriched_meta = self._extract_metadata_from_url(url)
            chunk.metadata.update(enriched_meta)

            # 2. Contextual Chunking: Inject metadata into text to help the Vector model
            # This makes a chunk about 'eligibility' distinct if it's for 'INDIANA'
            state = chunk.metadata.get('state', 'National')
            topic = chunk.metadata.get('topic', 'General')
            contextual_text = f"[{state} - {topic}] {chunk.page_content}"
            
            doc_id = hashlib.md5(contextual_text.encode()).hexdigest()
            
            if doc_id not in unique_chunks:
                unique_chunks[doc_id] = {
                    "content": contextual_text,
                    "metadata": chunk.metadata
                }

        ids = list(unique_chunks.keys())
        documents = [val["content"] for val in unique_chunks.values()]
        metadatas = [val["metadata"] for val in unique_chunks.values()]

        batch_size = 100 
        for i in range(0, len(ids), batch_size):
            self.main_collection.upsert(
                documents=documents[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size], 
                ids=ids[i : i + batch_size]
            )
            print(f"--- Indexed {min(i + batch_size, len(ids))}/{len(ids)} chunks ---")
            time.sleep(1.0) # Adjusted for stability

class ChatClient:
    def __init__(self, vector_db):
        self.vector_db = vector_db
        self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)

    def get_relevant_chunks(self, query, state_filter=None, n_results=3):
        # Implementation of Search-Time Filtering
        kwargs = {"query_texts": [query], "n_results": n_results}
        if state_filter:
            kwargs["where"] = {"state": state_filter}

        results = self.vector_db.main_collection.query(**kwargs)
        return results['documents'][0], results['metadatas'][0]

    def create_rag_prompt(self, query, relevant_context):
        return f"""You are a helpful and informative bot that answers questions using text from the reference passage included below.
Be sure to respond in a friendly and conversational tone.

<REFERENCE PASSAGE>
{relevant_context}
</REFERENCE PASSAGE>

QUESTION: '{query}'

ANSWER:
"""

    def generate_answer(self, query, state_filter=None):
        relevant_chunks, relevant_metadata = self.get_relevant_chunks(query, state_filter=state_filter)
        
        context_string = "\n\n----- \n\n".join(relevant_chunks)
        prompt = self.create_rag_prompt(query, context_string)

        # Updated model to 2.0-flash
        response = self.gemini_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        answer = response.text

        sources = set([meta.get("source_url") for meta in relevant_metadata if meta.get("source_url")])
        if sources:
            answer += "\n\n**Sources:**\n" + "\n".join([f"- {url}" for url in sources])

        return answer

if __name__ == "__main__":
    
    # 1. load data
    chunked_text = folder_to_chunks("./www.hud.gov")

    # 2. create vector database
    vector_db = VectorDatabase("./chroma_db", GEMINI_API_KEY)
    vector_db.add_documents(chunked_text)
    
    # 3. create chat client

    chat_client = ChatClient(vector_db)

    # Example: Manually passing 'INDIANA' as a filter
    user_query = "I'm looking for affordable and subsidzid housing'? STATE: Indiana INCOME: Less than 40,000 yearly"
    print(chat_client.generate_answer(user_query, state_filter="INDIANA"))