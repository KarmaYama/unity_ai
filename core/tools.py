# core/tools.py

import os
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.agents import Tool
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA


def build_memory(api_key: str):
    """
    Load the fact sheet, chunk it, embed it, and return a FAISS retriever
    that will serve as Unity’s 'neural brain'.
    """
    loader = TextLoader("fact_sheet.txt", encoding="utf8")
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    chunks = splitter.split_documents(docs)

    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vs = FAISS.from_documents(chunks, embeddings)
    return vs.as_retriever(search_kwargs={"k": 5})


def setup_tools(api_key: str, llm, return_retriever_only=False):
    """
    Returns:
      - If return_retriever_only=False: a list of Tools for the main agent (web search + LocalFactSheet QA).
      - If return_retriever_only=True: just the retriever (for backward compatibility).
    """
    # 1) Live web search
    search = DuckDuckGoSearchRun()

    # 2) Full QA chain over the same vectorstore
    #    (useful if you want a 'LocalFactSheet' tool alongside memory-based QA)
    memory_retriever = build_memory(api_key)
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
