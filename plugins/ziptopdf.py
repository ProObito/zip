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
import motor.motor_asyncio
from config import Config
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB Setup (using motor like database.py)
try:
    mongo_client = motor.motor_asyncio.AsyncIOMotorClient(Config.DB_URL)
    db = mongo_client[Config.DB_NAME]
    autho_users_collection = db["authorized_users"]
    user_settings_collection = db["user_settings"]
    logger.info("MongoDB connected successfully")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    autho_users_collection = None
    user_settings_collection = None

# Ensure SUPPORT_CHAT is defined in Config
if not hasattr(Config, 'SUPPORT_CHAT'):
    Config.SUPPORT_CHAT = "@YourSupportChat"  # Replace with your actual support chat

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

def sanitize_filename(name: str) -> str:
    """Sanitize filename to remove invalid characters."""
    return re.sub(r'[^\w\-_\. ]', '', name).strip()

def generate_pdf(image_files, output_path, progress_callback=None):
    """Convert images to PDF without compression, with progress tracking."""
    total = len(image_files)
    image_iter = (Image.open(f).convert("RGB") for f in image_files)
    first = next(image_iter)
    images = [first]
    for i, img in enumerate(image_iter, 1):
        images.append(img)
        if progress_callback:
            progress_callback(i, total)
    first.save(output_path, save_all=True, append_images=images[1:])

# Progress Bar Utility
async def update_progress_bar(message: Message, current: int, total: int, stage: str):
    """Update Telegram message with a text-based progress bar."""
    if total == 0:
        text = f"<b>{stage}: [          ] 0% (empty file)</b>"
    else:
        percentage = int((current / total) * 100)
        bar_length = 10
        filled = int(bar_length * current / total)
        bar = "█" * filled + " " * (bar_length - filled)
        text = f"<b>{stage}: [{bar}] {percentage}%</b>"
    try:
        await message.edit_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Failed to update progress bar: {e}")

# MongoDB Helper Functions
async def add_autho_user(user_id: int):
    """Add an authorized user to MongoDB."""
    if autho_users_collection is not None:
        await autho_users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id}},
            upsert=True
        )

async def remove_autho_user(user_id: int):
    """Remove an authorized user from MongoDB."""
    if autho_users_collection is not None:
        autho_users_collection.delete_one({"user_id": user_id})

async def is_autho_user_exist(user_id: int) -> bool:
    """Check if a user is authorized."""
    if autho_users_collection is not None:
        user = await autho_users_collection.find_one({"user_id": user_id})
        return bool(user)
    return False

async def get_all_autho_users() -> list:
    """Get list of all authorized users."""
    if autho_users_collection is not None:
        users = []
        async for doc in autho_users_collection.find():
            users.append(doc["user_id"])
        return users
    return []

async def get_format_template(user_id: int) -> str:
    """Get format template for a user (default if not set)."""
    if user_settings_collection is not None:
        user = await user_settings_collection.find_one({"user_id": user_id})
        return user.get("format_template", "default_format") if user else "default_format"
    return "default_format"

async def get_media_preference(user_id: int) -> str:
    """Get media preference for a user (default if not set)."""
    if user_settings_collection is not None:
        user = await user_settings_collection.find_one({"user_id": user_id})
        return user.get("media_preference", "default") if user else "default"
    return "default"

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
    check = await is_autho_user_exist(user_id) or user_id in Config.ADMIN
    if check:
        await message.reply_text(
            "<b>Yes, You are an Authorised user 🟢</b>\n"
            "<blockquote>You can send files to Convert to PDF.</blockquote>",
            parse_mode=ParseMode.HTML
        )
    else:
        await message.reply_text(
            f"<b>Nope, You are not an Authorised user 🔴</b>\n"
            f"<blockquote>You can't send files to Convert to PDF.</blockquote>\n"
            f"<b>Contact {Config.SUPPORT_CHAT} to get authorized.</b>",
            parse_mode=ParseMode.HTML
        )

