import os
from flask import (Flask, render_template, request, redirect,
                   url_for, jsonify, flash)
from dotenv import load_dotenv

from database import (init_db, save_report, get_report, get_all_reports,
                      delete_report, save_market_items, get_market_items,
                      get_profile, save_profile)
from scraper import scrape_city_data
from youtube_api import get_city_videos

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'soft-landing-dev-key-change-me')

CURRENCIES = [
    ('USD', 'USD — US Dollar'),
    ('EUR', 'EUR — Euro'),
    ('GBP', 'GBP — British Pound'),
    ('JPY', 'JPY — Japanese Yen'),
    ('BRL', 'BRL — Brazilian Real'),
    ('CAD', 'CAD — Canadian Dollar'),
    ('AUD', 'AUD — Australian Dollar'),
    ('CHF', 'CHF — Swiss Franc'),
    ('CNY', 'CNY — Chinese Yuan'),
    ('INR', 'INR — Indian Rupee'),
    ('MXN', 'MXN — Mexican Peso'),
    ('SGD', 'SGD — Singapore Dollar'),
    ('HKD', 'HKD — Hong Kong Dollar'),
    ('NZD', 'NZD — New Zealand Dollar'),
    ('SEK', 'SEK — Swedish Krona'),
    ('NOK', 'NOK — Norwegian Krone'),
    ('DKK', 'DKK — Danish Krone'),
    ('THB', 'THB — Thai Baht'),
    ('MYR', 'MYR — Malaysian Ringgit'),
    ('PHP', 'PHP — Philippine Peso'),
    ('KRW', 'KRW — South Korean Won'),
    ('ZAR', 'ZAR — South African Rand'),
    ('AED', 'AED — UAE Dirham'),
    ('TRY', 'TRY — Turkish Lira'),
    ('PLN', 'PLN — Polish Zloty'),
    ('CZK', 'CZK — Czech Koruna'),
    ('ARS', 'ARS — Argentine Peso'),
    ('CLP', 'CLP — Chilean Peso'),
    ('COP', 'COP — Colombian Peso'),
    ('PEN', 'PEN — Peruvian Sol'),
    ('VND', 'VND — Vietnamese Dong'),
    ('IDR', 'IDR — Indonesian Rupiah'),
]

init_db()

