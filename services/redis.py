import redis
import json
import os
from datetime import timedelta

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
EX = int(os.getenv("REDIS_DATA_EXPIRATION_TIME_LIMIT", "3600"))

redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

def get_from_cache(key):
    try:
        cached = redis_client.get(key)
        if cached:
            print(f"[Redis] cache hit for key: {key}")
            return json.loads(cached)
        else:
            print(f"[Redis] Cache miss for key: {key}")
            return None
    except Exception as e:
        print(f"[Redis] Get error for key {key}:", e)
        return None

def set_to_cache(key, value, ex=EX):
    try:
        redis_client.setex(key, timedelta(seconds=ex), json.dumps(value))
        print(f"[Redis] Set for key: {key}")
    except Exception as e:
        print(f"[Redis] Set error for key {key}:", e)

def delete_from_cache(key):
    try:
        redis_client.delete(key)
        print(f"[Redis] Deleted key: {key}")
    except Exception as e:
        print(f"[Redis] Delete error for key {key}:", e)