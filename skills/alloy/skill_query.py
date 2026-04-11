import logging
import sys
from pathlib import Path

# Adiciona a raiz da URB ao path para importar as ferramentas como pacote
URB_ROOT = "/home/debian/code/universal-rag-builder"
if URB_ROOT not in sys.path:
    sys.path.append(URB_ROOT)

from core.step7_researcher import DomainResearcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Singleton do pesquisador para evitar recarregar o modelo em cada chamada
_researcher = None

def get_researcher():
    global _researcher
    if _researcher is None:
        _researcher = DomainResearcher(domain="alloy")
    return _researcher

def alloy_rag_search(query: str, k: int = 4):
    """
    Ferramenta de busca semântica para o Alloy Engineer.
    """
    try:
        researcher = get_researcher()
        results = researcher.search(query, k=k)
        
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
