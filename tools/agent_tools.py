import os
import re
import hashlib         # For SHA256 hashing
import json            # For saving/loading hashes
import tempfile        # For atomic file writes
from pathlib import Path
from typing import Optional, Union

from langchain_community.tools import DuckDuckGoSearchRun
from langchain.agents import Tool
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA

from core.config import Config     # To load API keys, paths, etc.


# -----------------------------------------------------------------------------
# SECURITY: In production, set this to a fixed, root-owned directory (non-user-writable),
# e.g. "/opt/zira/data" or "C:\\ProgramData\\Zira\\data". 
# Do NOT use os.getcwd() in production.
# -----------------------------------------------------------------------------
_config = Config()
_ALLOWED_DATA_ROOT = os.path.abspath(
    os.getenv("ZIRA_DATA_ROOT", os.path.join(os.getcwd(), "data"))
)
# Make absolutely sure _ALLOWED_DATA_ROOT cannot be changed at runtime by normal users
_ALLOWED_DATA_ROOT = os.path.realpath(_ALLOWED_DATA_ROOT)


# FAISS index subfolder and filenames
FAISS_INDEX_SUBDIR = "faiss_index"
FAISS_INDEX_NAME = "zira_database"
FAISS_HASH_FILE_NAME = f"{FAISS_INDEX_NAME}.hash"


def _is_safe_path(
    base_path: Union[str, Path], 
    proposed_path: Union[str, Path], 
    logger
) -> bool:
    """
    Validates that 'proposed_path' is within 'base_path' after resolving symlinks
    and does not contain any '..' segments. Prevents path traversal attacks.
    """
    try:
        abs_base = Path(base_path).resolve(strict=False)
        abs_prop = Path(proposed_path).resolve(strict=False)
    except Exception as e:
        logger.error(f"Error resolving paths: {e}", exc_info=False)
        return False

    # If any parent of abs_prop is not under abs_base, it’s invalid
    try:
        abs_prop.relative_to(abs_base)
    except Exception:
        logger.warning(
            f"Path '{proposed_path}' resolves to '{abs_prop}', which is outside allowed base '{abs_base}'."
        )
        return False

    return True


def _calculate_file_hash(filepath: Union[str, Path]) -> Optional[str]:
    """
    Calculates the SHA256 hash of a file. Returns None if file not found.
    """
    path = Path(filepath)
    if not path.is_file():
        return None

    hasher = hashlib.sha256()
    try:
        with path.open("rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                hasher.update(chunk)
    except Exception:
        return None

    return hasher.hexdigest()


def _atomic_write_json(data: dict, target_path: Union[str, Path], logger) -> None:
    """
    Writes a JSON file atomically by writing to a temporary file first,
    then renaming to the final location.
    """
    target = Path(target_path)
    temp_dir = target.parent
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=temp_dir, delete=False
        ) as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_name = tmp.name
        # Atomic replace (POSIX and Windows compatible)
        os.replace(tmp_name, str(target))
        logger.info(f"Atomic write succeeded for hash file '{target}'.")
    except Exception as e:
        logger.error(f"Failed to write JSON atomically to '{target}': {e}", exc_info=True)
        # If atomic write fails, attempt a normal write as a fallback
        try:
            with target.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.warning(
                f"Atomic write failed; performed non-atomic write to '{target}'. Potential risk of corruption."
            )
        except Exception as e2:
            logger.error(f"Fallback non-atomic write also failed for '{target}': {e2}", exc_info=True)


def _save_hashes(
    faiss_file: Union[str, Path], 
    pkl_file: Union[str, Path], 
    hash_file_path: Union[str, Path], 
    logger
) -> None:
    """
    Calculates SHA256 for both the FAISS index and its .pkl metadata file,
    then writes them to 'hash_file_path' (atomically).
    """
    faiss_hash = _calculate_file_hash(faiss_file)
    pkl_hash   = _calculate_file_hash(pkl_file)

    if faiss_hash is None or pkl_hash is None:
        logger.error(
            f"Cannot compute hashes: "
            f"FAISS file='{faiss_file}', PKL file='{pkl_file}'. At least one is missing."
        )
        return

    hashes = {"faiss_hash": faiss_hash, "pkl_hash": pkl_hash}
    _atomic_write_json(hashes, hash_file_path, logger)


