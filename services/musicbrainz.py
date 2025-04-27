import os
import json
import time
from typing import List

import requests
from dotenv import load_dotenv

from model.artist_node import ArtistNode

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
                print(f"[MUSICBRAINZ] Failed after {retries} attempts: {e}")
                return None

def fetch_artist_genre_data(
    artists: List[ArtistNode],
    write_to_file=False
) -> List[ArtistNode]:
    if artists is None and not write_to_file:
        raise ValueError("[MUSICBRAINZ] artists cannot be None")
    elif artists is None and write_to_file:
        with open(top_artists_path, "r", encoding="utf-8") as f:
            artist_dicts = json.load(f)
            artists = [ArtistNode(**a) for a in artist_dicts]


    seen = set()
    i = 1

    for artist in artists:
        if i > MAX_ARTIST_COUNT:
            break

        name = artist.name
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

        artist.append_genres(artist_data.get("tags", []))
        if not artist.lastfmMBID:
            artist.lastfmMBID = artist_data.get("id")
        tags_list = [tag.get("name", "") for tag in artist_data.get('tags', [])]
        print(f"[MUSICBRAINZ] ({i}/{len(artists)}) Processed: {artist.name} ({', '.join(tags_list)})")
        i += 1

    # if write_to_file:
    #     with open(musicbrainz_output_path, "w", encoding="utf-8") as f:
    #         json.dump([a.to_dict() for a in artists], f, indent=2)

    return artists