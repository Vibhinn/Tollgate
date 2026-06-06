import chromadb
import redis.asyncio as redis

redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)


vector_db_client = chromadb.Client()
storage_collection = vector_db_client.create_collection("STORAGE")