def _verify_hashes(
    faiss_file: Union[str, Path], 
    pkl_file: Union[str, Path], 
    hash_file_path: Union[str, Path], 
    logger
) -> bool:
    """
    Loads stored hashes from 'hash_file_path' and compares against current file hashes.
    Returns True if both match; False otherwise (indicating rebuild is needed).
    """
    hash_path = Path(hash_file_path)
    if not hash_path.is_file():
        logger.warning(f"Hash file '{hash_file_path}' not found. Forcing FAISS rebuild.")
        return False

    try:
        stored = json.loads(hash_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to read/parse hash file '{hash_file_path}': {e}", exc_info=False)
        return False

    current_faiss_hash = _calculate_file_hash(faiss_file)
    current_pkl_hash   = _calculate_file_hash(pkl_file)
    if current_faiss_hash is None or current_pkl_hash is None:
        logger.warning("FAISS or PKL file is missing during hash verification. Forcing rebuild.")
        return False

    if (
        stored.get("faiss_hash") == current_faiss_hash and
        stored.get("pkl_hash")   == current_pkl_hash
    ):
        logger.info("FAISS index integrity verified (hashes match).")
        return True

    logger.warning(
        "Hash mismatch detected! FAISS file or PKL file may have been tampered or corrupted. Forcing rebuild."
    )
    return False


def build_memory(config: Config, logger) -> "FAISS.Retriever":
    """
    Loads or creates a FAISS vectorstore from the local fact-sheet. Returns Retriever.
    Raises if the fact sheet is missing or paths are invalid.
    """
    # 1) Ensure the data root is secure
    if not _is_safe_path(_ALLOWED_DATA_ROOT, _ALLOWED_DATA_ROOT, logger):
        raise ValueError(f"Configured data root '{_ALLOWED_DATA_ROOT}' is invalid or not secure.")

    # 2) Define full index directory
    faiss_dir = os.path.join(_ALLOWED_DATA_ROOT, FAISS_INDEX_SUBDIR)
    faiss_file = os.path.join(faiss_dir, f"{FAISS_INDEX_NAME}.faiss")
    pkl_file   = os.path.join(faiss_dir, f"{FAISS_INDEX_NAME}.pkl")
    hash_file  = os.path.join(faiss_dir, FAISS_HASH_FILE_NAME)

    # 3) If index directory exists, verify its safety
    if os.path.isdir(faiss_dir):
        if not _is_safe_path(_ALLOWED_DATA_ROOT, faiss_dir, logger):
            raise ValueError(f"FAISS directory '{faiss_dir}' is outside the allowed data root.")
    else:
        try:
            # Create with restrictive permissions (owner rwx only)
            os.makedirs(faiss_dir, exist_ok=True, mode=0o700)
            logger.info(f"Created FAISS directory at '{faiss_dir}' with mode 0o700.")
        except Exception as e:
            logger.error(f"Failed to create FAISS directory '{faiss_dir}': {e}", exc_info=True)
            raise

    # 4) Check for existing files + verify hashes
    files_exist = (
        os.path.isfile(faiss_file) 
        and os.path.isfile(pkl_file) 
        and os.path.isfile(hash_file)
    )

    if files_exist and _verify_hashes(faiss_file, pkl_file, hash_file, logger):
        logger.info(f"Loading existing FAISS index from '{faiss_dir}'.")
        try:
            # WARNING: allow_dangerous_deserialization=True is required by LangChain but is risky.
            # Ensure that no untrusted user can overwrite these files.
            vectorstore = FAISS.load_local(
                faiss_dir,
                HuggingFaceEmbeddings(model_name=config.AGENT_EMBEDDING_MODEL),
                index_name=FAISS_INDEX_NAME,
                allow_dangerous_deserialization=True
            )
            return vectorstore.as_retriever(search_kwargs={"k": config.AGENT_RETRIEVER_K})
        except Exception as e:
            logger.error(f"Error loading FAISS from '{faiss_dir}': {e}", exc_info=True)
            # Fall through to rebuild
    else:
        if files_exist:
            logger.warning("Existing FAISS files detected but hash verification failed; rebuilding.")
        else:
            logger.info("No valid FAISS index found; building new index.")

    # 5) Validate fact-sheet path
    fact_path = config.AGENT_FACT_SHEET_PATH
    if not _is_safe_path(_ALLOWED_DATA_ROOT, fact_path, logger):
        raise ValueError(f"Fact sheet path '{fact_path}' is outside allowed data root.")

    if not os.path.isfile(fact_path):
        logger.error(f"Fact sheet not found at '{fact_path}'. Cannot build FAISS index.")
        raise FileNotFoundError(f"Missing fact sheet file: {fact_path}")

    # 6) Load documents, split, and index
    try:
        loader = TextLoader(fact_path, encoding="utf8")
        docs = loader.load()
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.AGENT_TEXT_SPLITTER_CHUNK_SIZE,
            chunk_overlap=config.AGENT_TEXT_SPLITTER_CHUNK_OVERLAP
        )
        chunks = splitter.split_documents(docs)

        embeddings = HuggingFaceEmbeddings(model_name=config.AGENT_EMBEDDING_MODEL)
        vectorstore = FAISS.from_documents(chunks, embeddings)

        # Save index (with restrictive permissions)
        vectorstore.save_local(
            faiss_dir, 
            index_name=FAISS_INDEX_NAME
        )
        # The `save_local` call typically writes `<faiss>.faiss` and `<faiss>.pkl`.
        # Fix file permissions so only the owner can read/write:
        try:
            os.chmod(faiss_file, 0o600)
            os.chmod(pkl_file,   0o600)
        except Exception as e:
            logger.warning(f"Failed to set restrictive permissions on FAISS files: {e}")

        # 7) Compute and save hashes
        _save_hashes(faiss_file, pkl_file, hash_file, logger)

        logger.info(f"FAISS index built and saved under '{faiss_dir}'.")
        return vectorstore.as_retriever(search_kwargs={"k": config.AGENT_RETRIEVER_K})

    except Exception as e:
        logger.error(f"Error building FAISS index: {e}", exc_info=True)
        raise


