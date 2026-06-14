import os
import json
import asyncio
from dotenv import load_dotenv
import redis.asyncio as aioredis
from backend.utils.timezone_helper import ist_now

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")

class InMemoryRedis:
    """Fallback in-memory mock for Redis when local server or Upstash is down"""
    def __init__(self):
        self._data = {}
        self._lists = {}

    async def ping(self):
        return True

    async def set(self, key, value, ex=None):
        self._data[key] = str(value)
        return True

    async def get(self, key):
        return self._data.get(key)

    async def rpush(self, key, *values):
        if key not in self._lists:
            self._lists[key] = []
        for val in values:
            self._lists[key].append(str(val))
        return len(self._lists[key])

    async def lrange(self, key, start, end):
        if key not in self._lists:
            return []
        lst = self._lists[key]
        if end == -1:
            return lst[start:]
        return lst[start:end+1]

    async def delete(self, *keys):
        count = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                count += 1
            if key in self._lists:
                del self._lists[key]
                count += 1
        return count

    async def type(self, key):
        if key in self._lists:
            return "list"
        if key in self._data:
            return "string"
        return "none"

    async def close(self):
        pass

redis_client = None

async def init_redis():
    global redis_client
    if REDIS_URL:
        # Check URL protocol
        url_to_connect = REDIS_URL
        if url_to_connect.startswith("redis-cli"):
            # Clean command-line artifact if passed incorrectly
            import re
            match = re.search(r'redis?s://[^\s]+', url_to_connect)
            if match:
                url_to_connect = match.group(0)

        # Standard Upstash SSL check
        ssl_kwargs = {}
        if url_to_connect.startswith("rediss://"):
            ssl_kwargs = {
                "ssl_cert_reqs": None,
                "ssl_check_hostname": False
            }
            
        print(f"[Redis] Connecting to Upstash Redis at {url_to_connect.split('@')[-1] if '@' in url_to_connect else url_to_connect}...")
        try:
            redis_client = aioredis.from_url(
                url_to_connect, 
                decode_responses=True, 
                socket_timeout=5.0,
                **ssl_kwargs
            )
            await asyncio.wait_for(redis_client.ping(), timeout=5.0)
            print("[Redis] Successfully connected to Redis.")
            
            # Self-healing: delete events key if it is not a list
            try:
                type_val = await redis_client.type("hail_mary:events")
                if type_val != "list" and type_val != "none":
                    print(f"[Redis] Cleaning up stale events key of type: {type_val}")
                    await redis_client.delete("hail_mary:events")
            except Exception as ex:
                print(f"[Redis] Self-healing check failed: {ex}")
                
            return
        except Exception as e:
            print(f"[Redis] WARNING: Redis connection failed: {e}. Falling back to In-Memory Redis Emulator.")
            
    redis_client = InMemoryRedis()
    print("[Redis] Successfully initialized In-Memory Redis Emulator.")

async def get_redis():
    global redis_client
    if redis_client is None:
        await init_redis()
    return redis_client
