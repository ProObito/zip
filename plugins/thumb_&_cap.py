# plugins/thumb_&_cap.py
from pyrogram import Client, filters
from pyrogram.types import ForceReply
from database import set_thumbnail, get_thumbnail, delete_thumbnail, set_caption, get_caption, delete_caption
from config import Config

@Client.on_message(filters.private & filters.command("set_thumb") & filters.user(Config.ADMIN))
async def addthumbs(client, message):
    if message.reply_to_message and message.reply_to_message.photo:
        await set_thumbnail(message.from_user.id, file_id=message.reply_to_message.photo.file_id)
        await message.reply_text("✅ Thumbnail set successfully!")
    else:
        await message.reply_text("Please reply to a photo to set it as your thumbnail.", reply_markup=ForceReply())

@Client.on_message(filters.private & filters.command("see_thumb") & filters.user(Config.ADMIN))
async def seethumbs(client, message):
    thumbnail = await get_thumbnail(message.from_user.id)
    if thumbnail:
        await message.reply_photo(photo=thumbnail['file_id'], caption="This is your current thumbnail.")
    else:
        await message.reply_text("No thumbnail set.")

@Client.on_message(filters.private & filters.command("del_thumb") & filters.user(Config.ADMIN))
async def delthumbs(client, message):
    if await delete_thumbnail(message.from_user.id):
        await message.reply_text("✅ Thumbnail deleted successfully!")
    else:
        await message.reply_text("No thumbnail to delete.")

@Client.on_message(filters.private & filters.command("set_caption") & filters.user(Config.ADMIN))
async def setcaption(client, message):
    if len(message.command) > 1:
        caption = " ".join(message.command[1:])
        await set_caption(message.from_user.id, caption)
        await message.reply_text(f"✅ Caption set to: `{caption}`")
    else:
        await message.reply_text("Please provide a caption.\nExample: `/set_caption File: {filename}`", reply_markup=ForceReply())

@Client.on_message(filters.private & filters.command("see_caption") & filters.user(Config.ADMIN))
async def seecaption(client, message):
    caption = await get_caption(message.from_user.id)
    if caption:
        await message.reply_text(f"Your current caption: `{caption}`")
    else:
        await message.reply_text("No caption set.")

@Client.on_message(filters.private & filters.command("del_caption") & filters.user(Config.ADMIN))
async def delcaption(client, message):
    if await delete_caption(message.from_user.id):
        await message.reply_text("✅ Caption deleted successfully!")
    else:
        await message.reply_text("No caption to delete.")

def register_handlers(app: Client):
    app.on_message(filters.private & filters.command(["set_thumb", "see_thumb", "del_thumb", "set_caption", "see_caption", "del_caption"]))(lambda c, m: None)  # Placeholder for registration
