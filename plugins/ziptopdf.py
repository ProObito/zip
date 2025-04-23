import re
import os
import zipfile
import tempfile
import asyncio
import shutil
from PIL import Image
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from pymongo import MongoClient
from config import Config

# MongoDB Setup
mongo_client = MongoClient(Config.DB_URL)
db = mongo_client[Config.DB_NAME]
autho_users_collection = db["authorized_users"]
user_settings_collection = db["user_settings"]

# Ensure SUPPORT_CHAT is defined in Config
if not hasattr(Config, 'SUPPORT_CHAT'):
    Config.SUPPORT_CHAT = "@i_killed_my_clan"  # Replace with your actual support chat

# Utility Functions
def natural_sort(file_list):
    """Sorts file names naturally (e.g., img1, img2, img10)."""
    return sorted(file_list, key=lambda f: [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', f)])

def remove_duplicates(file_list):
    """Keep base image (e.g., 1.jpg) and remove variants like 1t.jpg."""
    base_map = {}
    valid_extensions = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".img")
    for file in file_list:
        name, ext = os.path.splitext(os.path.basename(file))
        if ext.lower() not in valid_extensions:
            continue
        match = re.match(r"^(\d+)[a-zA-Z]?$", name)
        if match:
            base = match.group(1)
            if base not in base_map or not name.endswith("t"):
                base_map[base] = file
    return list(base_map.values())

def generate_pdf(image_files, output_path):
    """Convert images to PDF without compression."""
    image_iter = (Image.open(f).convert("RGB") for f in image_files)
    first = next(image_iter)
    first.save(output_path, save_all=True, append_images=image_iter)

# MongoDB Helper Functions
async def add_autho_user(user_id: int):
    """Add an authorized user to MongoDB."""
    autho_users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id}},
        upsert=True
    )

async def remove_autho_user(user_id: int):
    """Remove an authorized user from MongoDB."""
    autho_users_collection.delete_one({"user_id": user_id})

async def is_autho_user_exist(user_id: int) -> bool:
    """Check if a user is authorized."""
    return bool(autho_users_collection.find_one({"user_id": user_id}))

async def get_all_autho_users() -> list:
    """Get list of all authorized users."""
    return [doc["user_id"] for doc in autho_users_collection.find()]

async def get_format_template(user_id: int) -> str:
    """Get format template for a user (default if not set)."""
    user = user_settings_collection.find_one({"user_id": user_id})
    return user.get("format_template", "default_format") if user else "default_format"

async def get_media_preference(user_id: int) -> str:
    """Get media preference for a user (default if not set)."""
    user = user_settings_collection.find_one({"user_id": user_id})
    return user.get("media_preference", "default") if user else "default"

# Command Handlers
@Client.on_message(filters.private & filters.command("addautho_user") & filters.user(Config.ADMIN))
async def add_authorise_user(client: Client, message: Message):
    ids = message.text.removeprefix("/addautho_user").strip().split()
    check = True

    try:
        if ids:
            for id_str in ids:
                if len(id_str) == 10 and id_str.isdigit():
                    await add_autho_user(int(id_str))
                else:
                    check = False
                    break
        else:
            check = False
    except ValueError:
        check = False

    if check:
        await message.reply_text(
            f'<b>Authorised Users Added ✅</b>\n<blockquote>{" ".join(ids)}</blockquote>',
            parse_mode=ParseMode.HTML
        )
    else:
        await message.reply_text(
            "<b>INVALID USE OF COMMAND:</b>\n"
            "<blockquote><b>➪ Check if the command is empty OR the added ID should be correct (10 digit numbers)</b></blockquote>",
            parse_mode=ParseMode.HTML
        )

@Client.on_message(filters.private & filters.command("delautho_user") & filters.user(Config.ADMIN))
async def delete_authorise_user(client: Client, message: Message):
    ids = message.text.removeprefix("/delautho_user").strip().split()
    check = True

    try:
        if ids:
            for id_str in ids:
                if len(id_str) == 10 and id_str.isdigit():
                    await remove_autho_user(int(id_str))
                else:
                    check = False
                    break
        else:
            check = False
    except ValueError:
        check = False

    if check:
        await message.reply_text(
            f'<b>Deleted Authorised Users 🆑</b>\n<blockquote>{" ".join(ids)}</blockquote>',
            parse_mode=ParseMode.HTML
        )
    else:
        await message.reply_text(
            "<b>INVALID USE OF COMMAND:</b>\n"
            "<blockquote><b>➪ Check if the command is empty OR the added ID should be correct (10 digit numbers)</b></blockquote>",
            parse_mode=ParseMode.HTML
        )

