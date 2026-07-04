import re
import json
import html
import requests
from bs4 import BeautifulSoup

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
# Crawler social: algunos sitios (ej. Mercado Libre) sólo sirven la página completa
# (con precio) a los bots de previsualización tipo WhatsApp/Facebook.
SOCIAL_UA = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"


def _get(url, ua):
    return requests.get(
        url, headers={"User-Agent": ua, "Accept-Language": "es-UY,es;q=0.9,en;q=0.8"}, timeout=15
    )


# ---------- helpers ----------

def _meta(soup, *names):
    for name in names:
        tag = soup.find("meta", property=name) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


def _clean_num(text):
    return re.sub(r"[^\d]", "", text or "")


def _thousands(n):
    try:
        return f"{int(n):,}".replace(",", ".")
    except Exception:
        return str(n)


def _norm_currency(cur):
    c = (cur or "").upper()
    if "USD" in c or "U$S" in c or "US$" in c or "U$" in c or "DOLAR" in c or "DÓLAR" in c:
        return "USD"
    if "UYU" in c or c in ("$", "$U"):
        return "$"
    return c.strip() or ""


def _fmt_price(amount, currency="USD"):
    num = _clean_num(str(amount))
    if not num:
        return None
    cur = _norm_currency(currency) or "USD"
    return f"{cur} {_thousands(num)}".strip()


# ---------- JSON-LD ----------

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


def _price_from_offers(offers):
    """Soporta Offer (price) y AggregateOffer (lowPrice/highPrice). Devuelve texto formateado."""
    if not isinstance(offers, dict):
        if isinstance(offers, list) and offers:
            offers = offers[0]
        else:
            return None
    cur = offers.get("priceCurrency", "USD")
    if offers.get("price"):
        return _fmt_price(offers["price"], cur)
    low, high = offers.get("lowPrice"), offers.get("highPrice")
    if low and high and _clean_num(str(low)) != _clean_num(str(high)):
        return f"{_norm_currency(cur) or 'USD'} {_thousands(_clean_num(str(low)))} - {_thousands(_clean_num(str(high)))}"
    if low:
        return "Desde " + (_fmt_price(low, cur) or "")
    if high:
        return _fmt_price(high, cur)
    return None


def _from_jsonld(soup):
    out = {}
    for item in _iter_jsonld(soup):
        if not isinstance(item, dict):
            continue
        if not out.get("price") and item.get("offers"):
            p = _price_from_offers(item["offers"])
            if p:
                out["price"] = p
        if not out.get("title") and item.get("name"):
            out["title"] = str(item["name"]).strip()
        if not out.get("image") and item.get("image"):
            img = item["image"]
            if isinstance(img, list):
                img = img[0] if img else None
            if isinstance(img, dict):
                img = img.get("url")
            if isinstance(img, str):
                out["image"] = img
    return out


# ---------- título ----------

def _trim(text, max_len, prefer_seps):
    """Recorta texto a max_len cortando idealmente en un separador limpio."""
    if not text:
        return None
    t = text.strip()
    if len(t) <= max_len:
        return t
    cut = t[:max_len]
    for sep in prefer_seps:
        i = cut.rfind(sep)
        if i > max_len * 0.5:
            return cut[:i].rstrip(" .,-·|") + ("…" if sep == " " else "")
    i = cut.rfind(" ")
    if i > max_len * 0.55:
        return cut[:i].rstrip() + "…"
    return cut.rstrip() + "…"


def _short_title(t):
    return _trim(t, 75, [" · ", " | ", " - ", "Ref ", ". "])


def _short_desc(d):
    return _trim(d, 180, [". ", ".\n", "! ", "? ", " · "])


# Frases de páginas anti-bot / interstitials (ej. Mercado Libre) que NO son títulos reales.
_JUNK_TITLE_PHRASES = (
    "por seguridad", "completá este paso", "completa este paso", "antes de continuar",
    "verificá que sos", "verifica que eres", "no soy un robot", "are you a robot",
    "acceso denegado", "access denied", "just a moment", "un momento",
)

# Títulos genéricos (nombre del sitio) que aparecen cuando no se pudo leer el aviso real.
_GENERIC_TITLES = {
    "mercado libre", "mercadolibre", "golf inmobiliaria", "infocasas",
    "casas y +", "casas y mas", "inicio", "home",
}


def _is_junk_title(t, site_name=None):
    if not t:
        return True
    s = t.strip()
    if len(s) < 5:
        return True
    low = s.lower()
    if low in _GENERIC_TITLES:
        return True
    if any(ph in low for ph in _JUNK_TITLE_PHRASES):
        return True
    if re.fullmatch(r"(?:ref\.?\s*:?\s*[,;.\-/]*\s*)+", s, re.IGNORECASE):
        return True
    if site_name and low == site_name.strip().lower():
        return True
    return False


