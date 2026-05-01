import requests
from bs4 import BeautifulSoup
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
    """Spaces → hyphens and strip accents: 'New York' → 'New-York', 'São Paulo' → 'Sao-Paulo'."""
    normalized = unicodedata.normalize('NFKD', city)
    ascii_city = ''.join(c for c in normalized if not unicodedata.combining(c))
    return ascii_city.strip().replace(' ', '-')


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


def scrape_city_data(city, currency='USD'):
    city_slug = _normalize_city_slug(city)
    url = f'https://www.numbeo.com/cost-of-living/in/{city_slug}?displayCurrency={currency}'

    resp = None
    for attempt in range(MAX_RETRIES):
        try:
            if attempt > 0:
                time.sleep(RETRY_DELAYS[attempt - 1])
            resp = requests.get(url, headers=HEADERS, timeout=20)
            break
        except requests.exceptions.ConnectionError:
            if attempt == MAX_RETRIES - 1:
                print(f'Connection failed after {MAX_RETRIES} attempts for {url}')
                return None
        except Exception as e:
            print(f'Request failed for {url}: {e}')
            return None

    if resp is None or resp.status_code != 200:
        print(f'HTTP {resp.status_code if resp else "no response"} for {url}')
        return None

    try:
        soup = BeautifulSoup(resp.text, 'lxml')
    except Exception:
        soup = BeautifulSoup(resp.text, 'html.parser')

    title = soup.find('title')
    if title:
        title_lower = title.get_text(strip=True).lower()
        if 'not found' in title_lower or 'error' in title_lower:
            return None

    if not soup.find('table', class_='data_wide_table') and not soup.find('table'):
        return None

    return _parse(soup, city_slug.replace('-', ' ').title())


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
