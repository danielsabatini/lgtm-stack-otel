import json
import numpy as np
from sentence_transformers import SentenceTransformer
from pathlib import Path
import logging
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

INPUT = Path("rag/index/chunks.json")
OUTPUT = Path("rag/index/embeddings.npy")
MODEL_NAME = "all-MiniLM-L6-v2"


def main():
    if not INPUT.exists():
        logger.error(f"Arquivo não encontrado: {INPUT}")
        return

    chunks = json.load(open(INPUT))
    texts = [c["content"] for c in chunks]

    logger.info(f"Gerando embeddings para {len(texts)} chunks")

    start = time.time()

    model = SentenceTransformer(MODEL_NAME)
    embeddings = model.encode(texts, show_progress_bar=True)

    np.save(OUTPUT, embeddings)

    duration = time.time() - start

    logger.info("========== RESUMO ==========")
    logger.info(f"Embeddings gerados: {len(embeddings)}")
    logger.info(f"Dimensão: {len(embeddings[0])}")
    logger.info(f"Tempo: {duration:.2f}s")
    logger.info(f"Salvo em: {OUTPUT}")


if __name__ == "__main__":
    main()