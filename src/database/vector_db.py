import os
from dotenv import load_dotenv
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma

# Load API Key from .env
load_dotenv()

def build_knowledge_base():
    # 1. Load medical documents from data/raw
    if not os.path.exists('./data/raw'):
        os.makedirs('./data/raw')
        print("Created data/raw folder. Please add medical_notes.txt and run again.")
        return

    loader = DirectoryLoader('./data/raw', glob="./*.txt", loader_cls=TextLoader)
    documents = loader.load()

    if not documents:
        print("No text files found in data/raw!")
        return

    # 2. Split text into manageable chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = text_splitter.split_documents(documents)

    # 3. Create the searchable database using Google's free embedding model
    # Model gemini-embedding-001 is the stable 2026 replacement for text-embedding-004
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    
    vector_db = Chroma.from_documents(
        documents=chunks, 
        embedding=embeddings, 
        persist_directory="./data/vector_store"
    )
    
    print(f"✅ Success! Knowledge base built with {len(chunks)} snippets.")

if __name__ == "__main__":
    build_knowledge_base()