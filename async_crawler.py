import asyncio
import json
import re
import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8",
}

def clean_price(price_str: str) -> float:
    if not price_str:
        return 0.0
    cleaned = re.sub(r"[^\d,\.]", "", price_str).replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

async def scrape_site(client: httpx.AsyncClient, site_key: str, conf: dict, query: str, max_price: float):
    formatted_query = query.replace(" ", "+")
    url = conf["search_url"].format(query=formatted_query)
    results = []

    try:
        res = await client.get(url, headers=HEADERS, timeout=10.0, follow_redirects=True)
        if res.status_code != 200:
            return results

        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.select(conf["item_selector"])

        for it in items:
            title_node = it.select_one(conf["title_selector"])
            price_node = it.select_one(conf["price_selector"])
            link_node = it.select_one(conf["link_selector"])

            if not title_node or not price_node:
                continue

            title = title_node.get_text(strip=True)
            price = clean_price(price_node.get_text(strip=True))

            raw_link = link_node.get("href", "") if link_node else ""
            if not raw_link:
                continue

            full_url = f"{conf['base_url']}{raw_link}" if raw_link.startswith("/") else raw_link

            if max_price and price > max_price:
                continue

            if price > 0:
                results.append({
                    "platform": conf["name"],
                    "title": title,
                    "price": price,
                    "url": full_url
                })
    except Exception:
        pass

    return results

async def search_all_sites(query: str, max_price: float = None):
    with open("sites_config.json", "r", encoding="utf-8") as f:
        config_data = json.load(f)

    semaphore = asyncio.Semaphore(5)

    async def sem_task(client, k, c):
        async with semaphore:
            return await scrape_site(client, k, c, query, max_price)

    async with httpx.AsyncClient(verify=False) as client:
        tasks = [sem_task(client, k, c) for k, c in config_data.items()]
        gathered = await asyncio.gather(*tasks)

    flat = [item for sub in gathered for item in sub]
    flat.sort(key=lambda x: x["price"])
    return flat
