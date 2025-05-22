import os
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.agents import Tool
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA

def setup_tools(api_key: str, llm):
    # Live web search
    search = DuckDuckGoSearchRun()

    # Load the fact sheet directly from the root directory
    loader = TextLoader("fact_sheet.txt", encoding="utf8")
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = splitter.split_documents(docs)

    # Use HuggingFace embeddings
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # Vector store
    vectorstore = FAISS.from_documents(chunks, embeddings)
    fact_qa = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=vectorstore.as_retriever(),
        return_source_documents=False,
    )

    tools = [
        Tool(
            name="DuckDuckGo Search",
            func=search.run,
            description="Use this to look up very recent or live information."
        ),
        Tool(
            name="LocalFactSheet",
            func=lambda q: fact_qa.run(q),
            description="Use this to answer questions about legal rights, asylum, detention, housing, health, education, employment, and emergency contacts specifically from our local fact sheet."
        )
    ]
    # Return the retriever for direct use in the reflection agent
    return fact_qa.retriever