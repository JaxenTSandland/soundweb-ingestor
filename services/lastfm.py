import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://ws.audioscrobbler.com/2.0/"
API_KEY = os.getenv("LASTFM_API_KEY")
MAX_ARTIST_LOOKUP = 1000

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.makedirs(os.path.join(project_root, 'data', 'temp'), exist_ok=True)

top_artists_path = os.path.join(project_root, 'data', 'temp', 'lastfmTopArtists.json')
detailed_artists_path = os.path.join(project_root, 'data', 'temp', 'lastfmArtists.json')
genre_map_path = os.path.join(project_root, 'data', 'genreMap.json')

def normalize_name(name):
    return ''.join(c.lower() for c in name if c.isalnum()).strip()

def get_similar_artists(name):
    try:
        response = requests.get(BASE_URL, params={
            "method": "artist.getsimilar",
            "artist": name,
            "api_key": API_KEY,
            "format": "json",
            "limit": 10
        })
        response.raise_for_status()
        data = response.json()
        return [a["name"] for a in data.get("similarartists", {}).get("artist", [])]
    except Exception as e:
        print(f"Failed to fetch similar artists for {name}: {e}")
        return []

def fetch_top_artists(write_to_file=True):
    all_artists = {}

    for page in range(1, 21):
        try:
            response = requests.get(BASE_URL, params={
                "method": "chart.gettopartists",
                "api_key": API_KEY,
                "format": "json",
                "page": page
            })
            response.raise_for_status()
            data = response.json()
            for artist in data.get("artists", {}).get("artist", []):
                key = normalize_name(artist["name"])
                if key not in all_artists:
                    all_artists[key] = {
                        "name": artist["name"],
                        "mbid": artist.get("mbid"),
                        "url": artist.get("url")
                    }
            print(f"Fetched page {page} with {len(data.get('artists', {}).get('artist', []))} artists")
        except Exception as e:
            print(f"Failed to fetch top artists page {page}: {e}")

    all_values = list(all_artists.values())
    if write_to_file:
        with open(top_artists_path, "w", encoding="utf-8") as f:
            json.dump(all_values, f, indent=2)
        print(f"Saved {len(all_artists)} artists to lastfmTopArtists.json")

    return all_values

def fetch_artist_details(write_to_file=True):
    with open(top_artists_path, "r", encoding="utf-8") as f:
        top_artists = json.load(f)

    with open(genre_map_path, "r", encoding="utf-8") as f:
        genre_map = json.load(f)

    seen = set()
    results = []
    i = 1

    for artist in top_artists:
        if i > MAX_ARTIST_LOOKUP:
            break

        name = artist["name"]
        norm_name = normalize_name(name)
        if norm_name in seen:
            continue
        seen.add(norm_name)

        try:
            response = requests.get(BASE_URL, params={
                "method": "artist.getinfo",
                "artist": name,
                "api_key": API_KEY,
                "format": "json"
            })
            response.raise_for_status()
            data = response.json().get("artist")

            if not data:
                print(f"No artist data for {name}")
                continue

            tags = [tag["name"].lower() for tag in data.get("tags", {}).get("tag", [])]
            filtered_tags = [tag for tag in tags if tag in genre_map]

            similar = get_similar_artists(name)

            images = data.get("image", [])
            image_url = next((img["#text"] for img in images if img.get("size") == "extralarge"), None)

            results.append({
                "name": data["name"],
                "mbid": data.get("mbid"),
                "url": data.get("url"),
                "genres": filtered_tags,
                "similar": similar,
                "imageUrl": image_url
            })

            print(f"({i}/{MAX_ARTIST_LOOKUP}) Processed: {name} ({', '.join(filtered_tags)})")
            i += 1
        except Exception as e:
            print(f"Failed to fetch details for {name}: {e}")

    if write_to_file:
        with open(detailed_artists_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Saved enriched artist data to lastfmArtists.json")

    return results