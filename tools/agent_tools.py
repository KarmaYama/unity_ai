import os
import re
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.agents import Tool
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from core.config import Config # Import Config to get settings
# from core.security.security_utils import is_path_secure_and_within_root # If you have a separate module for this

# Directory/filenames for FAISS index
# SECURITY NOTE: These paths are relative to the execution directory.
# In a production environment, ensure this path is secured and writable
# only by the application user.
# IMPORTANT CHANGE: Adjust FAISS_INDEX_PATH to be relative to _ALLOWED_DATA_ROOT
FAISS_INDEX_SUBDIR = "faiss_index" # Define just the subdirectory name
FAISS_INDEX_NAME = "zira_database"    # Define the FAISS index base name (change as needed)


# Define an allowed root directory for the fact sheet and FAISS index
# This is a critical security control against path traversal.
# You MUST configure this to a specific, non-sensitive directory.
# Example: '/var/lib/zira/data' or 'C:\ProgramData\Zira\Data'
_ALLOWED_DATA_ROOT = os.path.abspath(os.path.join(os.getcwd(), "data")) # Default to a 'data' subfolder in current working dir
# SECURITY NOTE: Replace os.getcwd() with a fixed, secure, and non-user-writable
# directory path in a production deployment, e.g., '/opt/zira/data'.

def _is_safe_path(base_path: str, proposed_path: str, logger) -> bool:
    """
    Validates if a proposed_path is canonicalized and falls within the base_path.
    Prevents path traversal attacks (e.g., via '..', symlinks).
    """
    if not proposed_path:
        logger.error("Proposed path is empty.")
        return False

    try:
        abs_base_path = os.path.abspath(base_path)
        abs_proposed_path = os.path.abspath(proposed_path)
    except Exception as e:
        logger.error(f"Error canonicalizing path: {e}")
        return False

    if ".." in abs_proposed_path.split(os.sep):
        logger.warning(f"Path traversal attempt detected: {proposed_path}")
        return False

    try:
        resolved_proposed_path = os.path.realpath(abs_proposed_path)
    except Exception as e:
        logger.error(f"Error resolving real path for {proposed_path}: {e}")
        return False

    if not resolved_proposed_path.startswith(os.path.realpath(abs_base_path)):
        logger.warning(f"Path '{proposed_path}' resolves to '{resolved_proposed_path}' which is outside allowed base '{abs_base_path}'.")
        return False

    return True


def build_memory(config: Config, logger) -> "FAISS.Retriever":
    """
    Loads (or creates) a FAISS vectorstore from the local fact‐sheet.
    Returns a Retriever with search_kwargs={'k': config.AGENT_RETRIEVER_K}.
    """
    embeddings = HuggingFaceEmbeddings(model_name=config.AGENT_EMBEDDING_MODEL)

    # Construct the full, expected path for FAISS index, relative to _ALLOWED_DATA_ROOT
    # This ensures the FAISS index is always placed inside the 'data' directory.
    FAISS_FULL_INDEX_PATH = os.path.join(_ALLOWED_DATA_ROOT, FAISS_INDEX_SUBDIR)

    # Validate FAISS index paths using the constructed full path
    if not _is_safe_path(_ALLOWED_DATA_ROOT, FAISS_FULL_INDEX_PATH, logger):
        # This error should now ideally not be hit if FAISS_FULL_INDEX_PATH is correctly formed
        raise ValueError(f"FAISS index path '{FAISS_FULL_INDEX_PATH}' is not secure or outside allowed data root.")
    
    faiss_file = os.path.join(FAISS_FULL_INDEX_PATH, f"{FAISS_INDEX_NAME}.faiss")
    pkl_file = os.path.join(FAISS_FULL_INDEX_PATH, f"{FAISS_INDEX_NAME}.pkl")

    try:
        # If both the .faiss and .pkl exist, we assume an index is already built
        if os.path.exists(FAISS_FULL_INDEX_PATH) and os.path.exists(faiss_file) and os.path.exists(pkl_file):
            logger.info("Loading existing FAISS index from '%s'.", FAISS_FULL_INDEX_PATH)
            
            # SECURITY WARNING: allow_dangerous_deserialization=True
            # This flag is DANGEROUS if you cannot guarantee the integrity
            # of your FAISS index files (faiss_index/*.faiss and *.pkl).
            # An attacker who can write to FAISS_FULL_INDEX_PATH could inject
            # malicious code into the .pkl file that executes on load.
            # ONLY set this to True if you have stringent filesystem permissions
            # and integrity checks on FAISS_FULL_INDEX_PATH and its contents.
            # In a high-security environment, consider alternative serialization
            # methods or strong cryptographic integrity checks on these files.
            # For this project, assuming self-generated and trusted files.
            vectorstore = FAISS.load_local(
                FAISS_FULL_INDEX_PATH,
                embeddings,
                index_name=FAISS_INDEX_NAME,
                allow_dangerous_deserialization=True
            )
            return vectorstore.as_retriever(search_kwargs={"k": config.AGENT_RETRIEVER_K})

        # Otherwise, create a new FAISS index
        logger.info("Creating new FAISS index at '%s'.", FAISS_FULL_INDEX_PATH)

        # Validate the fact sheet file path before loading
        if not _is_safe_path(_ALLOWED_DATA_ROOT, config.AGENT_FACT_SHEET_PATH, logger):
            raise ValueError(f"Fact sheet path '{config.AGENT_FACT_SHEET_PATH}' is not secure or outside allowed data root.")

        if not os.path.exists(config.AGENT_FACT_SHEET_PATH):
            logger.error(
                "Fact sheet file not found at '%s'. Cannot build FAISS index.",
                config.AGENT_FACT_SHEET_PATH
            )
            raise FileNotFoundError(f"Missing fact sheet: {config.AGENT_FACT_SHEET_PATH}")

        # Input Validation: TextLoader expects a file path. No direct user input here.
        loader = TextLoader(config.AGENT_FACT_SHEET_PATH, encoding="utf8")
        docs = loader.load()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.AGENT_TEXT_SPLITTER_CHUNK_SIZE,
            chunk_overlap=config.AGENT_TEXT_SPLITTER_CHUNK_OVERLAP
        )
        chunks = splitter.split_documents(docs)

        vectorstore = FAISS.from_documents(chunks, embeddings)

        # Ensure the directory exists, then save
        # SECURITY NOTE: os.makedirs(exist_ok=True) is safe for directory creation.
        # Permissions for created directories should be restricted (e.g., 0o700).
        # Python's default for os.makedirs doesn't set specific permissions for new directories,
        # so consider setting umask or explicitly using os.chmod if not running in a container
        # with controlled permissions.
        os.makedirs(FAISS_FULL_INDEX_PATH, exist_ok=True) # Use the full path for creation
        vectorstore.save_local(FAISS_FULL_INDEX_PATH, index_name=FAISS_INDEX_NAME) # Use the full path for saving

        logger.info("FAISS index created and saved to '%s'.", FAISS_FULL_INDEX_PATH)
        return vectorstore.as_retriever(search_kwargs={"k": config.AGENT_RETRIEVER_K})

    except Exception as e:
        logger.error("Error building/loading FAISS index: %s", e, exc_info=True)
        # Fail-secure: Re-raise to prevent agent from operating with a corrupted or missing index.
        raise


