#!/usr/bin/env python3
import os
from dotenv import load_dotenv
import google.genai as genai
import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from chunking import folder_to_chunks
import uuid
import hashlib
import time
import argparse

load_dotenv('.env')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("Gemini API Key not provided. Please provide GEMINI_API_KEY as an environment variable")

class GeminiEmbedding(EmbeddingFunction):
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.model_id = "models/gemini-embedding-001" 
        # Or use the preview model for potentially better performance:
        # model_id = "models/gemini-embedding-2-preview"

    def __call__(self, input: Documents) -> Embeddings:
        response = self.client.models.embed_content(
            model=self.model_id,
            contents=input
        )
        # The Gemini API returns a list of objects; ChromaDB needs a list of lists of floats.
        return [item.values for item in response.embeddings]

class VectorDatabase:
    def __init__(self, api_key, path="./chroma_db", name="main_collection"):
        self.db_path = path
        self.chroma_client = chromadb.PersistentClient(path=path)
        self.main_collection = self.chroma_client.get_or_create_collection(
            name=name, 
            embedding_function=GeminiEmbedding(api_key=api_key)
        )
        # We only support using 1 collection. In the future it would be good to add support for multiple!
    
    def add_documents(self, chunks: list):
        if len(chunks) == 0: return
        
        # 1. Deduplicate based on content (MD5 Hash)
        unique_chunks = {}
        for chunk in chunks:
            content = chunk.page_content
            doc_id = hashlib.md5(content.encode()).hexdigest()
            if doc_id not in unique_chunks:
                unique_chunks[doc_id] = {
                    "content": content,
                    "metadata": chunk.metadata
                }

        # 2. Convert to lists for indexing
        ids = list(unique_chunks.keys())
        documents = [val["content"] for val in unique_chunks.values()]
        metadatas = [val["metadata"] for val in unique_chunks.values()]

        # 3. BATCHING LOGIC: Process 100 chunks at a time
        batch_size = 100 
        total_unique = len(ids)
        
        print(f"Starting index of {total_unique} unique chunks in batches of {batch_size}...")

        for i in range(0, total_unique, batch_size):
            # Slice the lists to get the current batch
            batch_ids = ids[i : i + batch_size]
            batch_docs = documents[i : i + batch_size]
            batch_metas = metadatas[i : i + batch_size]
            
            # Upsert this specific batch
            self.main_collection.upsert(
                documents=batch_docs,
                metadatas=batch_metas, 
                ids=batch_ids
            )
            
            # Progress update
            current_count = min(i + batch_size, total_unique)
            print(f"--- Indexed {current_count}/{total_unique} chunks ---")
            time.sleep(2.1) # Wait between batches

        print(f"--- Finished! Successfully indexed {total_unique} unique chunks. ---")


class ChatClient:
    def __init__(self, vector_db):
        self.vector_db = vector_db
        self.gemini_api_key = GEMINI_API_KEY
        self.gemini_client = genai.Client(api_key=self.gemini_api_key)
        self.history = []  # List of {"question": ..., "answer": ...} dicts

    def get_relevant_chunks(self, query, n_results=3):
        results = self.vector_db.main_collection.query(query_texts=[query], n_results=n_results)

        relevant_chunks = results['documents'][0]
        relevant_metadata = results['metadatas'][0]

        print(f"\nResults for: {query}")
        for doc in results['documents'][0]:
            print(f"- {doc[:300]}...")
    


        return relevant_chunks, relevant_metadata

    def create_rag_prompt(self, relevant_context, query):
 
        history_text = ""
        if self.history:
            history_text = "CONVERSATION HISTORY:\n"
            for turn in self.history:
                history_text += f"Question: {turn['question']}\nAnswer: {turn['answer']}\n\n"
 
        prompt = ("""You are a helpful and informative bot that answers questions using text from the sources included below. Sources are fetched based on the user's questions. \
                Answer concisely and strike a friendly and converstional tone. Be sure to ask the user relevant questions that might lead to more helpful sources. \
        If the sources are irrelevant to the answer, you may ignore it.
 
        {history_text}
        <START OF SOURCES>
        {relevant_context}
        <END OF SOURCES>
 
        Question:
        {query}
 
        Answer:
        """).format(query=query, relevant_context=relevant_context, history_text=history_text)
 
        return prompt
 
    def generate_answer(self, query):
        relevant_chunks, relevant_metadata = self.get_relevant_chunks(query, n_results=5)
 
        prompt = self.create_rag_prompt(relevant_context="\n\n---\n\n".join(relevant_chunks), query=query)
 
        response = self.gemini_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        answer = response.text
 
        # Save this turn to history
        self.history.append({"question": query, "answer": answer})
 
        # Extract unique source URLs as a separate list (preserving order)
        seen = set()
        sources = []
        for meta in relevant_metadata:
            url = meta.get("source_url")
            if url and url not in seen:
                seen.add(url)
                sources.append(url)
 
        return answer, sources, relevant_chunks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape a website and save pages as Markdown files.")
    parser.add_argument("data_folder", type=str, default="./www.hud.gov", help="Path to the folder containing all Markdown files")
    parser.add_argument("-v", "--database_path", type=str, default="./chroma_db", help="(default: ./chroma_db)")
    parser.add_argument("-c", "--collection_name", type=str, default="main_collection", help="Name of collection within vector database (default: \"main_collection\")")
    
    args = parser.parse_args()

    # 1. load data
    chunked_text = folder_to_chunks(args.data_folder)

    # 2. create collection in vector database
    vector_db = VectorDatabase(GEMINI_API_KEY, args.database_path, args.collection_name)
    vector_db.add_documents(chunked_text)

    # 3. create chat client
    chat_client = ChatClient(vector_db)

    answer, sources, chunks = chat_client.generate_answer("I am a homeless veteran and need a Housing Choice Voucher. Who can I contact?")
    print(answer, sources)
