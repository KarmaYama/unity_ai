# core/tools.py
import os
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.agents import Tool

# NEW: imports for local retrieval
from langchain.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import GooglePalmEmbeddings
from langchain.vectorstores import FAISS
from langchain.chains import RetrievalQA

def setup_tools(api_key: str, llm):
    # Live web search
    search = DuckDuckGoSearchRun()

    # Local fact sheet retrieval
    loader = TextLoader("fact_sheet.txt", encoding="utf8")
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = splitter.split_documents(docs)
    embeddings = GooglePalmEmbeddings(api_key=api_key)
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
            description="Use this to answer questions from our static fact sheet."
        )
    ]
    return tools
