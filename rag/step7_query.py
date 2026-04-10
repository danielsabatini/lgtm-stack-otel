import faiss
import json
import numpy as np
from sentence_transformers import SentenceTransformer
import logging
from pathlib import Path

# ==============================
# LOGGING
# ==============================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ==============================
# PATHS ROBUSTOS (FIX DEFINITIVO)
# ==============================
BASE_DIR = Path(__file__).resolve().parent

INDEX_PATH = BASE_DIR / "rag/index/faiss.index"
META_PATH = BASE_DIR / "rag/index/chunks.json"

# ==============================
# VALIDAÇÃO DE ARQUIVOS
# ==============================
if not INDEX_PATH.exists():
    raise FileNotFoundError(f"FAISS index não encontrado: {INDEX_PATH}")

if not META_PATH.exists():
    raise FileNotFoundError(f"Metadata não encontrada: {META_PATH}")

logger.info(f"[LOAD] Index: {INDEX_PATH}")
logger.info(f"[LOAD] Metadata: {META_PATH}")

# ==============================
# LOAD MODELO E INDEX
# ==============================
model = SentenceTransformer("all-MiniLM-L6-v2")

index = faiss.read_index(str(INDEX_PATH))

with open(META_PATH, encoding="utf-8") as f:
    metadata = json.load(f)

logger.info(f"[READY] Index carregado com {index.ntotal} vetores")


# ==============================
# SEARCH
# ==============================
def search(query: str, k: int = 4):
    """
    Busca semântica no índice FAISS

    Args:
        query (str): consulta
        k (int): número de resultados

    Returns:
        list: chunks relevantes
    """

    logger.info(f"[QUERY] {query}")

    try:
        vec = model.encode([query]).astype("float32")

        distances, indices = index.search(vec, k)

        results = []
        for i in indices[0]:
            if i != -1:
                results.append(metadata[i])

        logger.info(f"[RESULTADOS] {len(results)} encontrados")

        return results

    except Exception as e:
        logger.error(f"[ERRO] Falha na busca: {e}")
        return []        