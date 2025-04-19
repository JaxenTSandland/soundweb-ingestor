import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://musicbrainz.org/ws/2/artist/"
MAX_RETRIES = 3
DELAY_MS = 5000
MAX_ARTIST_COUNT = 1000

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
data_dir = os.path.join(project_root, "data")
temp_dir = os.path.join(data_dir, "temp")
os.makedirs(temp_dir, exist_ok=True)

top_artists_path = os.path.join(temp_dir, "lastfmTopArtists.json")
genre_map_path = os.path.join(data_dir, "genreMap.json")
musicbrainz_output_path = os.path.join(temp_dir, "musicBrainzArtists.json")

def normalize_name(name):
    return ''.join(c.lower() for c in name if c.isalnum()).strip()

def delay(ms):
    time.sleep(ms / 1000)

def fetch_with_retry(url, retries=MAX_RETRIES, delay_ms=DELAY_MS):
    headers = {
        "User-Agent": "SoundWebIngestor/1.0"
    }

    for attempt in range(retries):
        try:
            res = requests.get(url, headers=headers, timeout=10)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            if attempt < retries - 1:
                delay(delay_ms)
            else:
                print(f"Failed after {retries} attempts: {e}")
                return None

def fetch_artist_genre_data(write_to_file=True, top_artists=None):
    if top_artists is None:
        with open(top_artists_path, "r", encoding="utf-8") as f:
            top_artists = json.load(f)

    with open(genre_map_path, "r", encoding="utf-8") as f:
        genre_map = json.load(f)

    results = []
    seen = set()
    i = 1

    for artist in top_artists:
        if i > MAX_ARTIST_COUNT:
            break

        name = artist["name"]
        norm_name = normalize_name(name)
        if norm_name in seen:
            continue
        seen.add(norm_name)

        url = f"{BASE_URL}?query=artist:{requests.utils.quote(name)}&fmt=json"
        data = fetch_with_retry(url)

        if not data or not data.get("artists"):
            print(f"No match for {name}")
            continue

        artist_data = data["artists"][0]
        tags = [
            tag["name"].lower()
            for tag in artist_data.get("tags", [])
            if tag["name"].lower() in genre_map
        ]

        results.append({
            "name": artist_data["name"],
            "mbid": artist_data["id"],
            "genres": tags
        })

        print(f"({i}) Processed: {artist_data['name']} ({', '.join(tags)})")
        i += 1

    if write_to_file:
        with open(musicbrainz_output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    return results
