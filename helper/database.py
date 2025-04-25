# +++ Made By Obito [telegram username: @i_killed_my_clan] +++ #
from pymongo import MongoClient
from config import Config

mongo_client = MongoClient(Config.DB_URL)
db = mongo_client[Config.DB_NAME]
autho_users_collection = db["authorized_users"]
user_settings_collection = db["user_settings"]

async def add_autho_user(user_id: int):
    autho_users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id}},
        upsert=True
    )

async def remove_autho_user(user_id: int):
    autho_users_collection.delete_one({"user_id": user_id})

async def is_autho_user_exist(user_id: int) -> bool:
    return bool(autho_users_collection.find_one({"user_id": user_id}))

async def get_all_autho_users() -> list:
    return [doc["user_id"] for doc in autho_users_collection.find()]

async def set_thumbnail(user_id: int, thumbnail_path: str):
    user_settings_collection.update_one(
        {"user_id": user_id},
        {"$set": {"thumbnail_path": thumbnail_path}},
        upsert=True
    )

async def get_thumbnail(user_id: int) -> str:
    user = user_settings_collection.find_one({"user_id": user_id})
    return user.get("thumbnail_path") if user else None

async def delete_thumbnail(user_id: int):
    user_settings_collection.update_one(
        {"user_id": user_id},
        {"$unset": {"thumbnail_path": ""}}
    )

async def set_banner_status(user_id: int, status: bool):
    user_settings_collection.update_one(
        {"user_id": user_id},
        {"$set": {"banner_status": status}},
        upsert=True
    )

async def get_banner_status(user_id: int) -> bool:
    user = user_settings_collection.find_one({"user_id": user_id})
    return user.get("banner_status", False) if user else False

async def set_banner_position(user_id: int, position: str):
    user_settings_collection.update_one(
        {"user_id": user_id},
        {"$set": {"banner_position": position}},
        upsert=True
    )

async def get_banner_position(user_id: int) -> str:
    user = user_settings_collection.find_one({"user_id": user_id})
    return user.get("banner_position", "first") if user else "first"

async def set_banner_url(user_id: int, url: str):
    user_settings_collection.update_one(
        {"user_id": user_id},
        {"$set": {"banner_url": url}},
        upsert=True
    )

async def get_banner_url(user_id: int) -> str:
    user = user_settings_collection.find_one({"user_id": user_id})
    return user.get("banner_url", None) if user else None

async def set_banner_image(user_id: int, image_path: str):
    user_settings_collection.update_one(
        {"user_id": user_id},
        {"$set": {"banner_image_path": image_path}},
        upsert=True
    )

async def get_banner_image(user_id: int) -> str:
    user = user_settings_collection.find_one({"user_id": user_id})
    return user.get("banner_image_path") if user else None

async def delete_banner_image(user_id: int):
    user_settings_collection.update_one(
        {"user_id": user_id},
        {"$unset": {"banner_image_path": ""}}
    )