@Client.on_message(filters.private & filters.document)
async def handle_zip_file(client: Client, message: Message):
    user_id = message.from_user.id
    logger.info(f"Received file from user {user_id}")
    check = await is_autho_user_exist(user_id) or user_id in Config.ADMIN
    if not check:
        logger.warning(f"User {user_id} not authorized for file processing")
        await message.reply_text(
            f"<b>⚠️ You are not an Authorised User ⚠️</b>\n"
            f"<blockquote>If you want to use this bot, please contact: {Config.SUPPORT_CHAT}</blockquote>",
            parse_mode=ParseMode.HTML
        )
        return

    document = message.document
    if not document or not document.file_name.endswith(".zip"):
        logger.error(f"File {document.file_name if document else 'None'} is not a ZIP")
        await message.reply_text(
            "<b>❌ Please send a valid ZIP file.</b>",
            parse_mode=ParseMode.HTML
        )
        return

    # Prompt for new PDF name
    logger.info(f"Prompting user {user_id} for new PDF name")
    prompt_message = await message.reply_text(
        "<b>Please reply to this message with the new name for your PDF (without .pdf extension).</b>",
        parse_mode=ParseMode.HTML
    )

    # Store context in MongoDB
    if user_settings_collection is not None:
        try:
            await user_settings_collection.update_one(
                {"user_id": user_id},
                {"$set": {
                    "pending_pdf_conversion": {
                        "message_id": message.id,
                        "chat_id": message.chat.id,
                        "document": {
                            "file_id": document.file_id,
                            "file_name": document.file_name
                        }
                    }
                }},
                upsert=True
            )
            logger.info(f"Stored conversion context for user {user_id}")
        except Exception as e:
            logger.error(f"MongoDB store error for user {user_id}: {e}")
            await message.reply_text(
                "<b>⚠️ Database error, but you can still reply with the PDF name.</b>",
                parse_mode=ParseMode.HTML
            )
    else:
        logger.error(f"MongoDB not available for user {user_id}")
        await message.reply_text(
            "<b>❌ Database unavailable. Please try again later.</b>",
            parse_mode=ParseMode.HTML
        )
        return

