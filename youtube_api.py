import requests
import os

YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', '')
SEARCH_URL = 'https://www.googleapis.com/youtube/v3/search'


def _search(query, max_results=3):
    if not YOUTUBE_API_KEY:
        return []
    try:
        resp = requests.get(SEARCH_URL, params={
            'part': 'snippet',
            'q': query,
            'key': YOUTUBE_API_KEY,
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
        f'Where to go for eating in {city_name}',
        f'Quick Guide to {city_name}',
        f'Cost of Living in {city_name}',
    ]
    return {q: _search(q) for q in queries}
