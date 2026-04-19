import os
from langchain_text_splitters import RecursiveCharacterTextSplitter

def concatenate_markdown_files(folder_path, output_filename=""):
    markdown_contents = []
    
    # Sort files to ensure a consistent merge order
    files = sorted(os.listdir(folder_path))
    
    for filename in files:
        if filename.endswith(".md") or filename.endswith(".markdown"):
            file_path = os.path.join(folder_path, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                markdown_contents.append(f.read())
    
    text = "\n\n---\n\n".join(markdown_contents) 

    if output_filename != "":
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Successfully merged {len(markdown_contents)} files into {output_filename}")
    
    return text

def folder_to_chunks(folder_path):
    docs = []
    metadatas = []
    
    # Read each file and extract the URL from the first line
    for filename in sorted(os.listdir(folder_path)):
        if filename.endswith((".md", ".markdown")):
            file_path = os.path.join(folder_path, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if len(lines) > 2:
                    url = lines[0].strip() # Grab the URL from line 1
                    content = "".join(lines[2:]) # Skip URL and '---'
                    docs.append(content)
                    metadatas.append({"source_url": url}) # Store as a dict

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2500,       
        chunk_overlap=500,     
        length_function=len,  
        is_separator_regex=False,
    )

    # Pass the metadatas array to Langchain
    chunks = text_splitter.create_documents(docs, metadatas=metadatas)
    print(f"Split into {len(chunks)} chunks.")
    
    # Return the full Document objects, not just the text!
    return chunks
