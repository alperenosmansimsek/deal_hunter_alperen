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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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

async def scrape_site_query(client: httpx.AsyncClient, site_key: str, conf: dict, query: str, max_price: float, sizes: list, colors: list):
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

            # 1. Bütçe Filtresi
            if max_price and price > max_price:
                continue

            title_lower = title.lower()

            # 2. Çoklu Renk Filtresi (Belirtilmişse en az biri geçmeli)
            if colors:
                if not any(color.lower() in title_lower for color in colors):
                    pass # Bazı siteler başlıkta renk vermez, esnek tutulabilir

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

async def search_all_sites_multi(keyword: str, brands: list, gender: str, sizes: list, colors: list, max_price: float):
    with open("sites_config.json", "r", encoding="utf-8") as f:
        config_data = json.load(f)

    # Aranacak sorgu kalıplarını inşa et
    # Kullanıcı 3 marka yazdıysa her marka için ayrı paralel arama açılır
    search_queries = []
    if brands:
        for b in brands:
            q = f"{keyword} {b} {gender}".strip()
            search_queries.append(q)
    else:
        q = f"{keyword} {gender}".strip()
        search_queries.append(q)

    semaphore = asyncio.Semaphore(8)

    async def sem_task(client, site_key, conf, q):
        async with semaphore:
            return await scrape_site_query(client, site_key, conf, q, max_price, sizes, colors)

    async with httpx.AsyncClient(verify=False) as client:
        tasks = []
        for q in search_queries:
            for k, conf in config_data.items():
                tasks.append(sem_task(client, k, conf, q))
        
        gathered = await asyncio.gather(*tasks)

    # Sonuçları düzleştir ve tekilleştir (Aynı URL iki kez gelmesin)
    seen_urls = set()
    unique_results = []
    for sub in gathered:
        for item in sub:
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                unique_results.append(item)

    unique_results.sort(key=lambda x: x["price"])
    return unique_results