def _best_title(soup, ld):
    site_name = _meta(soup, "og:site_name")
    h1 = None
    h1s = [h.get_text(" ", strip=True) for h in soup.find_all("h1", limit=5)]
    h1s = [h for h in h1s if h]
    if h1s:
        h1 = max(h1s, key=len)
    candidates = [
        _meta(soup, "og:title", "twitter:title"),
        ld.get("title"),
        h1,
        (soup.title.string.strip() if soup.title and soup.title.string else None),
    ]
    for c in candidates:
        if not _is_junk_title(c, site_name):
            return c
    for c in candidates:
        if c and c.strip():
            return c
    return None


# ---------- imagen ----------

def _is_logo(u):
    u = (u or "").lower()
    return any(k in u for k in ("logo", "placeholder", "/icon", "favicon", "sprite"))


def _best_image(soup, ld):
    og = _meta(soup, "og:image", "twitter:image")
    if og and not _is_logo(og):
        return og
    if ld.get("image") and not _is_logo(ld["image"]):
        return ld["image"]
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy") or img.get("data-original") or ""
        if src.startswith("http") and not _is_logo(src) and not src.lower().endswith(".svg"):
            return src
    return og or ld.get("image")


# ---------- precio desde texto ----------

def _money_matches(text):
    out = []
    for m in re.finditer(r"(U\$?S|USD|US\$|\$U?S?|\$)\s?([\d][\d.,]{2,})", text, re.IGNORECASE):
        cur_raw = m.group(1).upper()
        num = _clean_num(m.group(2))
        if not num:
            continue
        is_usd = "U" in cur_raw or "USD" in cur_raw  # U$S / US$ / USD / $U
        out.append((is_usd, int(num)))
    return out


def _extract_price(text):
    # Primer monto plausible (el precio principal suele ser el primero del aviso).
    # Se prioriza USD; los montos chicos (precio/m², expensas) quedan filtrados por el piso.
    matches = _money_matches(text)
    for is_usd, v in matches:
        if is_usd and 1000 <= v <= 100_000_000:
            return "USD " + _thousands(v)
    for is_usd, v in matches:
        if not is_usd and 10000 <= v <= 10_000_000_000:
            return "$ " + _thousands(v)
    return None


def _extract_expenses(text):
    """Detecta gastos comunes en cualquier orden:
       'Gastos comunes: $ 8.500'  /  'G.C. U$S 200'  /  '$18.000 Gastos comunes'  /  'sin gastos comunes'."""
    AMT = r"((?:U\$?S|USD|US\$|\$U?S?|\$)\s?[\d][\d.,]{1,})"
    # Patrón 1: label antes del valor
    m = re.search(rf"(?:gastos?\s+comun\w*|g\.?\s?c\.?)\s*(?:aprox\w*)?\s*:?\s*{AMT}", text, re.IGNORECASE)
    # Patrón 2: valor antes del label (caso casasymas)
    if not m:
        m = re.search(rf"{AMT}\s*(?:de\s*)?gastos?\s+comun", text, re.IGNORECASE)
    if m:
        raw = m.group(1)
        num = _clean_num(raw)
        # Piso de valor: evita basura tipo "$ 9" por separadores raros (espacios de miles, etc.)
        if num and int(num) >= 100:
            cur = "USD" if re.search(r"U", raw, re.IGNORECASE) and re.search(r"S", raw, re.IGNORECASE) else "$"
            return f"{cur} {_thousands(num)}"
    if re.search(r"sin\s+gastos?\s+comun\w*", text, re.IGNORECASE):
        return "Sin gastos comunes"
    return None


def _extract_bedrooms(text):
    m = re.search(r"(\d+)\s*(?:dormitorio|dorm\.?|habitaci[oó]n|cuarto)", text, re.IGNORECASE)
    return m.group(1) if m else None


def _extract_area(text):
    m = re.search(r"(\d{2,4})\s*(?:m2|m²|mts?2?|metros)", text, re.IGNORECASE)
    return f"{m.group(1)} m²" if m else None


# ---------- sitios con API propia (Tokko / GOLF) ----------

def _int(v):
    try:
        return int(float(v))
    except Exception:
        return 0