@Client.on_message(filters.private & filters.text & filters.reply)
async def handle_pdf_name_reply(client: Client, message: Message):
    user_id = message.from_user.id
    logger.info(f"Received PDF name reply from user {user_id}")

    try:
        check = await is_autho_user_exist(user_id) or user_id in Config.ADMIN
        if not check:
            logger.warning(f"User {user_id} not authorized")
            await message.reply_text(
                f"<b>⚠️ You are not authorized to use this command ⚠️</b>\n"
                f"<blockquote>Contact {Config.SUPPORT_CHAT} to get authorized.</blockquote>",
                parse_mode=ParseMode.HTML
            )
            return

        # Check if the reply is to a message asking for a PDF name
        if not message.reply_to_message or "Please reply to this message with the new name for your PDF" not in message.reply_to_message.text:
            logger.warning(f"Reply not to PDF name prompt for user {user_id}")
            await message.reply_text(
                "<b>❌ Please reply to the bot's prompt message asking for the PDF name.</b>",
                parse_mode=ParseMode.HTML
            )
            return

        # Get the new PDF name
        new_pdf_name = sanitize_filename(message.text)
        if not new_pdf_name:
            logger.error(f"Invalid PDF name provided by user {user_id}")
            await message.reply_text(
                "<b>❌ Invalid PDF name. Please provide a valid name without special characters.</b>",
                parse_mode=ParseMode.HTML
            )
            return

        # Retrieve conversion context from MongoDB
        if user_settings_collection is None:
            logger.error(f"MongoDB not available for user {user_id}")
            await message.reply_text(
                "<b>❌ Database unavailable. Please try again later.</b>",
                parse_mode=ParseMode.HTML
            )
            return

        try:
            user_data = await user_settings_collection.find_one({"user_id": user_id})
            if not user_data or "pending_pdf_conversion" not in user_data:
                logger.error(f"No pending PDF conversion found in MongoDB for user {user_id}")
                await message.reply_text(
                    "<b>❌ No pending PDF conversion found. Please send the ZIP file again.</b>",
                    parse_mode=ParseMode.HTML
                )
                return
            conversion_data = user_data["pending_pdf_conversion"]
            # Clear pending conversion from MongoDB
            await user_settings_collection.update_one(
                {"user_id": user_id},
                {"$unset": {"pending_pdf_conversion": ""}}
            )
            logger.info(f"Cleared conversion context for user {user_id}")
        except Exception as e:
            logger.error(f"MongoDB retrieve error for user {user_id}: {e}")
            await message.reply_text(
                "<b>❌ Database error. Please send the ZIP file again.</b>",
                parse_mode=ParseMode.HTML
            )
            return

        message_id = conversion_data["message_id"]
        chat_id = conversion_data["chat_id"]
        document_file_id = conversion_data["document"]["file_id"]
        original_file_name = conversion_data["document"]["file_name"]

        # Validate file_id
        if not document_file_id:
            logger.error(f"Invalid file_id for user {user_id}")
            await message.reply_text(
                "<b>❌ Invalid file ID. Please send the ZIP file again.</b>",
                parse_mode=ParseMode.HTML
            )
            return

        # Start processing
        progress_message = await message.reply_text(
            "<b>📂 Processing your ZIP file...</b>",
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Started processing ZIP for user {user_id}, new name: {new_pdf_name}")

        # Use temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, original_file_name)
            debug_zip_path = f"/tmp/{user_id}_{original_file_name}"  # Save for debugging
            extract_folder = os.path.join(temp_dir, f"{new_pdf_name}_extracted")
            pdf_path = os.path.join(temp_dir, f"{new_pdf_name}.pdf")

            # Download ZIP file with progress
            async def download_progress(current, total):
                await update_progress_bar(progress_message, current, total, "Downloading ZIP")

            try:
                logger.info(f"Attempting to download file_id {document_file_id} for user {user_id}")
                # Fetch the original message using message_id and chat_id
                original_message = await client.get_messages(chat_id=chat_id, message_ids=message_id)
                if not original_message or not original_message.document:
                    logger.error(f"Failed to fetch original message for user {user_id}, message_id {message_id}")
                    await progress_message.edit_text(
                        "<b>❌ Failed to access the ZIP file. Please send it again.</b>",
                        parse_mode=ParseMode.HTML
                    )
                    return

                await client.download_media(
                    message=original_message,
                    file_name=zip_path,
                    progress=download_progress
                )
                # Save a copy for debugging
                shutil.copy(zip_path, debug_zip_path)
                # Log file size
                file_size = os.path.getsize(zip_path) if os.path.exists(zip_path) else 0
                logger.info(f"Downloaded ZIP for user {user_id}, size: {file_size} bytes, saved to {debug_zip_path}")
                if file_size == 0:
                    await progress_message.edit_text(
                        "<b>❌ Downloaded file is empty. Please send a valid ZIP file.</b>",
                        parse_mode=ParseMode.HTML
                    )
                    return
            except Exception as e:
                logger.error(f"Download error for user {user_id}: {e}")
                await progress_message.edit_text(
                    f"<b>❌ Error downloading file: {str(e)}</b>",
                    parse_mode=ParseMode.HTML
                )
                return

            # Extract ZIP file with progress
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    file_list = zip_ref.namelist()
                    total_files = len(file_list)
                    if total_files == 0:
                        logger.error(f"ZIP file is empty for user {user_id}")
                        await progress_message.edit_text(
                            "<b>❌ ZIP file is empty.</b>",
                            parse_mode=ParseMode.HTML
                        )
                        return
                    for i, file in enumerate(file_list, 1):
                        zip_ref.extract(file, extract_folder)
                        await update_progress_bar(progress_message, i, total_files, "Extracting ZIP")
                logger.info(f"Extracted ZIP for user {user_id}")
            except zipfile.BadZipFile as e:
                logger.error(f"Invalid ZIP file for user {user_id}: {e}")
                await progress_message.edit_text(
                    f"<b>❌ Invalid ZIP file: {str(e)}. Please ensure the file is a valid ZIP.</b>",
                    parse_mode=ParseMode.HTML
                )
                return

            # Supported image formats
            valid_extensions = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".img")

            # Get image files, sorted naturally
            image_files = natural_sort([
                os.path.join(extract_folder, f) for f in os.listdir(extract_folder)
                if f.lower().endswith(valid_extensions)
            ])

            if not image_files:
                logger.error(f"No images found in ZIP for user {user_id}")
                await progress_message.edit_text(
                    "<b>❌ No images found in the ZIP.</b>",
                    parse_mode=ParseMode.HTML
                )
                return

            # Convert images to PDF with progress
            async def pdf_progress(current, total):
                await update_progress_bar(progress_message, current, total, "Converting to PDF")

            try:
                generate_pdf(image_files, pdf_path, pdf_progress)
                logger.info(f"Converted to PDF for user {user_id}")
            except Exception as e:
                logger.error(f"PDF conversion error for user {user_id}: {e}")
                await progress_message.edit_text(
                    f"<b>❌ Error converting to PDF: {e}</b>",
                    parse_mode=ParseMode.HTML
                )
                return

            # Upload PDF
            try:
                await client.send_document(
                    chat_id=chat_id,
                    document=pdf_path,
                    caption=f"<b>Here is your PDF: {new_pdf_name}.pdf 📄</b>",
                    parse_mode=ParseMode.HTML,
                    reply_to_message_id=message_id
                )
                await progress_message.edit_text(
                    "<b>✅ PDF generated and sent!</b>",
                    parse_mode=ParseMode.HTML
                )
                logger.info(f"Uploaded PDF for user {user_id}")
            except Exception as e:
                logger.error(f"Upload error for user {user_id}: {e}")
                await progress_message.edit_text(
                    f"<b>❌ Error uploading PDF: {e}</b>",
                    parse_mode=ParseMode.HTML
                )

    except Exception as e:
        logger.error(f"Error in handle_pdf_name_reply for user {user_id}: {e}")
        await message.reply_text(
            f"<b>❌ Error: {str(e)}</b>",
            parse_mode=ParseMode.HTML
        )

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

    # Prompt for new PDF name
    logger.info(f"Prompting user {user_id} for new PDF name")
    prompt_message = await message.reply_text(
        "<b>Please reply to this message with the new name for your PDF (without .pdf extension).</b>",
        parse_mode=ParseMode.HTML
    )

    # Store context in MongoDB
    if user_settings_collection is not None:
        try:
            await user_settings_collection.update_one(
                {"user_id": user_id},
                {"$set": {
                    "pending_pdf_conversion": {
                        "message_id": message.id,
                        "chat_id": message.chat.id,
                        "document": {
                            "file_id": document.file_id,
                            "file_name": document.file_name
                        }
                    }
                }},
                upsert=True
            )
            logger.info(f"Stored conversion context for user {user_id}")
        except Exception as e:
            logger.error(f"MongoDB store error for user {user_id}: {e}")
            await message.reply_text(
                "<b>⚠️ Database error, but you can still reply with the PDF name.</b>",
                parse_mode=ParseMode.HTML
            )
    else:
        logger.error(f"MongoDB not available for user {user_id}")
        await message.reply_text(
            "<b>❌ Database unavailable. Please try again later.</b>",
            parse_mode=ParseMode.HTML
        )
        return
