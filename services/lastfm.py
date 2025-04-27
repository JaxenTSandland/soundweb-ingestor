import os
import json
from typing import List, Optional

import requests
from dotenv import load_dotenv

from model.artist_node import ArtistNode

load_dotenv()

BASE_URL = "https://ws.audioscrobbler.com/2.0/"
API_KEY = os.getenv("LASTFM_API_KEY")

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
        print(f"[LASTFM] Failed to fetch similar artists for {name}: {e}")
        return []

def fetch_top_artists(write_to_file=False, max_artists:int=1000) -> List[ArtistNode]:
    all_artists = {}
    page = 1

    while len(all_artists) < max_artists:
        try:
            response = requests.get(BASE_URL, params={
                "method": "chart.gettopartists",
                "api_key": API_KEY,
                "format": "json",
                "page": page
            })
            response.raise_for_status()
            data = response.json()
            fetched_artists = data.get("artists", {}).get("artist", [])

            if not fetched_artists:
                print(f"[LASTFM] No more artists returned at page {page}. Stopping.")
                break

            for artist in fetched_artists:
                key = normalize_name(artist["name"])
                if key not in all_artists:
                    all_artists[key] = {
                        "id": None,
                        "name": artist["name"],
                        "lastfmMBID": artist.get("mbid"),
                        "spotifyId": None,
                        "spotifyUrl": artist.get("url"),
                        "genres": [],
                        "popularity": None,
                        "userTags": [],
                        "relatedArtists": [],
                        "imageUrl": None,
                        "color": None,
                        "x": None,
                        "y": None,
                        "rank": None
                    }

                if len(all_artists) >= max_artists:
                    break

            print(f"[LASTFM] Fetched page {page} with {len(fetched_artists)} artists (total unique: {len(all_artists)})")

            page += 1

        except Exception as e:
            print(f"[LASTFM] Failed to fetch top artists page {page}: {e}")
            break

    base_artists = [ArtistNode(**a) for a in all_artists.values()]

    # if write_to_file:
    #     with open(top_artists_path, "w", encoding="utf-8") as f:
    #         json.dump([a.to_dict() for a in base_artists], f, indent=2)
    #     print(f"[LASTFM] Saved {len(base_artists)} artists to lastfmTopArtists.json")

    return base_artists


def fetch_artist_details(
    artists: List[ArtistNode],
    genre_map=None,
    write_to_file=False
) -> List[ArtistNode]:
    if artists is None and not write_to_file:
        raise ValueError("[LASTFM] artists must be provided when not using temp files.")
    elif artists is None and write_to_file:
        with open(top_artists_path, "r", encoding="utf-8") as f:
            artist_dicts = json.load(f)
            artists = [ArtistNode(**a) for a in artist_dicts]

    seen = set()
    i = 1

    for artist in artists:

        name = artist.name
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
                print(f"[LASTFM] No artist data for {name}")
                continue

            # Update the existing artist object
            similar = get_similar_artists(name)

            images = data.get("image", [])
            image_url = next((img["#text"] for img in images if img.get("size") == "extralarge"), None)

            artist.lastfmMBID = data.get("mbid") or artist.lastfmMBID
            artist.imageUrl = artist.imageUrl or image_url
            artist.append_genres(data.get("tags", {}).get("tag", []))
            artist.relatedArtists = similar or artist.relatedArtists

            tags_list = [tag["name"] for tag in data.get("tags", {}).get("tag", []) if tag.get("name")]
            print(f"[LASTFM] ({i}/{len(artists)}) Processed: {name} ({', '.join(tags_list)})")
            i += 1

        except Exception as e:
            print(f"[LASTFM] Failed to fetch details for {name}: {e}")

    # if write_to_file:
    #     with open(detailed_artists_path, "w", encoding="utf-8") as f:
    #         json.dump([a.to_dict() for a in artists], f, indent=2)
    #     print(f"[LASTFM] Saved enriched artist data to lastfmArtists.json")

    return artists
