import ollama
from step7_researcher import search
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL = "llama3"


def ask(query):
    logger.info(f"[PERGUNTA] {query}")

    start = time.time()

    chunks = search(query)

    if not chunks:
        logger.warning("Nenhum contexto encontrado")
        return "Não encontrei informações relevantes."

    context = "\n\n".join([c["content"] for c in chunks])

    prompt = f"""
Responda baseado apenas no contexto:

{context}

Pergunta: {query}
"""

    response = ollama.chat(model=MODEL, messages=[{"role": "user", "content": prompt}])

    duration = time.time() - start

    logger.info(f"[TEMPO] {duration:.2f}s")

    return response["message"]["content"]


if __name__ == "__main__":
    while True:
        q = input("Pergunta: ")
        print(ask(q))
