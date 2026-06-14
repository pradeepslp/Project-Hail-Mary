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
    # Force low-latency InMemoryRedis to bypass remote cloud Redis roundtrip latencies
    redis_client = InMemoryRedis()
    print("[Redis] Successfully initialized low-latency In-Memory Redis.")

async def get_redis():
    global redis_client
    if redis_client is None:
        await init_redis()
    return redis_client