def _scrape_golf(url):
    """inmobiliariagolf.com.uy es una web JS (backend Tokko). Leemos su API interna."""
    m = re.search(r"[?&]id=(\d+)", url)
    if not m:
        return None
    pid = m.group(1)
    try:
        r = requests.post(
            "https://www.inmobiliariagolf.com.uy/php/detallepropiedad.php",
            data={"id": pid},
            headers={"User-Agent": BROWSER_UA, "X-Requested-With": "XMLHttpRequest", "Referer": url},
            timeout=15,
        )
        pd = r.json().get("property_data")
    except Exception:
        return None
    if not pd:
        return None

    price = None
    if _int(pd.get("sale_price")) > 0:
        price = _fmt_price(_int(pd["sale_price"]), pd.get("sale_currency") or "USD")
    elif _int(pd.get("rent_price")) > 0:
        price = _fmt_price(_int(pd["rent_price"]), pd.get("rent_currency") or "USD")

    surf = pd.get("total_surface") or pd.get("roofed_surface")
    area = f"{_int(surf)} m²" if _int(surf) > 0 else None

    exp = None
    if _int(pd.get("expenses")) > 0:
        exp = f"$ {_thousands(_int(pd['expenses']))}"

    loc = None
    if pd.get("location"):
        parts = [x.strip() for x in str(pd["location"]).split("|") if x.strip()]
        if parts:
            loc = parts[-1]

    name = (pd.get("name") or "").strip() or None
    img = None
    if pd.get("photos"):
        img = pd["photos"][0]

    result = {
        "url": url,
        "title": _short_title(html.unescape(name)) if name else None,
        "price": price,
        "image": img,
        "bedrooms": _extract_bedrooms(name or ""),
        "area": area,
        "location": loc,
        "description": _short_desc(html.unescape((pd.get("description") or "").strip())) or None,
        "expenses": exp,
        "lat": str(pd["geo_lat"]) if pd.get("geo_lat") else None,
        "lng": str(pd["geo_long"]) if pd.get("geo_long") else None,
        "error": None,
    }
    return result


# ---------- principal ----------

def _parse(html_text, url):
    result = {
        "url": url, "title": None, "price": None, "image": None,
        "bedrooms": None, "area": None, "location": None, "description": None,
        "expenses": None, "lat": None, "lng": None, "error": None,
    }
    soup = BeautifulSoup(html_text, "lxml")
    ld = _from_jsonld(soup)

    result["title"] = _best_title(soup, ld)
    result["image"] = _best_image(soup, ld)
    result["description"] = _meta(soup, "og:description", "description", "twitter:description")

    # ---- precio: meta -> JSON-LD -> texto ----
    price_meta = _meta(soup, "product:price:amount", "og:price:amount")
    if price_meta and re.search(r"\d", price_meta):
        cur = _meta(soup, "product:price:currency", "og:price:currency") or "USD"
        result["price"] = _fmt_price(price_meta, cur)
    elif ld.get("price"):
        result["price"] = ld["price"]

    blob = " ".join(filter(None, [result["title"], result["description"],
                                  soup.get_text(" ", strip=True)[:6000]]))
    blob = html.unescape(blob)

    if not result["price"]:
        result["price"] = _extract_price(blob)
    result["bedrooms"] = _extract_bedrooms(blob)
    result["area"] = _extract_area(blob)
    result["expenses"] = _extract_expenses(blob)
    result["location"] = _meta(soup, "og:locality", "og:region", "geo.placename")

    if result["title"]:
        result["title"] = _short_title(html.unescape(result["title"]))
    if result["description"]:
        result["description"] = _short_desc(html.unescape(result["description"]))
    return result


def _merge(a, b):
    """Completa los campos vacíos de 'a' con los de 'b'. Además reemplaza el título
    de 'a' si era basura (página de seguridad) y 'b' trae uno bueno."""
    if b.get("title") and _is_junk_title(a.get("title")) and not _is_junk_title(b.get("title")):
        a["title"] = b["title"]
    for k in ("title", "price", "image", "bedrooms", "area", "location", "description", "expenses"):
        if not a.get(k) and b.get(k):
            a[k] = b[k]
    return a


def scrape(url):
    """Devuelve dict con los datos de la propiedad. Nunca lanza excepción.
    Estrategia: navegador normal y, si falta precio/imagen o el título es basura
    (página de seguridad), reintento con UA social — necesario para Mercado Libre,
    que a los bots les muestra la página completa."""
    # Sitios con API propia (webs 100% JavaScript que no exponen datos en el HTML).
    if "inmobiliariagolf.com.uy" in url:
        g = _scrape_golf(url)
        if g:
            return g

    try:
        resp = _get(url, BROWSER_UA)
        resp.raise_for_status()
    except Exception as e:
        return {"url": url, "title": None, "price": None, "image": None, "bedrooms": None,
                "area": None, "location": None, "description": None, "expenses": None,
                "lat": None, "lng": None, "error": f"No se pudo acceder al link: {e}"}

    result = _parse(resp.text, url)

    # Reintento con el crawler social si el navegador no trajo lo esencial.
    if (not result["price"]) or (not result["image"]) or _is_junk_title(result.get("title")):
        try:
            resp2 = _get(url, SOCIAL_UA)
            resp2.raise_for_status()
            result = _merge(result, _parse(resp2.text, url))
        except Exception:
            pass

    # Si el título quedó basura pese a todo, mejor dejarlo vacío que mostrar "Por seguridad…"
    if _is_junk_title(result.get("title")):
        result["title"] = None

    return result
