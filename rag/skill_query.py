import logging
from typing import List, Dict

from step7_researcher import search

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==============================
# TOOL PARA SKILL (ANTIGRAVITY)
# ==============================
def alloy_rag_search(query: str, k: int = 4) -> List[Dict]:
    """
    Tool de busca semântica para documentação do Grafana Alloy.

    Args:
        query (str): pergunta do usuário
        k (int): número de resultados

    Returns:
        List[Dict]: lista de chunks relevantes
    """

    try:
        logger.info(f"[SKILL] Query recebida: {query}")

        results = search(query, k)

        if not results:
            logger.warning("[SKILL] Nenhum resultado encontrado")
            return []

        formatted = []

        for r in results:
            formatted.append(
                {
                    "content": r["content"],
                    "source": r["metadata"].get("source", "unknown"),
                    "chunk_id": r["metadata"].get("chunk"),
                    "length": r["metadata"].get("length", len(r["content"])),
                }
            )

        logger.info(f"[SKILL] Retornando {len(formatted)} chunks")

        return formatted

    except Exception as e:
        logger.error(f"[SKILL][ERRO] {e}")
        return []
