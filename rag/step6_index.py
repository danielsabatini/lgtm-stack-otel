import faiss
import numpy as np
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

INPUT = Path("rag/index/embeddings.npy")
OUTPUT = Path("rag/index/faiss.index")


def main():
    if not INPUT.exists():
        logger.error(f"Embeddings não encontrados: {INPUT}")
        return

    vectors = np.load(INPUT).astype("float32")

    logger.info(f"Carregados {vectors.shape[0]} vetores (dim={vectors.shape[1]})")

    index = faiss.IndexFlatL2(vectors.shape[1])
    index.add(vectors)

    faiss.write_index(index, str(OUTPUT))

    logger.info("========== RESUMO ==========")
    logger.info(f"Indexados: {index.ntotal} vetores")
    logger.info(f"Índice salvo em: {OUTPUT}")


if __name__ == "__main__":
    main()