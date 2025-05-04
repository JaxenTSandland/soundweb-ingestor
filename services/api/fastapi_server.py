import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from main import generate_custom_artist_data, refresh_custom_artists_by_user_tag
from fastapi.middleware.cors import CORSMiddleware

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


class RefreshRequest(BaseModel):
    user_tag: str

@app.post("/api/add-custom-artist")
def ingest_custom_artist(request: CustomArtistRequest):
    try:
        result = generate_custom_artist_data(
            user_tag=request.user_tag,
            spotify_id=request.spotify_id
        )

        if result["status"] == "success":
            return {
                "success": True,
                "message": f"Custom artist '{result['artistName'] or request.spotify_id}' ingested successfully.",
                "data": result
            }
        elif result["status"] == "alreadyExists":
            return {
                "success": True,
                "message": f"Artist '{request.spotify_id}' already exists. User tag {'added' if result['userTagAdded'] else 'already present'}.",
                "data": result
            }
        else:
            raise HTTPException(status_code=500, detail="Unexpected result status.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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