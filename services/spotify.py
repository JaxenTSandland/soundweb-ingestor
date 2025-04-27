import os
import json
import time
import base64
from typing import List

import requests
from dotenv import load_dotenv

from model.artist_node import ArtistNode

load_dotenv()

MAX_ARTIST_LOOKUP = 1000
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_NAME_SEARCH_URL = "https://api.spotify.com/v1/search"
SPOTIFY_ID_SEARCH_URL = "https://api.spotify.com/v1/artists"

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


def fetch_spotify_artist_by_id(spotify_id, token):
    url = f"{SPOTIFY_ID_SEARCH_URL}/{spotify_id}"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()

def search_spotify_artist_by_name(artist_name, token):
    query = requests.utils.quote(artist_name)
    url = f"{SPOTIFY_NAME_SEARCH_URL}?q={query}&type=artist&limit=3"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    items = response.json().get("artists", {}).get("items", [])
    if not items:
        raise Exception(f"[SPOTIFY] No artists found for {artist_name}")

    exact = next((a for a in items if a["name"].lower() == artist_name.lower()), None)
    return exact or max(items, key=lambda a: a.get("popularity", 0))

def fetch_spotify_data(
    artists: List[ArtistNode],
    write_to_file=False
) -> List[ArtistNode]:
    if artists is None and not write_to_file:
        raise ValueError('[SPOTIFY] artists cannot be None')
    elif artists is None and write_to_file:
        with open(lastfm_artist_path, "r", encoding="utf-8") as f:
            artist_dicts = json.load(f)
            artists = [ArtistNode(**a) for a in artist_dicts]

    token = get_spotify_access_token()
    seen = set()
    i = 1

    for artist in artists:
        if i > MAX_ARTIST_LOOKUP:
            break

        try:
            # Normalize the name early
            if artist.name:
                name = artist.name
                print(f"[SPOTIFY] ({i}/{len(artists)}) Fetching Spotify data for: {name}")
            else:
                name = ""

            # Avoid duplicate name lookups
            spotify_artist = None

            # Prefer lookup by Spotify ID if available
            if artist.spotifyId:
                spotify_artist = fetch_spotify_artist_by_id(artist.spotifyId, token)
                print(f"[SPOTIFY] Found by Id: {spotify_artist}")

            # Fallback: if no result by ID, try searching by name
            if not spotify_artist and name:
                if artist.spotifyId:
                    raise Exception(f"[SPOTIFY] No artist found by ID for {name} (ID: {artist.spotifyId}), falling back to name search.")

                spotify_artist = search_spotify_artist_by_name(name, token)

            if not spotify_artist:
                print(f"[SPOTIFY] No match found for {name} ({artist.spotifyId})")
                continue
            name = spotify_artist.get("name", artist.name)
            norm_name = normalize_name(name)
            if norm_name in seen:
                continue
            seen.add(norm_name)

            # Update the ArtistNode fields
            artist.spotifyId = spotify_artist.get("id", artist.spotifyId)
            artist.id = artist.spotifyId
            artist.name = name
            artist.popularity = spotify_artist.get("popularity", None)
            artist.spotifyUrl = spotify_artist.get("external_urls", {}).get("spotify", artist.spotifyUrl)

            if spotify_artist.get("images"):
                artist.imageUrl = spotify_artist["images"][0].get("url", artist.imageUrl)

            if spotify_artist.get("genres"):
                genres_as_dicts = [{"name": genre} for genre in spotify_artist.get("genres", [])]
                artist.append_genres(genres_as_dicts)

            i += 1

        except Exception as err:
            print(f"[SPOTIFY] Failed to fetch from Spotify for {artist.name or 'Unknown Artist'}: {err}")


    return artists
