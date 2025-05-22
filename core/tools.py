import os
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.agents import Tool
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA

class RetrieverWrapper:
    """Wraps a LangChain retriever to give .invoke(query) → str(summary)."""
    def __init__(self, retriever):
        self._retriever = retriever

    def invoke(self, query: str) -> str:
        # 1) Pull the top-k documents
        docs = self._retriever.get_relevant_documents(query)
        if not docs:
            return "I couldn’t find anything matching that in my fact sheet."

        # 2) Extract each document’s Title line
        titles = []
        for doc in docs:
            content = getattr(doc, "page_content", str(doc))
            for line in content.splitlines():
                if line.lower().startswith("title:"):
                    # grab text after "Title:"
                    titles.append(line.split(":", 1)[1].strip())
                    break

        # 3) Build a bullet-list summary
        summary_lines = [f"• {t}" for t in titles]
        summary = "\n".join(summary_lines)

        # 4) Return a single string
        return f"From my fact sheet, I know about:\n{summary}"

def setup_tools(api_key: str, llm, return_retriever_only=True):
    # Live web search
    search = DuckDuckGoSearchRun()

    # Load and chunk the fact sheet
    loader = TextLoader("fact_sheet.txt", encoding="utf8")
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = splitter.split_documents(docs)

    # Build FAISS
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vs = FAISS.from_documents(chunks, embeddings)
    # limit to top 4 docs
    retriever = vs.as_retriever(search_kwargs={"k": 4})

    # Wrap it so .invoke() always returns a string
    retriever_wrapper = RetrieverWrapper(retriever)

    # Full QA chain for your agent tools
    fact_qa = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
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
            description="Answer user questions from the local fact sheet."
        ),
    ]

    return retriever_wrapper if return_retriever_only else tools
