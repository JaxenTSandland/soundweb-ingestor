import os
import json
import time
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

MAX_ARTIST_LOOKUP = 1000
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_SEARCH_URL = "https://api.spotify.com/v1/search"

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
data_dir = os.path.join(project_root, "data")
temp_dir = os.path.join(data_dir, "temp")
os.makedirs(temp_dir, exist_ok=True)

lastfm_artist_path = os.path.join(temp_dir, "lastfmArtists.json")
spotify_output_path = os.path.join(temp_dir, "spotifyArtists.json")

def normalize_name(name):
    return ''.join(c.lower() for c in name if c.isalnum()).strip()

def get_spotify_access_token():
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    auth_str = f"{client_id}:{client_secret}"
    auth_bytes = base64.b64encode(auth_str.encode()).decode()

    headers = {
        "Authorization": f"Basic {auth_bytes}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(SPOTIFY_TOKEN_URL, headers=headers, data={"grant_type": "client_credentials"})
    response.raise_for_status()
    return response.json()["access_token"]

def search_spotify_artist(artist_name, token):
    query = requests.utils.quote(artist_name)
    url = f"{SPOTIFY_SEARCH_URL}?q={query}&type=artist&limit=3"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    items = response.json().get("artists", {}).get("items", [])
    if not items:
        return None

    exact = next((a for a in items if a["name"].lower() == artist_name.lower()), None)
    return exact or max(items, key=lambda a: a.get("popularity", 0))

def fetch_spotify_data(write_to_file=True, lastfm_artists=None):
    if lastfm_artists is None and write_to_file is False:
        raise ValueError('[SPOTIFY] lastfm_artists cannot be None')
    elif lastfm_artists is None and write_to_file is True:
        with open(lastfm_artist_path, "r", encoding="utf-8") as f:
            lastfm_artists = json.load(f)

    token = get_spotify_access_token()
    results = []
    seen = set()
    i = 1

    for artist in lastfm_artists:
        if i > MAX_ARTIST_LOOKUP:
            break

        name = artist["name"]
        norm_name = normalize_name(name)
        if norm_name in seen:
            continue
        seen.add(norm_name)

        print(f"[SPOTIFY] ({i}/{MAX_ARTIST_LOOKUP}) Searching Spotify for: {name}")
        try:
            spotify_artist = search_spotify_artist(name, token)
            if not spotify_artist:
                print(f"No match found for {name}")
                continue

            results.append({
                "name": spotify_artist["name"],
                "spotifyId": spotify_artist["id"],
                "popularity": spotify_artist.get("popularity", 0),
                "genres": spotify_artist.get("genres", []),
                "followers": spotify_artist.get("followers", {}).get("total", 0),
                "listeners": artist.get("listeners", 0),
                "spotifyUrl": spotify_artist.get("external_urls", {}).get("spotify", ""),
                "imageUrl": spotify_artist.get("images", [{}])[0].get("url")
            })

            i += 1
        except Exception as err:
            print(f"[SPOTIFY] Failed to fetch from Spotify for {name}: {err}")

    if write_to_file:
        with open(spotify_output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    return results
