from app.services.cache_service import get_redis
r = get_redis()
if r:
    keys = r.keys("travelo:attractions:*")
    if keys:
        r.delete(*keys)
        print(f"Deleted {len(keys)} attraction cache keys from Redis.")
    else:
        print("No attraction cache keys found.")
else:
    print("Redis not available.")
