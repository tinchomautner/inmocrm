import re
import json
import html
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-UY,es;q=0.9,en;q=0.8",
}


def _meta(soup, *names):
    for name in names:
        tag = soup.find("meta", property=name) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


def _iter_jsonld(soup):
    for tag in soup.find_all("script", type="application/ld+json"):
        raw = tag.string or tag.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if isinstance(data, list):
            for item in data:
                yield item
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                for item in data["@graph"]:
                    yield item
            yield data


def _from_jsonld(soup):
    out = {}
    for item in _iter_jsonld(soup):
        if not isinstance(item, dict):
            continue
        offers = item.get("offers")
        if isinstance(offers, dict):
            price = offers.get("price")
            cur = offers.get("priceCurrency", "")
            if price and not out.get("price"):
                out["price"] = f"{cur} {price}".strip()
        if item.get("name") and not out.get("title"):
            out["title"] = item["name"]
        img = item.get("image")
        if img and not out.get("image"):
            if isinstance(img, list):
                img = img[0]
            if isinstance(img, dict):
                img = img.get("url")
            if isinstance(img, str):
                out["image"] = img
    return out


def _is_junk_title(t):
    """Detecta títulos inservibles: vacíos, muy cortos, o placeholders tipo 'Ref: ,'."""
    if not t:
        return True
    s = t.strip()
    if len(s) < 5:
        return True
    if re.fullmatch(r"(?:ref\.?\s*:?\s*[,;.\-/]*\s*)+", s, re.IGNORECASE):
        return True
    return False


def _best_title(soup):
    # h1 más largo de los primeros (evita un h1 chico de logo/nav)
    h1 = None
    h1s = [h.get_text(" ", strip=True) for h in soup.find_all("h1", limit=5)]
    h1s = [h for h in h1s if h]
    if h1s:
        h1 = max(h1s, key=len)
    candidates = [
        _meta(soup, "og:title", "twitter:title"),
        h1,
        (soup.title.string.strip() if soup.title and soup.title.string else None),
    ]
    for c in candidates:
        if not _is_junk_title(c):
            return c
    for c in candidates:  # último recurso: lo que haya
        if c and c.strip():
            return c
    return None


def _clean_num(text):
    return re.sub(r"[^\d]", "", text or "")


def _extract_price(text):
    # USD 185.000 / U$S 185000 / $ 185.000
    m = re.search(r"(U\$?S|USD|US\$|\$U?)\s?([\d.,]{4,})", text, re.IGNORECASE)
    if m:
        num = _clean_num(m.group(2))
        if num:
            cur = "USD" if "U" in m.group(1).upper() and "S" in m.group(1).upper() else "$"
            return f"{cur} {int(num):,}".replace(",", ".")
    return None


def _extract_bedrooms(text):
    m = re.search(r"(\d+)\s*(?:dormitorio|dorm\.?|habitaci[oó]n|cuarto)", text, re.IGNORECASE)
    return m.group(1) if m else None


def _extract_area(text):
    m = re.search(r"(\d{2,4})\s*(?:m2|m²|mts?2?|metros)", text, re.IGNORECASE)
    return f"{m.group(1)} m²" if m else None


def scrape(url):
    """Return a dict with best-effort property data. Never raises."""
    result = {
        "url": url,
        "title": None,
        "price": None,
        "image": None,
        "bedrooms": None,
        "area": None,
        "location": None,
        "description": None,
        "error": None,
    }
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        result["error"] = f"No se pudo acceder al link: {e}"
        return result

    soup = BeautifulSoup(resp.text, "lxml")

    result["title"] = _best_title(soup)
    result["image"] = _meta(soup, "og:image", "twitter:image")
    result["description"] = _meta(soup, "og:description", "description", "twitter:description")
    result["price"] = _meta(soup, "product:price:amount", "og:price:amount")
    if result["price"]:
        cur = _meta(soup, "product:price:currency", "og:price:currency") or ""
        result["price"] = f"{cur} {result['price']}".strip()

    ld = _from_jsonld(soup)
    for k in ("title", "price", "image"):
        if not result[k] and ld.get(k):
            result[k] = ld[k]

    # Build a text blob for regex fallbacks
    blob = " ".join(
        filter(None, [result["title"], result["description"], soup.get_text(" ", strip=True)[:4000]])
    )
    blob = html.unescape(blob)

    if not result["price"] or not re.search(r"\d", result["price"]):
        result["price"] = _extract_price(blob) or result["price"]
    result["bedrooms"] = _extract_bedrooms(blob)
    result["area"] = _extract_area(blob)

    # Location: try og:locality / address-ish from title
    result["location"] = _meta(soup, "og:locality", "og:region", "geo.placename")

    if result["title"]:
        result["title"] = html.unescape(result["title"])[:200]
    if result["description"]:
        result["description"] = html.unescape(result["description"])[:400]

    return result
