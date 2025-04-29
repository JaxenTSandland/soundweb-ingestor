print("✅ fastapi_server.py has been loaded")

from fastapi import FastAPI

app = FastAPI()

@app.get("/api/test")
def api_test():
    return {"success": True, "message": "Ingestor API is running."}

@app.get("/api/health")
def health_check():
    return {"status": "ok"}
