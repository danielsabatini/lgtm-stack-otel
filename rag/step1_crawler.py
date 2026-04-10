import httpx
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pathlib import Path
import hashlib
import logging

# ==============================
# CONFIG
# ==============================
BASE_DOMAIN = "grafana.com"
START_URL = "https://grafana.com/docs/grafana-cloud/send-data/alloy/"
MAX_DEPTH = 2
MAX_PAGES = 1000
OUTPUT_DIR = Path("rag/docs")

CONCURRENCY = 5
TIMEOUT = 20
RETRIES = 3

# ==============================
# LOGGING
# ==============================
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ==============================
# ESTADO
# ==============================
visited = set()
queued = set()


# ==============================
# UTILS
# ==============================
def normalize_url(url: str) -> str:
    parsed = urlparse(url)

    # remove query + fragment
    path = parsed.path.rstrip("/")

    return f"{parsed.scheme}://{parsed.netloc}{path}"


def generate_filename(url: str) -> str:
    parsed = urlparse(url)
    base = parsed.path.strip("/").replace("/", "_") or "index"

    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

    return f"{base}_{url_hash}.html"


def is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return BASE_DOMAIN in parsed.netloc


# ==============================
# HTTP FETCH
# ==============================
async def fetch(client, url):
    for attempt in range(RETRIES):
        try:
            response = await client.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.warning(f"[retry {attempt+1}] {url} -> {e}")
            await asyncio.sleep(2 ** attempt)

    logger.error(f"[FAIL] {url}")
    return None


# ==============================
# LINK EXTRACTION
# ==============================
def extract_links(html: str, base_url: str):
    soup = BeautifulSoup(html, "html.parser")
    links = set()

    for tag in soup.find_all("a", href=True):
        href = urljoin(base_url, tag["href"])
        href = normalize_url(href)

        if is_valid_url(href):
            links.add(href)

    return links


# ==============================
# PROCESS SINGLE PAGE
# ==============================
async def process_url(client, url, depth, queue):
    global visited

    if url in visited:
        return

    visited.add(url)
    logger.info(f"[{depth}] {url}")

    html = await fetch(client, url)
    if not html:
        return

    # salvar arquivo
    filename = generate_filename(url)
    filepath = OUTPUT_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    # extrair links
    if depth < MAX_DEPTH:
        links = extract_links(html, url)

        for link in links:
            if link not in visited and link not in queued:
                queue.append((link, depth + 1))
                queued.add(link)


# ==============================
# MAIN CRAWLER
# ==============================
async def crawl(start_url):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    queue = [(normalize_url(start_url), 0)]
    queued.add(normalize_url(start_url))

    semaphore = asyncio.Semaphore(CONCURRENCY)

    async with httpx.AsyncClient(
        headers={"User-Agent": "RAG-Crawler/1.0"},
        follow_redirects=True
    ) as client:

        async def worker():
            while queue:
                if len(visited) >= MAX_PAGES:
                    logger.warning("Limite de páginas atingido")
                    return

                url, depth = queue.pop(0)

                async with semaphore:
                    await process_url(client, url, depth, queue)

        workers = [asyncio.create_task(worker()) for _ in range(CONCURRENCY)]
        await asyncio.gather(*workers)


# ==============================
# ENTRYPOINT
# ==============================
if __name__ == "__main__":
    asyncio.run(crawl(START_URL))