# ── Country name → Unicode flag emoji ─────────────────────────────────────────
_COUNTRY_ISO = {
    'Afghanistan': 'AF', 'Albania': 'AL', 'Algeria': 'DZ', 'Angola': 'AO',
    'Argentina': 'AR', 'Armenia': 'AM', 'Australia': 'AU', 'Austria': 'AT',
    'Azerbaijan': 'AZ', 'Bahrain': 'BH', 'Bangladesh': 'BD', 'Belarus': 'BY',
    'Belgium': 'BE', 'Bolivia': 'BO', 'Bosnia And Herzegovina': 'BA',
    'Brazil': 'BR', 'Bulgaria': 'BG', 'Cambodia': 'KH', 'Cameroon': 'CM',
    'Canada': 'CA', 'Chile': 'CL', 'China': 'CN', 'Colombia': 'CO',
    'Costa Rica': 'CR', 'Croatia': 'HR', 'Cuba': 'CU', 'Cyprus': 'CY',
    'Czech Republic': 'CZ', 'Denmark': 'DK', 'Dominican Republic': 'DO',
    'Ecuador': 'EC', 'Egypt': 'EG', 'El Salvador': 'SV', 'Estonia': 'EE',
    'Ethiopia': 'ET', 'Finland': 'FI', 'France': 'FR', 'Georgia': 'GE',
    'Germany': 'DE', 'Ghana': 'GH', 'Greece': 'GR', 'Guatemala': 'GT',
    'Honduras': 'HN', 'Hong Kong': 'HK', 'Hungary': 'HU', 'Iceland': 'IS',
    'India': 'IN', 'Indonesia': 'ID', 'Iran': 'IR', 'Iraq': 'IQ',
    'Ireland': 'IE', 'Israel': 'IL', 'Italy': 'IT', 'Jamaica': 'JM',
    'Japan': 'JP', 'Jordan': 'JO', 'Kazakhstan': 'KZ', 'Kenya': 'KE',
    'Kuwait': 'KW', 'Latvia': 'LV', 'Lebanon': 'LB', 'Lithuania': 'LT',
    'Luxembourg': 'LU', 'Malaysia': 'MY', 'Malta': 'MT', 'Mexico': 'MX',
    'Moldova': 'MD', 'Mongolia': 'MN', 'Montenegro': 'ME', 'Morocco': 'MA',
    'Mozambique': 'MZ', 'Myanmar': 'MM', 'Nepal': 'NP', 'Netherlands': 'NL',
    'New Zealand': 'NZ', 'Nicaragua': 'NI', 'Nigeria': 'NG', 'Norway': 'NO',
    'Oman': 'OM', 'Pakistan': 'PK', 'Panama': 'PA', 'Paraguay': 'PY',
    'Peru': 'PE', 'Philippines': 'PH', 'Poland': 'PL', 'Portugal': 'PT',
    'Qatar': 'QA', 'Romania': 'RO', 'Russia': 'RU', 'Saudi Arabia': 'SA',
    'Senegal': 'SN', 'Serbia': 'RS', 'Singapore': 'SG', 'Slovakia': 'SK',
    'Slovenia': 'SI', 'South Africa': 'ZA', 'South Korea': 'KR', 'Spain': 'ES',
    'Sri Lanka': 'LK', 'Sudan': 'SD', 'Sweden': 'SE', 'Switzerland': 'CH',
    'Taiwan': 'TW', 'Tanzania': 'TZ', 'Thailand': 'TH', 'Tunisia': 'TN',
    'Turkey': 'TR', 'Uganda': 'UG', 'Ukraine': 'UA',
    'United Arab Emirates': 'AE', 'United Kingdom': 'GB',
    'United States': 'US', 'Uruguay': 'UY', 'Uzbekistan': 'UZ',
    'Venezuela': 'VE', 'Vietnam': 'VN', 'Yemen': 'YE', 'Zambia': 'ZM',
    'Zimbabwe': 'ZW',
}


def _country_flag(country_name):
    code = _COUNTRY_ISO.get(country_name, '')
    if not code:
        return ''
    return ''.join(chr(0x1F1E6 + ord(c) - ord('A')) for c in code)


app.jinja_env.filters['flag'] = _country_flag


@app.route('/')
def index():
    recent = get_all_reports(limit=6)
    return render_template('index.html', recent_reports=recent)


@app.route('/search', methods=['POST'])
def search():
    city = request.form.get('city', '').strip()
    if not city:
        flash('Please enter a city name.', 'warning')
        return redirect(url_for('index'))
    slug = city.replace(' ', '-')
    return redirect(url_for('report', city=slug))


@app.route('/report/<path:city>')
def report(city):
    city_display = city.replace('-', ' ').title()
    refresh = request.args.get('refresh') == '1'
    profile_currency = get_profile().get('currency', 'USD')

    cached = None if refresh else get_report(city_display)
    # Invalidate cache when currency changed or report predates country detection
    if cached and (cached.get('currency') != profile_currency or 'country' not in cached):
        cached = None
    from_cache = cached is not None

    if not from_cache:
        data = scrape_city_data(city, currency=profile_currency)
        if data:
            save_report(city_display, data)
        else:
            flash(
                f'Could not retrieve data for "{city_display}". '
                'Check the spelling or try another city.',
                'danger'
            )
            return redirect(url_for('index'))
    else:
        data = cached

    videos = get_city_videos(city_display)

    return render_template(
        'report.html',
        city=city_display,
        city_slug=city,
        data=data,
        videos=videos,
        from_cache=from_cache,
    )


@app.route('/history')
def history():
    reports = get_all_reports()
    return render_template('history.html', reports=reports)


