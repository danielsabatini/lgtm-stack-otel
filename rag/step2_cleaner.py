from bs4 import BeautifulSoup
from pathlib import Path
import logging

# ==============================
# LOGGING
# ==============================
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ==============================
# CONFIG
# ==============================
INPUT_DIR = Path("rag/crawled")
OUTPUT_DIR = Path("rag/cleaned")


# ==============================
# CLEAN HTML
# ==============================
def clean_html(html):
    soup = BeautifulSoup(html, "html.parser")

    # remover ruído
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    main = soup.find("main") or soup.find("article") or soup

    return main.prettify()


# ==============================
# MAIN
# ==============================
def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    files = list(INPUT_DIR.glob("*.html"))

    if not files:
        logger.warning(f"Nenhum arquivo encontrado em {INPUT_DIR}")
        return

    logger.info(f"Iniciando limpeza de {len(files)} arquivos")

    processed = 0
    skipped = 0

    for file in files:
        try:
            logger.info(f"[PROCESSANDO] {file.name}")

            html = file.read_text(encoding="utf-8")

            original_size = len(html)

            cleaned = clean_html(html)

            cleaned_size = len(cleaned)

            if not cleaned.strip():
                logger.warning(f"[VAZIO] {file.name} após limpeza")
                skipped += 1
                continue

            output_path = OUTPUT_DIR / file.name

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(cleaned)

            logger.info(f"[OK] {file.name} | {original_size} → {cleaned_size} chars")

            processed += 1

        except Exception as e:
            logger.error(f"[ERRO] {file.name} -> {e}")

    logger.info("========== RESUMO ==========")
    logger.info(f"Processados: {processed}")
    logger.info(f"Pulados: {skipped}")
    logger.info(f"Total: {len(files)}")


# ==============================
# ENTRYPOINT
# ==============================
if __name__ == "__main__":
    main()
