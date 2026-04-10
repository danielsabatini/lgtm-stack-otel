import asyncio
import httpx
import argparse
import hashlib
import os
from datetime import datetime
from urllib.parse import urlparse


# -----------------------------
# CONFIG
# -----------------------------
DEFAULT_CONCURRENCY = 5
DEFAULT_TIMEOUT = 30


# -----------------------------
# UTILS
# -----------------------------
def generate_filename(url: str) -> str:
    parsed = urlparse(url)

    base = (parsed.netloc + parsed.path).replace("/", "_")
    base = base.strip("_") or "index"

    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")

    return f"{base}_{timestamp}_{url_hash}.html"


# -----------------------------
# DOWNLOAD TASK
# -----------------------------
async def fetch_and_save(client, url, output_dir, semaphore):
    async with semaphore:
        try:
            print(f"[INFO] Baixando: {url}")

            response = await client.get(url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()

            filename = generate_filename(url)
            filepath = os.path.join(output_dir, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(response.text)

            print(f"[OK] Salvo em: {filepath}")

        except Exception as e:
            print(f"[ERRO] {url} -> {e}")


# -----------------------------
# MAIN ASYNC
# -----------------------------
async def download_all(urls, output_dir, concurrency):
    os.makedirs(output_dir, exist_ok=True)

    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = [fetch_and_save(client, url, output_dir, semaphore) for url in urls]

        await asyncio.gather(*tasks)


# -----------------------------
# CLI ENTRYPOINT
# -----------------------------
def main():
    parser = argparse.ArgumentParser(description="Async downloader para RAG")

    parser.add_argument("urls", nargs="+", help="Lista de URLs")

    parser.add_argument("--output", default="docs", help="Diretório de saída")

    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help="Número de downloads simultâneos",
    )

    args = parser.parse_args()

    asyncio.run(download_all(args.urls, args.output, args.concurrency))


if __name__ == "__main__":
    main()
