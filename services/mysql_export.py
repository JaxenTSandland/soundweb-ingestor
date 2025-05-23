import os
import json
import mysql.connector
from dotenv import load_dotenv

from model.incomplete_artist import IncompleteArtist

load_dotenv()

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
data_dir = os.path.join(project_root, "data")
genre_map_path = os.path.join(data_dir, "genreMap.json")

db_config = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE")
}

def export_genres_to_mysql(genre_map=None):
    if genre_map is None:
        with open(genre_map_path, "r", encoding="utf-8") as f:
            genre_map = json.load(f)

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM genres")

        insert_query = """
            INSERT INTO genres (name, x, y, color, count)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                x = VALUES(x),
                y = VALUES(y),
                color = VALUES(color),
                count = VALUES(count)
        """

        for name, data in genre_map.items():
            x = data.get("x")
            y = data.get("y")
            color = data.get("color")
            count = data.get("count", 0)

            cursor.execute(insert_query, (name, x, y, color, count))

        conn.commit()
        print(f"[MYSQL] Exported {len(genre_map)} genres to MySQL.")
    except Exception as e:
        print(f"[MYSQL] Error exporting genres to MySQL: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def save_incomplete_artist(mysql_conn, artist: IncompleteArtist):
    cursor = mysql_conn.cursor()

    # Avoid inserting duplicates for the same (spotify_id, user_tag)
    cursor.execute(
        """
        SELECT 1 FROM incomplete_artists
        WHERE spotify_id = %s AND user_tag = %s
        """,
        (artist.spotify_id, artist.user_tag)
    )
    if cursor.fetchone():
        print(f"[SKIP] IncompleteArtist {artist.spotify_id} for user {artist.user_tag} already exists.")
        cursor.close()
        return

    cursor.execute("""
        INSERT INTO incomplete_artists
        (spotify_id, user_tag, name, popularity, image_url, failure_reason, last_attempted)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, artist.to_sql_tuple())

    mysql_conn.commit()
    cursor.close()


