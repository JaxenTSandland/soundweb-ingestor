import os
from datetime import datetime, timezone
from http.client import HTTPException
from typing import List

import neo4j
from neo4j import Session

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


def generate_custom_artist_data(spotify_id: str = None, mbid: str = None, user_tag: str = None, session = None):
    if not spotify_id:
        raise ValueError("Must provide spotify id")

    own_driver = None
    own_session = False

    if session is None:
        own_driver = neo4j.GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        session = own_driver.session(database=NEO4J_ARTISTS_DB)
        own_session = True

    try:
        existing = get_existing_artist_by_spotify_id(session, spotify_id)

        if existing:
            artist_props, user_tags, is_top = existing
            print(f"[CUSTOM] Artist {spotify_id} already exists.")

            last_updated_str = artist_props.get("lastUpdated")
            should_refresh = True

            if last_updated_str:
                try:
                    last_updated = datetime.fromisoformat(last_updated_str)
                    days_since_update = (datetime.now(timezone.utc) - last_updated).days
                    should_refresh = days_since_update > 90
                except Exception as e:
                    print(f"[WARN] Could not parse lastUpdated: {e} (forcing refresh)")

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

            refresh_required = not existing or (not is_top and should_refresh)

            if not refresh_required:
                print(f"[CUSTOM] Skipping re-fetch: {'TopArtist' if is_top else 'Recently updated'}")

                artist_node = ArtistNode(
                    id=artist_props.get("id"),
                    name=artist_props.get("name", ""),
                    popularity=artist_props.get("popularity", 0),
                    spotifyId=artist_props.get("spotifyId"),
                    spotifyUrl=artist_props.get("spotifyUrl"),
                    lastfmMBID=artist_props.get("lastfmMBID"),
                    imageUrl=artist_props.get("imageUrl"),
                    genres=artist_props.get("genres", []),
                    x=artist_props.get("x"),
                    y=artist_props.get("y"),
                    color=artist_props.get("color"),
                    userTags=user_tags,
                    relatedArtists=artist_props.get("relatedArtists", []),
                    rank=artist_props.get("rank", 0),
                    lastUpdated=artist_props.get("lastUpdated")
                )

                return {
                    "status": "alreadyExists",
                    "spotifyId": spotify_id,
                    "userTagAdded": user_tag_added,
                    "artistNode": artist_node
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
        if own_session:
            session.close()
        if own_driver:
            own_driver.close()

def ingest_artist_minimal(spotify_id: str, user_tag: str, session: Session):
    artist = ArtistNode(
        id=spotify_id,
        name="",
        spotifyId=spotify_id,
        userTags=[user_tag],
        relatedArtists=[],
        genres=[]
    )

    artists = [artist]
    artists = fetch_spotify_data(artists, write_to_file=False)
    artists = fetch_artist_details(artists, write_to_file=False)
    artists = fetch_artist_genre_data(artists, write_to_file=False)
    artists = implement_genre_data(artists, top_artists=False)
    export_artist_data_to_neo4j(artists, write_to_file=False, add_top_artist_label=False)

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


def remove_user_tag_from_artist_node(spotify_id: str, user_tag: str) -> dict:

    driver = neo4j.GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    session = driver.session(database=NEO4J_ARTISTS_DB)

    try :
        result = session.run(
        """
        MATCH (a:Artist {spotifyId: $spotify_id})
        RETURN a.userTags AS userTags
        """,
        {"spotify_id": spotify_id}
        )
        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail=f"Artist with spotifyId {spotify_id} not found.")

        current_tags = record["userTags"] or []

        if user_tag not in current_tags:
            return {
                "success": True,
                "message": f"user_tag '{user_tag}' was not associated with artist '{spotify_id}'",
                "userTagRemoved": False
            }

        updated_tags = [tag for tag in current_tags if tag != user_tag]

        session.run(
            """
            MATCH (a:Artist {spotifyId: $spotify_id})
            SET a.userTags = $updated_tags
            """,
            {
                "spotify_id": spotify_id,
                "updated_tags": updated_tags
            }
        )

        return {
            "success": True,
            "message": f"Removed user_tag '{user_tag}' from artist '{spotify_id}'",
            "userTagRemoved": True
        }

    finally:
        session.close()
        driver.close()



if __name__ == "__main__":
    main()