@Client.on_message(filters.private & filters.command("autho_users") & filters.user(Config.ADMIN))
async def authorise_user_list(client: Client, message: Message):
    autho_users = await get_all_autho_users()
    if autho_users:
        autho_users_str = "\n".join(map(str, autho_users))
        await message.reply_text(
            f"<b>🚻 AUTHORIZED USERS: 🌀</b>\n\n<code>{autho_users_str}</code>",
            parse_mode=ParseMode.HTML
        )
    else:
        await message.reply_text(
            "<b>No authorized users found.</b>",
            parse_mode=ParseMode.HTML
        )

@Client.on_message(filters.private & filters.command("check_autho"))
async def check_authorise_user(client: Client, message: Message):
    user_id = message.from_user.id
    check = await is_autho_user_exist(user_id)
    if check:
        await message.reply_text(
            "<b>Yes, You are an Authorised user 🟢</b>\n"
            "<blockquote>You can send files to Rename or Convert to PDF.</blockquote>",
            parse_mode=ParseMode.HTML
        )
    else:
        await message.reply_text(
            f"<b>Nope, You are not an Authorised user 🔴</b>\n"
            f"<blockquote>You can't send files to Rename or Convert to PDF.</blockquote>\n"
            f"<b>Contact {Config.SUPPORT_CHAT} to get authorized.</b>",
            parse_mode=ParseMode.HTML
        )

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client: Client, message: Message):
    user_id = message.from_user.id
    check = await is_autho_user_exist(user_id)
    if not check:
        await message.reply_text(
            f"<b>⚠️ You are not an Authorised User ⚠️</b>\n"
            f"<blockquote>If you want to use this bot, please contact: {Config.SUPPORT_CHAT}</blockquote>",
            parse_mode=ParseMode.HTML
        )
        return

    # Add inline buttons for Zip to PDF and Close
    inline_buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Zip to PDF 📄", callback_data=f"convert_pdf_{message.message_id}")],
        [InlineKeyboardButton("Close ❌", callback_data="close")]
    ])

    await message.reply_text(
        "<b>File received! Choose an option below:</b>",
        reply_markup=inline_buttons,
        parse_mode=ParseMode.HTML
    )

@Client.on_callback_query(filters.regex(r"convert_pdf_(\d+)"))
async def handle_convert_pdf_callback(client: Client, callback_query):
    user_id = callback_query.from_user.id
    message_id = int(callback_query.data.split("_")[2])
    check = await is_autho_user_exist(user_id)
    if not check:
        await callback_query.answer("You are not authorized to perform this action.", show_alert=True)
        return

    # Get the original message
    message = callback_query.message
    chat_id = message.chat.id

    # Check if the message has a document
    if not message.reply_to_message or not message.reply_to_message.document:
        await callback_query.answer("No document found to convert.", show_alert=True)
        return

    document = message.reply_to_message.document
    if not document.file_name.endswith(".zip"):
        await callback_query.answer("Please send a ZIP file for conversion.", show_alert=True)
        return

    zip_name = os.path.splitext(document.file_name)[0]
    await callback_query.message.edit_text("<b>📂 Processing your ZIP file...</b>", parse_mode=ParseMode.HTML)

    # Use temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, document.file_name)
        extract_folder = os.path.join(temp_dir, f"{zip_name}_extracted")
        pdf_path = os.path.join(temp_dir, f"{zip_name}.pdf")

        # Download ZIP file
        try:
            await message.reply_to_message.download(zip_path)
        except Exception as e:
            await callback_query.message.edit_text(f"<b>❌ Error downloading file: {e}</b>", parse_mode=ParseMode.HTML)
            return

        # Extract ZIP file
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_folder)
        except zipfile.BadZipFile:
            await callback_query.message.edit_text("<b>❌ Invalid ZIP file.</b>", parse_mode=ParseMode.HTML)
            return

        # Supported image formats
        valid_extensions = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".img")

        # Get image files, sorted naturally
        image_files = natural_sort([
            os.path.join(extract_folder, f) for f in os.listdir(extract_folder)
            if f.lower().endswith(valid_extensions)
        ])

        if not image_files:
            await callback_query.message.edit_text("<b>❌ No images found in the ZIP.</b>", parse_mode=ParseMode.HTML)
            return

        # Convert images to PDF without compression
        try:
            first_image = Image.open(image_files[0]).convert("RGB")
            image_list = [Image.open(img).convert("RGB") for img in image_files[1:]]
            first_image.save(pdf_path, save_all=True, append_images=image_list)
        except Exception as e:
            await callback_query.message.edit_text(f"<b>❌ Error converting to PDF: {e}</b>", parse_mode=ParseMode.HTML)
            return

        # Upload PDF
        try:
            await client.send_document(
                chat_id=chat_id,
                document=pdf_path,
                caption=f"<b>Here is your PDF: {zip_name}.pdf 📄</b>",
                parse_mode=ParseMode.HTML,
                reply_to_message_id=message_id
            )
            await callback_query.message.edit_text("<b>✅ PDF generated and sent!</b>", parse_mode=ParseMode.HTML)
        except Exception as e:
            await callback_query.message.edit_text(f"<b>❌ Error uploading PDF: {e}</b>", parse_mode=ParseMode.HTML)

