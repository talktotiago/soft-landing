import requests

def search_city(term):
    url = "https://www.numbeo.com/common/CitySearchJson"

    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0"
    }

    params = {
        "term": term
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()

        print(f"\nResults for '{term}':\n")

        # Try JSON first
        try:
            data = response.json()
            if isinstance(data, list):
                for item in data:
                    print(item)
            else:
                print(data)

        # Fallback to raw text
        except ValueError:
            print(response.text)

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")


if __name__ == "__main__":
    city_term = input("Enter city search term: ").strip()
    search_city(city_term)