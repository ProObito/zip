# +++ Made By Obito [telegram username: @i_killed_my_clan] +++ #
from pymongo import MongoClient
from config import Config

client = MongoClient(Config.DB_URL)
db = client[Config.DB_NAME]
users_collection = db["users"]

async def add_user(user_id: int, username: str, first_name: str, last_name: str):
    user_data = {
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "thumbnail": None,
        "caption": None,
        "authorized": False
    }
    users_collection.update_one({"user_id": user_id}, {"$set": user_data}, upsert=True)

async def is_autho_user_exist(user_id: int) -> bool:
    user = users_collection.find_one({"user_id": user_id})
    return user.get("authorized", False) if user else False

async def set_thumbnail(user_id: int, file_id: str):
    users_collection.update_one({"user_id": user_id}, {"$set": {"thumbnail": file_id}})

async def get_thumbnail(user_id: int):
    user = users_collection.find_one({"user_id": user_id})
    return user.get("thumbnail") if user and user.get("thumbnail") else None

async def delete_thumbnail(user_id: int) -> bool:
    result = users_collection.update_one({"user_id": user_id}, {"$unset": {"thumbnail": ""}})
    return result.modified_count > 0

async def set_caption(user_id: int, caption: str):
    users_collection.update_one({"user_id": user_id}, {"$set": {"caption": caption}})

async def get_caption(user_id: int):
    user = users_collection.find_one({"user_id": user_id})
    return user.get("caption") if user and user.get("caption") else None

async def delete_caption(user_id: int) -> bool:
    result = users_collection.update_one({"user_id": user_id}, {"$unset": {"caption": ""}})
    return result.modified_count > 0
