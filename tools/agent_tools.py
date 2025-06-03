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
FAISS_INDEX_NAME = "fact_sheet_index" # Renamed for clarity, consistent with LangChain's param name

def build_memory(config: Config):
    """Load/load and save the fact sheet embeddings using FAISS."""
    embeddings = HuggingFaceEmbeddings(model_name=config.AGENT_EMBEDDING_MODEL)

    # Construct full paths for the expected FAISS files
    faiss_file = os.path.join(FAISS_INDEX_PATH, f"{FAISS_INDEX_NAME}.faiss")
    pkl_file = os.path.join(FAISS_INDEX_PATH, f"{FAISS_INDEX_NAME}.pkl")

    # Check for the existence of both the .faiss and .pkl files within the directory
    if os.path.exists(FAISS_INDEX_PATH) and os.path.exists(faiss_file) and os.path.exists(pkl_file):
        print("[INFO] Loading existing FAISS index...")
        # IMPORTANT SECURITY NOTE:
        # Setting allow_dangerous_deserialization=True is necessary because FAISS.load_local()
        # relies on loading a pickle file (.pkl). Pickle files can execute arbitrary code.
        # This is considered 'safe' in this specific context ONLY IF:
        # 1. You are the sole creator of the 'faiss_index' files.
        # 2. These files are stored locally and never sourced from untrusted origins.
        # 3. These files are not shared with others who might modify them maliciously.
        # If any of these conditions are not met, this poses a security risk.
        vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, index_name=FAISS_INDEX_NAME, allow_dangerous_deserialization=True)
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
        # Save using the directory path and the index_name
        vectorstore.save_local(FAISS_INDEX_PATH, index_name=FAISS_INDEX_NAME)
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
