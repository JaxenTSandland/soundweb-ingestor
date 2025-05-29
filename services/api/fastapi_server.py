import os
from datetime import datetime, timezone
from typing import List

import mysql.connector
import neo4j
import uvicorn
from fastapi import FastAPI, HTTPException
from neo4j import Session
from pydantic import BaseModel
from main import generate_custom_artist_data, refresh_custom_artists_by_user_tag, remove_user_tag_from_artist_node, \
    ingest_artist_minimal
from fastapi.middleware.cors import CORSMiddleware

from services.mysql_export import db_config
from services.neo4j_export import add_user_tag_to_artist

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/test")
def api_test():
    return {"success": True, "message": "Ingestor API is running."}

class CustomArtistRequest(BaseModel):
    user_tag: str
    spotify_id: str

class BulkCustomArtistRequest(BaseModel):
    user_tag: str
    spotify_ids: List[str]

class RefreshRequest(BaseModel):
    user_tag: str

class RemoveUserTagRequest(BaseModel):
    spotify_id: str
    user_tag: str

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_ARTISTS_DB = os.getenv("NEO4J_ARTISTS_DB")

@app.post("/api/custom-artist")
def ingest_custom_artist(request: CustomArtistRequest):
    try:
        result = generate_custom_artist_data(
            user_tag=request.user_tag,
            spotify_id=request.spotify_id
        )

        if result["status"] == "success":
            return {
                "success": True,
                "alreadyExists": False,
                "message": f"Custom artist '{result['artistName'] or request.spotify_id}' ingested successfully.",
                "data": result
            }
        elif result["status"] == "alreadyExists":
            return {
                "success": True,
                "alreadyExists": True,
                "message": f"Artist '{request.spotify_id}' already exists. User tag {'added' if result['userTagAdded'] else 'already present'}.",
                "data": result
            }
        else:
            raise HTTPException(status_code=500, detail="Unexpected result status.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/custom-artist/bulk")
def ingest_multiple_custom_artists(request: BulkCustomArtistRequest):
    driver = neo4j.GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    session = driver.session(database=NEO4J_ARTISTS_DB)
    mysql_conn = mysql.connector.connect(**db_config)

    try:
        existing_map = get_existing_artists_metadata(session, request.spotify_ids)

        # Fetch all artist IDs currently tagged by this user
        query = """
        MATCH (a:Artist)
        WHERE $user_tag IN a.userTags
        RETURN a.spotifyId AS sid
        """
        result = session.run(query, user_tag=request.user_tag)
        tagged_ids = set(record["sid"] for record in result if record["sid"])
        current_ids = set(request.spotify_ids)

        # Remove tag from artists no longer in the current list
        to_remove = tagged_ids - current_ids
        if to_remove:
            print(f"Removing user tag from {len(to_remove)} artists")
            session.run("""
                MATCH (a:Artist)
                WHERE a.spotifyId IN $ids
                SET a.userTags = [tag IN a.userTags WHERE tag <> $user_tag]
            """, ids=list(to_remove), user_tag=request.user_tag)

        def should_process(meta, sid):
            if not meta:
                return True
            try:
                last = datetime.fromisoformat(meta["lastUpdated"])
                daysSinceLastDataRefresh = (datetime.now(timezone.utc) - last).days
            except (KeyError, TypeError, ValueError):
                daysSinceLastDataRefresh = 999
            if daysSinceLastDataRefresh >= 30:
                return True
            if request.user_tag not in meta["userTags"]:
                add_user_tag_to_artist(sid, request.user_tag, session)

        ids_to_process = [
            sid for sid in request.spotify_ids if should_process(existing_map.get(sid), sid)
        ]

        for idx, sid in enumerate(ids_to_process, start=1):
            print(f"[{idx}/{len(ids_to_process)}] Processing artist ID: {sid}")
            ingest_artist_minimal(
                sid,
                request.user_tag,
                session=session,
                mysql_conn=mysql_conn,
                already_exists=existing_map.get(sid) is not None
            )

        return {
            "success": True,
            "processedCount": len(ids_to_process),
            "removedCount": len(to_remove),
            "skippedCount": len(request.spotify_ids) - len(ids_to_process)
        }

    finally:
        session.close()
        driver.close()
        mysql_conn.close()

@app.post("/api/refresh-custom-artists")
def refresh_custom_artists(request: RefreshRequest):
    user_tag = request.user_tag
    if not user_tag:
        raise HTTPException(status_code=400, detail="Missing user_tag")
    try:
        results = refresh_custom_artists_by_user_tag(user_tag)
        return {
            "success": True,
            "message": f"Refreshed {len(results)} custom artists for user tag {user_tag}.",
            "refreshedArtists": [r["spotifyId"] for r in results]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/remove-custom-artist-usertag")
def remove_user_tag_from_artist(request: RemoveUserTagRequest):
    try:
        return remove_user_tag_from_artist_node(request.spotify_id, request.user_tag)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_existing_artists_metadata(session: Session, spotify_ids: List[str]) -> dict:
    result = session.run(
        """
        UNWIND $ids AS sid
        MATCH (a:Artist {spotifyId: sid})
        RETURN a.spotifyId AS spotifyId,
               a:TopArtist AS isTopArtist,
               a.lastUpdated AS lastUpdated,
               a.userTags AS userTags
        """,
        {"ids": spotify_ids}
    )

    existing = {}
    for record in result:
        existing[record["spotifyId"]] = {
            "isTopArtist": record.get("isTopArtist", False),
            "lastUpdated": record.get("lastUpdated"),
            "userTags": record.get("userTags") or []
        }
    return existing