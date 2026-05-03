import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urlparse
import re
import time
import random
import unicodedata

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

CATEGORY_ORDER = [
    'Restaurants', 'Markets', 'Transportation', 'Utilities (Monthly)',
    'Sports And Leisure', 'Childcare', 'Clothing And Shoes',
    'Rent Per Month', 'Buy Apartment Price', 'Salaries And Financing',
]

MAX_RETRIES = 3
RETRY_DELAYS = [2, 4, 8]


def _normalize_city_slug(city):
    """Spaces → hyphens and strip accents: 'New York' → 'New-York', 'São Paulo' → 'Sao-Paulo'.
    If already a hyphenated slug (no spaces), return as-is to preserve Numbeo's casing."""
    normalized = unicodedata.normalize('NFKD', city)
    ascii_city = ''.join(c for c in normalized if not unicodedata.combining(c))
    s = ascii_city.strip()
    if '-' in s and ' ' not in s:
        return s
    return s.title().replace(' ', '-')


def suggest_cities(term, limit=8):
    """Return up to `limit` autocomplete suggestions from Numbeo.
    Each item is {'label': 'Rio de Janeiro, Brazil', 'slug': 'Rio-de-Janeiro-Brazil', 'city_id': '2318'}.
    """
    try:
        resp = requests.get(
            'https://www.numbeo.com/common/CitySearchJson',
            params={'term': term},
            headers={
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'X-Requested-With': 'XMLHttpRequest',
                'User-Agent': HEADERS['User-Agent'],
            },
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data[:limit]:
            if isinstance(item, dict):
                label = item.get('label', '')
                city_id = str(item.get('value', ''))
            else:
                label = str(item)
                city_id = ''
            if not label:
                continue
            slug = '-'.join(label.replace(',', '').split())
            results.append({'label': label, 'slug': slug, 'city_id': city_id})
        return results
    except Exception:
        return []


def resolve_true_slug(city_label, city_id):
    """Use Numbeo's dispatcher to find the real page slug for a city.

    The dispatcher redirects to the canonical cost-of-living page, so we
    follow the redirect and extract the slug from the final URL.

    Example: city_label='Cordoba, Argentina', city_id='7448'
             → dispatcher → https://www.numbeo.com/cost-of-living/in/Cordoba
             → returns 'Cordoba'
    """
    where = 'https://www.numbeo.com/cost-of-living/in/'
    dispatcher_url = (
        'https://www.numbeo.com/common/dispatcher.jsp'
        '?where=' + quote(where, safe='') +
        '&city_selector_menu_city_id=' + quote(city_label, safe='') +
        '&city_id=' + quote(str(city_id), safe='') +
        '&name_city_id=' + quote(city_label, safe='')
    )
    try:
        resp = requests.get(
            dispatcher_url,
            headers=HEADERS,
            timeout=10,
            allow_redirects=True,
        )
        if '/cost-of-living/in/' in resp.url:
            path = urlparse(resp.url).path          # e.g. /cost-of-living/in/Cordoba
            slug = path.split('/in/')[-1].strip('/')
            if slug:
                return slug
    except Exception:
        pass
    return None


def resolve_city_slug(term):
    """Query Numbeo city autocomplete and return the URL slug for the first result.

    Example: 'Rio de Janeiro' → 'Rio-de-Janeiro-Brazil'
    Returns None if the request fails or returns no results.
    """
    try:
        resp = requests.get(
            'https://www.numbeo.com/common/CitySearchJson',
            params={'term': term},
            headers={
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'X-Requested-With': 'XMLHttpRequest',
                'User-Agent': HEADERS['User-Agent'],
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        first = data[0]
        if isinstance(first, dict):
            label = first.get('label') or first.get('value') or ''
        else:
            label = str(first)
        if not label:
            return None
        # Remove commas, collapse whitespace, replace spaces with hyphens
        slug = '-'.join(label.replace(',', '').split())
        return slug or None
    except Exception:
        return None


def _detect_country(soup):
    # Try every breadcrumb selector Numbeo might use
    bc = (soup.find(id='breadcrumb') or
          soup.find('ol', class_='breadcrumb') or
          soup.find(class_='breadcrumb'))
    if bc:
        links = bc.find_all('a')
        # Numbeo breadcrumb: Home > Cost of Living > Country > City
        # Country is always links[2]; city may or may not be a link
        if len(links) >= 3:
            return links[2].get_text(strip=True)

    # Fallback: title "Cost of Living in City[, State], Country. Updated Oct 2024."
    title = soup.find('title')
    if title:
        m = re.search(
            r'Cost of Living in (.+?)(?:\.\s*Updated|\.\s*$|$)',
            title.get_text(strip=True),
            re.IGNORECASE,
        )
        if m:
            parts = [p.strip() for p in m.group(1).split(',')]
            # Country is the last comma-segment with more than 3 chars
            # (filters US state abbreviations like "NY", "CA")
            for part in reversed(parts):
                part = re.sub(r'\s*\d.*$', '', part).strip()
                if len(part) > 3:
                    return part
    return ''


def _parse_price(text):
    if not text:
        return None
    cleaned = re.sub(r'[^\d.,\-]', '', text.replace('\xa0', '').strip())
    cleaned = cleaned.replace(',', '')
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def _parse_range(text):
    if not text:
        return None, None
    text = text.replace('\xa0', '').strip()
    match = re.search(r'([\d,]+\.?\d*)\s*[-–]\s*([\d,]+\.?\d*)', text)
    if match:
        lo = _parse_price(match.group(1))
        hi = _parse_price(match.group(2))
        return lo, hi
    return None, None


def _detect_currency(soup):
    sel = soup.find('select', id='userCurrency')
    if sel:
        opt = sel.find('option', selected=True)
        if opt:
            return opt.get_text(strip=True)
    # Scan price cells only — more targeted than searching the full page
    price_cells = soup.find_all('td', class_='priceValue')
    price_text = ' '.join(td.get_text() for td in price_cells[:20])
    for sym in ['€', '£', '¥', 'R$', 'A$', 'C$', '$']:
        if sym in price_text:
            return sym
    return '$'


def _fetch_slug(slug, currency, max_tries=MAX_RETRIES):
    """Fetch Numbeo page for slug. Returns BeautifulSoup on success, None on failure."""
    url = f'https://www.numbeo.com/cost-of-living/in/{slug}?displayCurrency={currency}'
    resp = None
    for attempt in range(max_tries):
        try:
            if attempt > 0:
                time.sleep(RETRY_DELAYS[attempt - 1])
            resp = requests.get(url, headers=HEADERS, timeout=20)
            break
        except requests.exceptions.ConnectionError:
            if attempt == max_tries - 1:
                return None
        except Exception:
            return None

    if resp is None or resp.status_code != 200:
        return None

    try:
        soup = BeautifulSoup(resp.text, 'lxml')
    except Exception:
        soup = BeautifulSoup(resp.text, 'html.parser')

    title = soup.find('title')
    if title:
        t = title.get_text(strip=True).lower()
        if 'not found' in t or 'error' in t:
            return None

    if not soup.find('table', class_='data_wide_table') and not soup.find('table'):
        return None

    return soup


def scrape_city_data(city, currency='USD'):
    base_slug = _normalize_city_slug(city)
    parts = base_slug.split('-')

    # Build candidate slugs: full slug first, then progressively strip trailing
    # segments (country name appended by autocomplete) until a valid page is found.
    # e.g. "Cordoba-Argentina" → "Cordoba", "New-York-United-States" → "New-York"
    seen = set()
    candidates = []
    for i in range(len(parts), max(0, len(parts) - 4), -1):
        slug = '-'.join(parts[:i])
        if slug and slug not in seen:
            seen.add(slug)
            candidates.append(slug)

    for idx, slug in enumerate(candidates):
        # Only retry on the primary attempt; fallbacks get a single try
        soup = _fetch_slug(slug, currency, max_tries=MAX_RETRIES if idx == 0 else 1)
        if soup:
            return _parse(soup, slug.replace('-', ' ').title())

    return None


def _parse(soup, city_display):
    currency = _detect_currency(soup)
    country = _detect_country(soup)
    categories = {}
    current_cat = 'General'

    tables = soup.find_all('table', class_='data_wide_table')
    if not tables:
        tables = soup.find_all('table')

    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            # Section header row detection
            ths = row.find_all('th')
            cat_name = None
            for th in ths:
                # Numbeo style: <th class="highlighted_th"><div class="category_title">Name
                cat_div = th.find('div', class_='category_title')
                if cat_div:
                    cat_name = cat_div.get_text(strip=True)
                    break
                # Fallback: th with colspan
                colspan = th.get('colspan', '')
                txt = th.get_text(strip=True)
                if colspan and txt and txt not in ('Average', 'Range', ''):
                    cat_name = txt
                    break
            if cat_name:
                current_cat = cat_name
                continue

            tds = row.find_all('td')
            if len(tds) < 2:
                continue

            # Item name: usually first td that isn't a price
            item_name = tds[0].get_text(strip=True)
            if not item_name or item_name in ('Edit',):
                if len(tds) > 1:
                    item_name = tds[1].get_text(strip=True)

            # Price value: td with class priceValue
            price_td = None
            for td in tds:
                if 'priceValue' in (td.get('class') or []):
                    price_td = td
                    break

            if not price_td:
                continue

            price_val = _parse_price(price_td.get_text(strip=True))
            if price_val is None:
                continue

            # Range: find td after the blank td following priceValue
            price_idx = tds.index(price_td)
            lo, hi = None, None
            if price_idx + 2 < len(tds):
                lo, hi = _parse_range(tds[price_idx + 2].get_text(strip=True))
            elif price_idx + 1 < len(tds):
                lo, hi = _parse_range(tds[price_idx + 1].get_text(strip=True))

            if current_cat not in categories:
                categories[current_cat] = []

            categories[current_cat].append({
                'name': item_name,
                'price': price_val,
                'range_low': lo,
                'range_high': hi,
            })

    if not categories:
        return None

    # Remove empty or duplicate General if real categories exist
    if 'General' in categories and len(categories) > 1:
        del categories['General']

    # Order categories canonically
    ordered = {}
    for cat in CATEGORY_ORDER:
        if cat in categories:
            ordered[cat] = categories.pop(cat)
    ordered.update(categories)

    # Compute per-category averages for summary card
    summary = {}
    for cat, items in ordered.items():
        prices = [i['price'] for i in items if i['price']]
        if prices:
            summary[cat] = round(sum(prices) / len(prices), 2)

    return {
        'city': city_display,
        'country': country,
        'currency': currency,
        'categories': ordered,
        'summary': summary,
    }
