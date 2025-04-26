import json
import os
from typing import List

import neo4j
from dotenv import load_dotenv
from datetime import datetime, timezone

from model.artist_node import ArtistNode

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_ARTISTS_DB = os.getenv("NEO4J_ARTISTS_DB")

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
data_dir = os.path.join(project_root, "data")
temp_dir = os.path.join(data_dir, "temp")
artist_data_path = os.path.join(temp_dir, "artistData.json")

def normalize_name(name):
    return ''.join(c.lower() for c in name if c.isalnum()).strip()

def update_neo4j_metadata(session, name="lastSync"):
    now_iso = datetime.now(timezone.utc).isoformat()
    session.run(
        """
        MERGE (m:Metadata {name: $name})
        SET m.updatedAt = datetime($timestamp)
        """,
        name=name,
        timestamp=now_iso
    )

def export_artist_data_to_neo4j(artist_data: List[ArtistNode], write_to_file=False):
    if artist_data is None and write_to_file is False:
        raise ValueError('[NEO4J] artist_data cannot be None')
    elif artist_data is None and write_to_file is True:
        with open(artist_data_path, "r", encoding="utf-8") as f:
            artist_data = json.load(f)

    driver = neo4j.GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    session = driver.session(database=NEO4J_ARTISTS_DB)

    try:
        print("[NEO4J] Starting export process...")

        # Get existing TopArtist node IDs
        existing_ids_result = session.run("MATCH (a:Artist:TopArtist) RETURN a.id AS id")
        existing_top_artist_ids = {record["id"] for record in existing_ids_result}
        new_top_artist_ids = {artist.id for artist in artist_data}

        print(f"[NEO4J] Found {len(existing_top_artist_ids)} existing top artists in database.")
        print(f"[NEO4J] Preparing to sync {len(new_top_artist_ids)} new top artists.")

        # Handle old TopArtists
        stale_ids = existing_top_artist_ids - new_top_artist_ids
        print(f"[NEO4J] Found {len(stale_ids)} stale top artists to clean up.")

        for stale_id in stale_ids:
            result = session.run(
                "MATCH (a:Artist:TopArtist {id: $id}) RETURN a.userTags AS userTags",
                {"id": stale_id}
            )
            record = result.single()
            existing_user_tags = record["userTags"] if record and record["userTags"] else []

            if existing_user_tags:
                print(f"[NEO4J] Preserving user-favorited artist {stale_id}, removing TopArtist label.")
                session.run(
                    """
                    MATCH (a:Artist:TopArtist {id: $id})
                    REMOVE a:TopArtist
                    """,
                    {"id": stale_id}
                )
            else:
                print(f"[NEO4J] Deleting stale artist {stale_id} (no user favorites).")
                session.run(
                    """
                    MATCH (a:Artist:TopArtist {id: $id})
                    DETACH DELETE a
                    """,
                    {"id": stale_id}
                )

        print(f"[NEO4J] Finished cleaning up stale top artists.")

        # Delete old RELATED_TO links between TopArtists
        print("[NEO4J] Deleting old RELATED_TO links between TopArtists...")
        session.run(
            """
            MATCH (a:Artist:TopArtist)-[r:RELATED_TO]-(b:Artist:TopArtist)
            DELETE r
            """
        )
        print("[NEO4J] Old TopArtist relationships deleted.")

        # Now upsert new top artists
        print("[NEO4J] Inserting or updating top artists...")
        for artist in artist_data:
            result = session.run(
                "MATCH (a:Artist {id: $id}) RETURN a.userTags AS userTags",
                {"id": artist.id}
            )
            record = result.single()
            existing_user_tags = record["userTags"] if record and record["userTags"] else []

            data = artist.to_dict()
            data["userTags"] = existing_user_tags

            session.run(
                """
                MERGE (a:Artist {id: $id})
                SET a:TopArtist,
                    a.name = $name,
                    a.popularity = $popularity,
                    a.spotifyId = $spotifyId,
                    a.spotifyUrl = $spotifyUrl,
                    a.lastfmMBID = $lastfmMBID,
                    a.imageUrl = $imageUrl,
                    a.genres = $genres,
                    a.x = $x,
                    a.y = $y,
                    a.color = $color,
                    a.userTags = $userTags
                """,
                data
            )
        print(f"[NEO4J] Finished upserting {len(artist_data)} top artists.")

        # Create new RELATED_TO relationships
        print("[NEO4J] Creating new RELATED_TO relationships...")
        name_to_id = {normalize_name(a.name): a.id for a in artist_data}
        created_links = set()

        for artist in artist_data:
            from_id = artist.id
            for related in artist.relatedArtists or []:
                to_id = name_to_id.get(normalize_name(related))
                if not to_id or from_id == to_id:
                    continue
                id_pair = tuple(sorted([from_id, to_id]))
                if id_pair in created_links:
                    continue
                created_links.add(id_pair)

                session.run(
                    """
                    MATCH (a:Artist {id: $id1})
                    MATCH (b:Artist {id: $id2})
                    MERGE (a)-[:RELATED_TO]-(b)
                    """,
                    {"id1": id_pair[0], "id2": id_pair[1]}
                )

        print(f"[NEO4J] Created {len(created_links)} new relationships.")

        update_neo4j_metadata(session)
        print("[NEO4J] Metadata (lastSync) updated.")

        print(f"[NEO4J] Finished syncing {len(artist_data)} top artists and {len(created_links)} relationships to Neo4j.")

    except Exception as e:
        print(f"[NEO4J] Error exporting to Neo4j: {e}")
    finally:
        session.close()
        driver.close()
        print("[NEO4J] Connection closed.")
