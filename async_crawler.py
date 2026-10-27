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

async def scrape_single_site(client: httpx.AsyncClient, site_key: str, config: dict, query: str, max_price: float = None):
    """It scrapes a single site based on the provided configuration and query."""
    formatted_query = query.replace(" ", "+")
    url = config["search_url"].format(query=formatted_query)
    products = []

    try:
        response = await client.get(url, headers=HEADERS, timeout=12.0, follow_redirects=True)
        if response.status_code != 200:
            return products

        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.select(config["item_selector"])

        for item in items:
            title_el = item.select_one(config["title_selector"])
            price_el = item.select_one(config["price_selector"])
            link_el = item.select_one(config["link_selector"])

            if not title_el or not price_el:
                continue

            title = title_el.get_text(strip=True)
            price = clean_price(price_el.get_text(strip=True))

            raw_link = link_el.get("href", "") if link_el else ""
            if raw_link.startswith("/"):
                product_url = f"{config['base_url']}{raw_link}"
            else:
                product_url = raw_link

            if max_price and price > max_price:
                continue

            if price > 0:
                products.append({
                    "platform": config["name"],
                    "title": title,
                    "price": price,
                    "url": product_url
                })

    except Exception as e:
        # Log the error for debugging purposes
        pass

    return products

async def search_all_sites(query: str, max_price: float = None):
    with open("sites_config.json", "r", encoding="utf-8") as f:
        sites_config = json.load(f)

    # Aynı anda en fazla 8 siteye paralel istek atarak güvenli tarama yapıyoruz
    semaphore = asyncio.Semaphore(8)

    async def limited_scrape(client, site_key, config):
        async with semaphore:
            return await scrape_single_site(client, site_key, config, query, max_price)

    async with httpx.AsyncClient() as client:
        tasks = [
            limited_scrape(client, site_key, config)
            for site_key, config in sites_config.items()
        ]
        all_results = await asyncio.gather(*tasks)

    flat_results = [item for sublist in all_results for item in sublist]
    flat_results.sort(key=lambda x: x["price"])
    return flat_results

if __name__ == "__main__":
    search_term = "kurtka the north face"
    budget = 400.0

    print(f"🚀 '{search_term}' searching all sites (Budget: {budget} PLN)...")
    results = asyncio.run(search_all_sites(search_term, budget))

    print(f"\n✅ Total {len(results)} suitable products found!\n")
    for idx, p in enumerate(results[:10], 1):
        print(f"{idx}. [{p['platform']}] {p['title']}")
        print(f"   Price: {p['price']} PLN")
        print(f"   Link: {p['url']}\n")