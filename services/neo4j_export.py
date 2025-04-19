import os
import json
import neo4j
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_TOPARTISTS_DB = os.getenv("NEO4J_TOPARTISTS_DB")

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
data_dir = os.path.join(project_root, "data")
temp_dir = os.path.join(data_dir, "temp")
artist_data_path = os.path.join(temp_dir, "artistData.json")

def normalize_name(name):
    return ''.join(c.lower() for c in name if c.isalnum()).strip()

def export_artist_data_to_neo4j(artist_data=None):
    if artist_data is None:
        with open(artist_data_path, "r", encoding="utf-8") as f:
            artist_data = json.load(f)

    driver = neo4j.GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    session = driver.session(database=NEO4J_TOPARTISTS_DB)

    try:
        session.run("MATCH (n) DETACH DELETE n")

        # Create nodes
        for artist in artist_data:
            session.run(
                """
                MERGE (a:Artist {id: $id})
                SET a.name = $name,
                    a.popularity = $popularity,
                    a.spotifyId = $spotifyId,
                    a.spotifyUrl = $spotifyUrl,
                    a.imageUrl = $imageUrl,
                    a.genres = $genres,
                    a.x = $x,
                    a.y = $y,
                    a.color = $color
                """,
                {
                    "id": artist["id"],
                    "name": artist["name"],
                    "popularity": artist.get("popularity", 0),
                    "spotifyId": artist.get("spotifyId"),
                    "spotifyUrl": artist.get("spotifyUrl"),
                    "imageUrl": artist.get("imageUrl"),
                    "genres": artist.get("genres", []),
                    "x": artist.get("x"),
                    "y": artist.get("y"),
                    "color": artist.get("color")
                }
            )

        # Prepare ID mapping
        name_to_id = {normalize_name(a["name"]): a["id"] for a in artist_data}
        created_links = set()

        # Create relationships
        for artist in artist_data:
            from_id = artist["id"]
            for related in artist.get("relatedArtists", []):
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


        print(f"Imported {len(artist_data)} artists and {len(created_links)} relationships into Neo4j.")
    except Exception as e:
        print(f"Error exporting to Neo4j: {e}")
    finally:
        session.close()
        driver.close()