@Client.on_callback_query(filters.regex("close"))
async def handle_close_callback(client: Client, callback_query):
    await callback_query.message.delete()
    await callback_query.answer("Message closed.")

@Client.on_message(filters.private & filters.command("pdf"))
async def pdf_handler(client: Client, message: Message):
    user_id = message.from_user.id
    check = await is_autho_user_exist(user_id) or user_id in Config.ADMIN
    if not check:
        await message.reply_text(
            f"<b>⚠️ You are not authorized to use this command ⚠️</b>\n"
            f"<blockquote>Contact {Config.SUPPORT_CHAT} to get authorized.</blockquote>",
            parse_mode=ParseMode.HTML
        )
        return

    # Reply and wait for the ZIP file in the same chat
    await message.reply_text(
        "<b>📂 Please send a ZIP file containing images. Reply to this message with the ZIP file.</b>",
        parse_mode=ParseMode.HTML
    )

@Client.on_message(filters.private & filters.document & filters.reply)
async def handle_zip_reply(client: Client, message: Message):
    user_id = message.from_user.id
    check = await is_autho_user_exist(user_id) or user_id in Config.ADMIN
    if not check:
        await message.reply_text(
            f"<b>⚠️ You are not authorized to use this command ⚠️</b>\n"
            f"<blockquote>Contact {Config.SUPPORT_CHAT} to get authorized.</blockquote>",
            parse_mode=ParseMode.HTML
        )
        return

    # Check if the reply is to a message asking for a ZIP file
    if not message.reply_to_message or "Please send a ZIP file" not in message.reply_to_message.text:
        return

    document = message.document
    if not document.file_name.endswith(".zip"):
        await message.reply_text("<b>❌ Please send a valid ZIP file.</b>", parse_mode=ParseMode.HTML)
        return

    zip_name = os.path.splitext(document.file_name)[0]
    await message.reply_text("<b>📂 Processing your ZIP file...</b>", parse_mode=ParseMode.HTML)

    # Use temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, document.file_name)
        extract_folder = os.path.join(temp_dir, f"{zip_name}_extracted")
        pdf_path = os.path.join(temp_dir, f"{zip_name}.pdf")

        # Download ZIP file
        try:
            await message.download(zip_path)
        except Exception as e:
            await message.reply_text(f"<b>❌ Error downloading file: {e}</b>", parse_mode=ParseMode.HTML)
            return

        # Extract ZIP file
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_folder)
        except zipfile.BadZipFile:
            await message.reply_text("<b>❌ Invalid ZIP file.</b>", parse_mode=ParseMode.HTML)
            return

        # Supported image formats
        valid_extensions = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".img")

        # Get image files, sorted naturally
        image_files = natural_sort([
            os.path.join(extract_folder, f) for f in os.listdir(extract_folder)
            if f.lower().endswith(valid_extensions)
        ])

        if not image_files:
            await message.reply_text("<b>❌ No images found in the ZIP.</b>", parse_mode=ParseMode.HTML)
            return

        # Convert images to PDF without compression
        try:
            first_image = Image.open(image_files[0]).convert("RGB")
            image_list = [Image.open(img).convert("RGB") for img in image_files[1:]]
            first_image.save(pdf_path, save_all=True, append_images=image_list)
        except Exception as e:
            await message.reply_text(f"<b>❌ Error converting to PDF: {e}</b>", parse_mode=ParseMode.HTML)
            return

        # Upload PDF
        try:
            await message.reply_document(
                document=pdf_path,
                caption=f"<b>Here is your PDF: {zip_name}.pdf 📄</b>",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await message.reply_text(f"<b>❌ Error uploading PDF: {e}</b>", parse_mode=ParseMode.HTML)
