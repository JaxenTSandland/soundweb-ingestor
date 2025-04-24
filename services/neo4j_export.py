import os
from typing import List

import neo4j
from dotenv import load_dotenv
from datetime import datetime, timezone

from utils.artist_node import ArtistNode

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

def export_artist_data_to_neo4j(artist_data: List[ArtistNode]):
    if artist_data is None:
        raise ValueError('artist_data cannot be None')

    driver = neo4j.GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    session = driver.session(database=NEO4J_ARTISTS_DB)

    try:
        # Get existing top artist IDs
        existing_ids_result = session.run("MATCH (a:Artist:TopArtist) RETURN a.id AS id")
        existing_ids = {record["id"] for record in existing_ids_result}
        new_ids = {artist.id for artist in artist_data}

        for artist in artist_data:
            # Check for existing userTags
            result = session.run("MATCH (a:Artist {id: $id}) RETURN a.userTags AS userTags", {"id": artist.id})
            record = result.single()
            existing_user_tags = record["userTags"] if record and record["userTags"] else []

            # Prepare dict and preserve userTags
            data = artist.to_dict()
            data["userTags"] = existing_user_tags

            session.run(
                """
                MERGE (a {id: $id})
                SET a:Artist,
                    a:TopArtist,
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

        # Remove old top artists (unless tagged by users)
        stale_ids = existing_ids - new_ids
        for stale_id in stale_ids:
            session.run(
                """
                MATCH (a:Artist:TopArtist {id: $id})
                WHERE (a.userTags IS NULL OR size(a.userTags) = 0)
                DETACH DELETE a
                """,
                {"id": stale_id}
            )

        print(f"[NEO4J] Deleted {len(stale_ids)} stale artists")

        # Relationship linking
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
                    MATCH (a:Artist {id: $id1}), (b:Artist {id: $id2})
                    MERGE (a)-[:RELATED_TO]-(b)
                    """,
                    {"id1": id_pair[0], "id2": id_pair[1]}
                )

        update_neo4j_metadata(session)
        print(f"[NEO4J] Synced {len(artist_data)} top artists and {len(created_links)} relationships to Neo4j.")

    except Exception as e:
        print(f"Error exporting to Neo4j: {e}")
    finally:
        session.close()
        driver.close()
