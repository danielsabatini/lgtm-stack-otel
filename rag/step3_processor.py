from markdownify import markdownify as md
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

INPUT_DIR = Path("rag/cleaned")
OUTPUT_DIR = Path("rag/processed")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    files = list(INPUT_DIR.glob("*.html"))
    if not files:
        logger.warning(f"Nenhum arquivo encontrado em {INPUT_DIR}")
        return

    logger.info(f"Convertendo {len(files)} arquivos para Markdown")

    processed = 0
    skipped = 0

    for file in files:
        try:
            logger.info(f"[PROCESSANDO] {file.name}")

            html = file.read_text(encoding="utf-8")
            original_size = len(html)

            markdown = md(html, heading_style="ATX")
            md_size = len(markdown)

            if not markdown.strip():
                logger.warning(f"[VAZIO] {file.name}")
                skipped += 1
                continue

            output_path = OUTPUT_DIR / f"{file.stem}.md"
            output_path.write_text(markdown, encoding="utf-8")

            logger.info(f"[OK] {file.name} | {original_size} → {md_size} chars")

            processed += 1

        except Exception as e:
            logger.error(f"[ERRO] {file.name} -> {e}")

    logger.info("========== RESUMO ==========")
    logger.info(f"Processados: {processed}")
    logger.info(f"Pulados: {skipped}")
    logger.info(f"Total: {len(files)}")


if __name__ == "__main__":
    main()