@app.route('/compare')
def compare():
    cities = request.args.getlist('city')
    profile_data = get_profile()
    profile_currency = profile_data.get('currency', 'USD')
    budget_total = float(profile_data.get('budget', 0) or 0)
    comparison = {}
    for c in cities:
        c_display = c.replace('-', ' ').title()
        d = get_report(c_display)
        if d and d.get('currency') != profile_currency:
            d = None
        if not d:
            d = scrape_city_data(c, currency=profile_currency)
            if d:
                save_report(c_display, d)
        if d:
            comparison[c_display] = d

    # Compute affordability rankings: count how many items each city prices lowest
    affordability_rank = {}
    least_affordable_rank = 0
    if len(comparison) >= 2:
        city_cheapest = {city: 0 for city in comparison}
        all_item_prices = {}
        for city, city_data in comparison.items():
            for cat, items in city_data.get('categories', {}).items():
                for item in items:
                    if not item.get('price'):
                        continue
                    key = (cat, item['name'])
                    if key not in all_item_prices:
                        all_item_prices[key] = {}
                    all_item_prices[key][city] = item['price']
        for city_prices in all_item_prices.values():
            if len(city_prices) < 2:
                continue
            min_price = min(city_prices.values())
            for city, price in city_prices.items():
                if price == min_price:
                    city_cheapest[city] += 1
        sorted_counts = sorted(city_cheapest.values(), reverse=True)
        affordability_rank = {
            city: sorted_counts.index(count) + 1
            for city, count in city_cheapest.items()
        }
        least_affordable_rank = max(affordability_rank.values()) if affordability_rank else 0

    # Summary insights
    most_affordable_city = next(
        (c for c, r in affordability_rank.items() if r == 1),
        next(iter(comparison), '')
    )
    cheapest_restaurants_city = ''
    cheapest_markets_city = ''
    city_salaries = {}
    if comparison:
        rest_avgs, mkt_avgs = {}, {}
        for city, d in comparison.items():
            for cat_name, items in d.get('categories', {}).items():
                prices = [i['price'] for i in items if i.get('price')]
                if prices:
                    avg = sum(prices) / len(prices)
                    if cat_name == 'Restaurants':
                        rest_avgs[city] = avg
                    elif cat_name == 'Markets':
                        mkt_avgs[city] = avg
            for item in d.get('categories', {}).get('Salaries And Financing', []):
                if 'Average Monthly Net Salary' in item.get('name', ''):
                    city_salaries[city] = item.get('price', 0)
                    break
        if rest_avgs:
            cheapest_restaurants_city = min(rest_avgs, key=rest_avgs.get)
        if mkt_avgs:
            cheapest_markets_city = min(mkt_avgs, key=mkt_avgs.get)

    all_reports = get_all_reports()
    return render_template('compare.html',
                           comparison=comparison,
                           all_reports=all_reports,
                           selected=cities,
                           affordability_rank=affordability_rank,
                           least_affordable_rank=least_affordable_rank,
                           most_affordable_city=most_affordable_city,
                           cheapest_restaurants_city=cheapest_restaurants_city,
                           cheapest_markets_city=cheapest_markets_city,
                           city_salaries=city_salaries,
                           budget_total=budget_total,
                           profile_currency=profile_currency)


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        currency = request.form.get('currency', 'USD')
        budget = float(request.form.get('budget', 0) or 0)
        if not name or not email:
            flash('Name and email are required.', 'warning')
            return redirect(url_for('profile'))
        valid_codes = {c[0] for c in CURRENCIES}
        if currency not in valid_codes:
            currency = 'USD'
        save_profile(name, email, currency, budget)
        flash('Profile saved successfully.', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html',
                           profile=get_profile(),
                           currencies=CURRENCIES,
                           market_items=get_market_items())


# ── API endpoints ──────────────────────────────────────────────────────────────

@app.route('/api/market', methods=['POST'])
def api_market():
    items = request.json.get('items', [])
    save_market_items(items)
    return jsonify({'ok': True})


@app.route('/api/report/<int:report_id>', methods=['DELETE'])
def api_delete(report_id):
    delete_report(report_id)
    return jsonify({'ok': True})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=os.environ.get('FLASK_ENV') != 'production',
            host='0.0.0.0', port=port)
