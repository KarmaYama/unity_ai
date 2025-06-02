# tools/agent_tools.py

import os
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.agents import Tool
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from core.config import Config # Import Config to get settings

# Define the directory for saving the FAISS index
FAISS_INDEX_PATH = "faiss_index"
FAISS_INDEX_FILENAME = "fact_sheet_index"

def build_memory(config: Config):
    """Load/load and save the fact sheet embeddings using FAISS."""
    embeddings = HuggingFaceEmbeddings(model_name=config.AGENT_EMBEDDING_MODEL)
    faiss_file_path = os.path.join(FAISS_INDEX_PATH, FAISS_INDEX_FILENAME)

    if os.path.exists(FAISS_INDEX_PATH) and os.path.exists(f"{faiss_file_path}.pkl"):
        print("[INFO] Loading existing FAISS index...")
        vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, file_path=f"{faiss_file_path}.pkl")
        return vectorstore.as_retriever(search_kwargs={"k": config.AGENT_RETRIEVER_K})
    else:
        print("[INFO] Creating new FAISS index...")
        loader = TextLoader(config.AGENT_FACT_SHEET_PATH, encoding="utf8")
        docs = loader.load()
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.AGENT_TEXT_SPLITTER_CHUNK_SIZE,
            chunk_overlap=config.AGENT_TEXT_SPLITTER_CHUNK_OVERLAP
        )
        chunks = splitter.split_documents(docs)
        vectorstore = FAISS.from_documents(chunks, embeddings)
        os.makedirs(FAISS_INDEX_PATH, exist_ok=True)
        vectorstore.save_local(FAISS_INDEX_PATH, index_name=f"{FAISS_INDEX_FILENAME}.pkl") # Changed to index_name
        print(f"[INFO] FAISS index saved to {FAISS_INDEX_PATH}")
        return vectorstore.as_retriever(search_kwargs={"k": config.AGENT_RETRIEVER_K})

def setup_tools(config: Config, llm, return_retriever_only=False):
    """Returns a list of Tools for the main agent."""
    search = DuckDuckGoSearchRun()
    memory_retriever = build_memory(config) # Pass config to build_memory
    fact_qa = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=memory_retriever,
        return_source_documents=False,
    )

    tools = [
        Tool(
            name="DuckDuckGo Search",
            func=search.run,
            description="Use this to look up live information."
        ),
        Tool(
            name="LocalFactSheet",
            func=lambda q: fact_qa.run(q),
            description="Answer detailed questions from the local fact sheet."
        ),
    ]

    if return_retriever_only:
        return memory_retriever
    return tools