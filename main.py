import os
from typing import List

import neo4j

from services.artist_lookup import get_existing_artist_by_spotify_id
from services.lastfm import (
    fetch_top_artists,
    fetch_artist_details,
)
from services.musicbrainz import fetch_artist_genre_data
from services.spotify import fetch_spotify_data
from services.combine_artist_data import combine_top_artist_data, implement_genre_data
from services.neo4j_export import export_artist_data_to_neo4j
from services.mysql_export import export_genres_to_mysql

from model.artist_node import ArtistNode
from utils.checkpoint import save_checkpoint, load_checkpoint

ENV = os.getenv("ENV", "production")
LOCAL_ENV = ENV == "local"
WRITE_TO_FILE = LOCAL_ENV

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_ARTISTS_DB = os.getenv("NEO4J_ARTISTS_DB")

RELOAD_LASTFM = True if LOCAL_ENV else True
RELOAD_MUSICBRAINZ = True if LOCAL_ENV else True
RELOAD_SPOTIFY = True if LOCAL_ENV else True
EXPORT_TO_NEO4J = True if LOCAL_ENV else True
EXPORT_TO_MYSQL = True if LOCAL_ENV else True


def main():
    # generate_custom_artist_data(
    #     user_tag="7717",
    #     name="Love Spells",
    #     spotify_id="5iiqhuffUTPEOjAUDj19IW"
    # )
    generate_top_artist_data()


def generate_top_artist_data(max_artists:int=1000):
    artists: list[ArtistNode] = []

    if RELOAD_LASTFM:
        print("[MAIN] Fetching top artists from Last.fm...")
        artists = fetch_top_artists(max_artists=max_artists)
        if WRITE_TO_FILE:
            save_checkpoint(artists, "lastfm_top")

        print("\n[MAIN] Fetching detailed info from Last.fm...")
        artists = fetch_artist_details(artists)
        if WRITE_TO_FILE:
            save_checkpoint(artists, "lastfm_detailed")

        print(f"\n[MAIN] Collected detailed info for {len(artists)} artists.")
    else:
        artists = load_checkpoint('lastfm_detailed')
        print(f"\n[MAIN] Loaded top artists from Last.fm detailed json file")

    if RELOAD_MUSICBRAINZ:
        print("\n[MAIN] Fetching genre data from MusicBrainz...")
        artists = fetch_artist_genre_data(artists)
        if WRITE_TO_FILE:
            save_checkpoint(artists, "musicbrainz")
        print(f"[MAIN] Collected MusicBrainz genre info for {len(artists)} artists.")
    else:
        artists = load_checkpoint('musicbrainz')
        print(f"\n[MAIN] Loaded top artists from MusicBrainz detailed json file")

    if RELOAD_SPOTIFY:
        print("\n[MAIN] Fetching Spotify data...")
        artists = fetch_spotify_data(artists)
        if WRITE_TO_FILE:
            save_checkpoint(artists, "spotify")
        print(f"[MAIN] Collected Spotify info for {len(artists)} artists.")
    else:
        artists = load_checkpoint('spotify')
        print(f"\n[MAIN] Loaded top artists from Spotify detailed json file")

    print("\n[MAIN] Finalizing artist nodes (calculate x/y/color)...")
    artists = implement_genre_data(artists, top_artists=True)
    if WRITE_TO_FILE:
        save_checkpoint(artists, "final_genre_combined")
    print(f"[MAIN] Finalized {len(artists)} artist nodes wth proper genre data implemented.")

    if EXPORT_TO_NEO4J:
        print("\n[MAIN] Exporting artists to Neo4j...")
        export_artist_data_to_neo4j(artists, write_to_file=WRITE_TO_FILE, add_top_artist_label=True)

    # if EXPORT_TO_MYSQL:
    #     print("\n[MAIN] Exporting genres to MySQL...")
    #     export_genres_to_mysql()


def generate_custom_artist_data(spotify_id: str = None, mbid: str = None, user_tag: str = None):
    if not spotify_id:
        raise ValueError("Must provide spotify id")

    driver = neo4j.GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    session = driver.session(database=NEO4J_ARTISTS_DB)

    try:
        existing = get_existing_artist_by_spotify_id(session, spotify_id)

        if existing:
            artist_props, user_tags, is_top = existing
            print(f"[CUSTOM] Artist {spotify_id} already exists.")

            user_tag_added = False
            if user_tag and user_tag not in user_tags:
                user_tags.append(user_tag)
                session.run(
                    """
                    MATCH (a:Artist {spotifyId: $spotifyId})
                    SET a.userTags = $userTags
                    """,
                    {"spotifyId": spotify_id, "userTags": user_tags}
                )
                print(f"[CUSTOM] Added userTag {user_tag} to artist.")
                user_tag_added = True

            if is_top:
                print(f"[CUSTOM] Skipping re-fetch: Artist is a TopArtist.")
                return {
                    "status": "alreadyExists",
                    "spotifyId": spotify_id,
                    "userTagAdded": user_tag_added,
                    "artistNode": None
                }

        print(f"[MAIN] Starting custom artist ingestion for SpotifyID: {spotify_id}...")

        artist = ArtistNode(
            id=spotify_id,
            name="",
            spotifyId=spotify_id,
            lastfmMBID=mbid,
            genres=[],
            userTags=[user_tag],
            relatedArtists=[],
        )

        artists = [artist]

        print("[MAIN] Fetching Spotify details...")
        artists = fetch_spotify_data(artists, write_to_file=False)

        print("[MAIN] Fetching Last.fm details...")
        artists = fetch_artist_details(artists, write_to_file=False)

        print("[MAIN] Fetching genre data from MusicBrainz...")
        artists = fetch_artist_genre_data(artists, write_to_file=False)

        print("[MAIN] Combining final data...")
        artists = implement_genre_data(artists, top_artists=False)

        print("[MAIN] Exporting to Neo4j...")
        export_artist_data_to_neo4j(artists, write_to_file=False, add_top_artist_label=False)

        print(f"[MAIN] Finished ingesting {artists[0].name}.")

        return {
            "status": "success",
            "artistName": artists[0].name,
            "spotifyId": spotify_id,
            "artistNode": artists[0]
        }

    finally:
        session.close()
        driver.close()

def get_custom_artists_by_user_tag(user_tag: str) -> List[str]:
    driver = neo4j.GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    session = driver.session(database=NEO4J_ARTISTS_DB)
    try:
        result = session.run(
            """
            MATCH (a:Artist)
            WHERE NOT a:TopArtist AND $userTag IN a.userTags
            RETURN a.spotifyId AS spotifyId
            """,
            {"userTag": user_tag}
        )
        return [record["spotifyId"] for record in result if record["spotifyId"]]
    finally:
        session.close()
        driver.close()

def refresh_custom_artists_by_user_tag(user_tag: str):
    spotify_ids = get_custom_artists_by_user_tag(user_tag)
    results = []
    for spotify_id in spotify_ids:
        result = generate_custom_artist_data(spotify_id=spotify_id, user_tag=user_tag)
        results.append(result)
    return results

if __name__ == "__main__":
    main()