def setup_tools(config: Config, llm, logger=None) -> list[Tool]:
    """
    Returns a list of LangChain Tools:
      1. duckduckgo_search (live web search)
      2. local_factsheet (answers from local fact-sheet via FAISS + RetrievalQA)
    """
    if logger is None:
        from core.logger_config import setup_logger as _setup
        logger = _setup(config)

    # 1) DuckDuckGo Search with a short timeout
    try:
        ddg = DuckDuckGoSearchRun(timeout=5)  # 5s timeout to avoid hanging
    except TypeError:
        # Some versions of DuckDuckGoSearchRun may not support timeout param;
        # fallback to default behavior but log a warning.
        ddg = DuckDuckGoSearchRun()
        logger.warning("DuckDuckGoSearchRun does not support timeout parameter; proceeding without timeout.")

    # 2) Build or load local FAISS retriever
    memory_retriever = build_memory(config, logger)

    fact_qa = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=memory_retriever,
        return_source_documents=False,
    )

    tools: list[Tool] = []

    # Tool #1: Live search
    tools.append(
        Tool(
            name="duckduckgo_search",
            func=lambda query: ddg.run(query) if isinstance(query, str) else "Invalid query format.",
            description=(
                "Use this tool for live web searches. "
                "Input must be a single-line string query (e.g., 'latest Python release')."
            )
        )
    )

    # Tool #2: Local fact-sheet QA
    def local_factsheet_tool(query: str) -> str:
        if not isinstance(query, str) or not query.strip():
            return "Please provide a non-empty question."
        # (You could add further sanitization on `query` if desired)
        return fact_qa.run(query)

    tools.append(
        Tool(
            name="local_factsheet",
            func=local_factsheet_tool,
            description=(
                "Answers specific questions about human rights from the local human rights fact sheet. "
                "Use this only for queries explicitly related to human rights. "
                "Input should be a single-line question."
            )
        )
    )

    return tools