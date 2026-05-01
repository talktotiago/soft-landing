import requests
import os

SEARCH_URL = 'https://www.googleapis.com/youtube/v3/search'


def _search(query, max_results=3):
    api_key = os.getenv('YOUTUBE_API_KEY', '')
    if not api_key:
        return []
    try:
        resp = requests.get(SEARCH_URL, params={
            'part': 'snippet',
            'q': query,
            'key': api_key,
            'maxResults': max_results,
            'type': 'video',
            'videoEmbeddable': 'true',
            'relevanceLanguage': 'en',
        }, timeout=10)
        if resp.status_code != 200:
            return []
        results = []
        for item in resp.json().get('items', []):
            vid_id = item['id']['videoId']
            snippet = item['snippet']
            results.append({
                'id': vid_id,
                'title': snippet['title'],
                'channel': snippet['channelTitle'],
                'thumbnail': snippet['thumbnails'].get('medium', {}).get('url', ''),
                'embed_url': f'https://www.youtube.com/embed/{vid_id}',
            })
        return results
    except Exception as e:
        print(f'YouTube API error: {e}')
        return []


def get_city_videos(city_name):
    queries = [
        f'Where to eat in {city_name}',
        f'Places to visit in {city_name}',
        f'Top attractions in {city_name}',
        f'Cost of Living in {city_name}',
    ]
    return {q: _search(q) for q in queries}
