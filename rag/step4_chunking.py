import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

INPUT_DIR = Path("rag/processed")
OUTPUT_FILE = Path("rag/index/chunks.json")


def chunk_markdown(md_text):
    chunks = []
    current = ""

    for line in md_text.split("\n"):
        if line.startswith("#"):
            if current:
                chunks.append(current.strip())
            current = line
        else:
            current += "\n" + line

    if current:
        chunks.append(current.strip())

    return chunks


def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    files = list(INPUT_DIR.glob("*.md"))
    if not files:
        logger.warning(f"Nenhum markdown encontrado em {INPUT_DIR}")
        return

    logger.info(f"Gerando chunks de {len(files)} arquivos")

    all_chunks = []
    total_chunks = 0

    for file in files:
        try:
            logger.info(f"[PROCESSANDO] {file.name}")

            content = file.read_text(encoding="utf-8")
            chunks = chunk_markdown(content)

            valid_chunks = 0

            for i, chunk in enumerate(chunks):
                if len(chunk.strip()) < 100:
                    continue

                all_chunks.append({
                    "id": f"{file.stem}_{i}",
                    "content": chunk,
                    "metadata": {
                        "source": file.name,
                        "chunk": i,
                        "length": len(chunk)
                    }
                })
                valid_chunks += 1

            logger.info(f"[OK] {file.name} → {valid_chunks} chunks válidos")
            total_chunks += valid_chunks

        except Exception as e:
            logger.error(f"[ERRO] {file.name} -> {e}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    logger.info("========== RESUMO ==========")
    logger.info(f"Total de chunks: {total_chunks}")
    logger.info(f"Arquivo gerado: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()