def setup_tools(config: Config, llm, logger=None) -> list[Tool]:
    """
    Returns a list of LangChain Tools for your agent:
      - "DuckDuckGo Search" (live web search)
      - "LocalFactSheet" (answers from your local fact sheet via FAISS + RetrievalQA)
    """

    # Ensure we have a logger to record FAISS status
    if logger is None:
        # In case setup_tools is called outside of main, create a temporary logger
        from core.logger_config import setup_logger as _setup
        logger = _setup(config)

    # 1) DuckDuckGo for live search
    # SECURITY NOTE: DuckDuckGoSearchRun is generally safe as it abstracts the
    # search query. However, for a production environment, ensure:
    # - Rate-limiting: Implement client-sided rate-limiting to prevent excessive API calls.
    # - HTTPS Enforcement: The underlying library should enforce HTTPS.
    # - Error Handling: Robust handling of network errors, timeouts, and rate limits.
    search = DuckDuckGoSearchRun()

    # 2) Build or load FAISS memory retriever
    memory_retriever = build_memory(config, logger)

    # 3) Wrap the retriever in a RetrievalQA chain
    # SECURITY NOTE: RetrievalQA can be sensitive if the 'llm' or 'retriever'
    # are misconfigured. Ensure:
    # - Context Window: LLM context never contains PII or secrets from retrieved docs.
    # - Prompt Injection: While RetrievalQA handles some aspects, custom prompts
    #   should be carefully constructed to resist prompt injection.
    fact_qa = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff", # "stuff" chain type puts all documents into one prompt.
                             # Ensure config.AGENT_RETRIEVER_K and document size don't exceed LLM context window.
        retriever=memory_retriever,
        return_source_documents=False, # Set to True for debugging; False for production to reduce data leakage.
    )

    # 4) Construct the list of Tools
    # SECURITY NOTE: Each Tool object MUST have a narrowly defined scope and
    # a clear input/output schema. Avoid "generic shell" tools.
    tools = [
        Tool(
            name="DuckDuckGo Search",
            func=search.run,
            description="Use this to look up live information. Input should be a concise search query."
        ),
        Tool(
            name="LocalFactSheet",
            func=lambda q: fact_qa.run(q), # Lambda for compatibility with Tool.func signature
            description="Answer detailed questions about Zira, its capabilities, and configuration from the local fact sheet. Input should be a question."
        ),
    ]

    # SECRET ROTATION / EXPIRATION AWARENESS:
    # If using external LLM services or embedding APIs that require direct API keys
    # beyond what LangChain handles internally via env vars (e.g., custom API clients),
    # ensure their usage here includes:
    # - Environment Variable Loading (already covered by Config)
    # - Mechanisms for regular key rotation (e.g., Kube secrets, HashiCorp Vault)
    # - Awareness of key expiration dates and handling of expired key errors.
    # (No direct code changes here as it's typically external to this file.)

    return tools

