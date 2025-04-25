# +++ Made By Obito [telegram username: @i_killed_my_clan] +++ #
import os
import tempfile
import asyncio
import shutil
from PIL import Image
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import Config
from helper.database import (
    is_autho_user_exist, add_autho_user, remove_autho_user, get_all_autho_users,
    set_thumbnail, get_thumbnail, delete_thumbnail,
    set_banner_status, get_banner_status, set_banner_position, get_banner_position,
    set_banner_url, get_banner_url, set_banner_image, get_banner_image, delete_banner_image
)
from helper.utils import create_banner_pdf, add_banner_to_pdf, add_banner_to_epub

async def show_banner_settings(client: Client, message: Message, user_id: int):
    banner_status = await get_banner_status(user_id)
    banner_position = await get_banner_position(user_id)
    banner_url = await get_banner_url(user_id) or "None"
    banner_image = await get_banner_image(user_id)
    status_text = "✅ Enabled" if banner_status else "❌ Disabled"

    text = (
        "📄 <b>PDF Banner Settings</b>\n"
        f"▫️ <b>Banner Status:</b> {status_text}\n"
        f"▫️ <b>Current Position:</b> {banner_position}\n"
        f"▫️ <b>Click URL:</b> {banner_url}\n\n"
        "<b>Configure your PDF banners:</b>\n"
        "1. Turn banner on/off\n"
        "2. Set banner position\n"
        "3. Add clickable URL\n"
        "4. Upload banner image"
    )

    buttons = [
        [
            InlineKeyboardButton("On" if not banner_status else "Off", callback_data=f"banner_toggle_{user_id}"),
            InlineKeyboardButton("Position", callback_data=f"banner_position_{user_id}")
        ],
        [InlineKeyboardButton("Set Image" if not banner_image else "Change/Remove Image", callback_data=f"banner_image_{user_id}")],
        [InlineKeyboardButton("Close ❌", callback_data="close")]
    ]

    await message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="html"
    )

def register_handlers(app: Client):
    @app.on_message(filters.private & filters.command("banner"))
    async def banner_settings_handler(client: Client, message: Message):
        user_id = message.from_user.id
        check = await is_autho_user_exist(user_id) or user_id in Config.ADMIN
        if not check:
            await message.reply_text(
                f"<b>⚠️ You are not authorized to use this command ⚠️</b>\n"
                f"<blockquote>Contact {Config.SUPPORT_CHAT} to get authorized.</blockquote>",
                parse_mode="html"
            )
            return
        await show_banner_settings(client, message, user_id)

    @app.on_callback_query(filters.regex(r"banner_toggle_(\d+)"))
    async def toggle_banner_callback(client: Client, callback_query):
        user_id = int(callback_query.data.split("_")[2])
        if callback_query.from_user.id != user_id:
            await callback_query.answer("You are not authorized.", show_alert=True)
            return
        current_status = await get_banner_status(user_id)
        await set_banner_status(user_id, not current_status)
        await callback_query.message.delete()
        await show_banner_settings(client, callback_query.message, user_id)
        await callback_query.answer("Banner status updated.")

    @app.on_callback_query(filters.regex(r"banner_position_(\d+)"))
    async def position_banner_callback(client: Client, callback_query):
        user_id = int(callback_query.data.split("_")[2])
        if callback_query.from_user.id != user_id:
            await callback_query.answer("You are not authorized.", show_alert=True)
            return
        buttons = [
            [InlineKeyboardButton("First Page", callback_data=f"set_position_{user_id}_first")],
            [InlineKeyboardButton("Last Page", callback_data=f"set_position_{user_id}_last")],
            [InlineKeyboardButton("Both", callback_data=f"set_position_{user_id}_both")],
            [InlineKeyboardButton("Back", callback_data=f"banner_back_{user_id}")]
        ]
        await callback_query.message.edit_text(
            "📍 <b>Select Banner Position</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="html"
        )
        await callback_query.answer()

    @app.on_callback_query(filters.regex(r"set_position_(\d+)_(\w+)"))
    async def set_position_callback(client: Client, callback_query):
        user_id = int(callback_query.data.split("_")[2])
        position = callback_query.data.split("_")[3]
        if callback_query.from_user.id != user_id:
            await callback_query.answer("You are not authorized.", show_alert=True)
            return
        await set_banner_position(user_id, position)
        await callback_query.message.delete()
        await show_banner_settings(client, callback_query.message, user_id)
        await callback_query.answer(f"Banner position set to {position}.")

    @app.on_callback_query(filters.regex(r"banner_image_(\d+)"))
    async def banner_image_callback(client: Client, callback_query):
        user_id = int(callback_query.data.split("_")[2])
        if callback_query.from_user.id != user_id:
            await callback_query.answer("You are not authorized.", show_alert=True)
            return
        banner_image = await get_banner_image(user_id)
        buttons = [
            [InlineKeyboardButton("Upload Banner Image", callback_data=f"upload_banner_{user_id}")]
        ]
        if banner_image:
            buttons.append([
                InlineKeyboardButton("Remove Banner", callback_data=f"remove_banner_{user_id}"),
                InlineKeyboardButton("Change Banner", callback_data=f"upload_banner_{user_id}")
            ])
        buttons.append([InlineKeyboardButton("Back", callback_data=f"banner_back_{user_id}")])
        await callback_query.message.edit_text(
            "🖼️ <b>Manage Banner Image</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="html"
        )
        await callback_query.answer()

    @app.on_callback_query(filters.regex(r"upload_banner_(\d+)"))
    async def upload_banner_callback(client: Client, callback_query):
        user_id = int(callback_query.data.split("_")[2])
        if callback_query.from_user.id != user_id:
            await callback_query.answer("You are not authorized.", show_alert=True)
            return
        await callback_query.message.edit_text(
            "📷 Please send an image to set as your banner. You have 60 seconds.",
            parse_mode="html"
        )
        try:
            image_msg = await client.listen(
                callback_query.message.chat.id,
                filters=filters.photo | filters.document & filters.create(
                    lambda _, __, m: m.document and m.document.mime_type.startswith("image/")
                ),
                timeout=60
            )
            with tempfile.TemporaryDirectory() as temp_dir:
                banner_path = os.path.join(temp_dir, f"banner_{user_id}.jpg")
                await image_msg.download(banner_path)
                Image.open(banner_path).convert("RGB").save(banner_path, "JPEG")
                persistent_path = os.path.join("banners", f"{user_id}.jpg")
                os.makedirs("banners", exist_ok=True)
                shutil.copy(banner_path, persistent_path)
                await set_banner_image(user_id, persistent_path)
                await image_msg.reply_text("✅ Banner image set successfully!", parse_mode="html")
                await callback_query.message.delete()
                await show_banner_settings(client, callback_query.message, user_id)
        except asyncio.TimeoutError:
            await callback_query.message.edit_text("⏰ Timeout: No image received within 60 seconds.", parse_mode="html")
        except Exception as e:
            await callback_query.message.edit_text(f"❌ Error setting banner: {e}", parse_mode="html")

    @app.on_callback_query(filters.regex(r"remove_banner_(\d+)"))
    async def remove_banner_callback(client: Client, callback_query):
        user_id = int(callback_query.data.split("_")[2])
        if callback_query.from_user.id != user_id:
            await callback_query.answer("You are not authorized.", show_alert=True)
            return
        banner_path = await get_banner_image(user_id)
        if banner_path:
            await delete_banner_image(user_id)
            if os.path.exists(banner_path):
                try:
                    os.remove(banner_path)
                except:
                    pass
        await callback_query.message.delete()
        await show_banner_settings(client, callback_query.message, user_id)
        await callback_query.answer("Banner image removed.")

    @app.on_callback_query(filters.regex(r"banner_back_(\d+)"))
    async def banner_back_callback(client: Client, callback_query):
        user_id = int(callback_query.data.split("_")[2])
        if callback_query.from_user.id != user_id:
            await callback_query.answer("You are not authorized.", show_alert=True)
            return
        await callback_query.message.delete()
        await show_banner_settings(client, callback_query.message, user_id)
        await callback_query.answer()

    @app.on_message(filters.private & filters.command("addautho_user") & filters.user(Config.ADMIN))
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
                f'**Authorised Users Added ✅**\n<blockquote>`{" ".join(ids)}`</blockquote>',
                parse_mode="html"
            )
        else:
            await message.reply_text(
                "**INVALID USE OF COMMAND:**\n"
                "<blockquote>**➪ Check if the command is empty OR the added ID should be correct (10 digit numbers)**</blockquote>",
                parse_mode="html"
            )

    @app.on_message(filters.private & filters.command("delautho_user") & filters.user(Config.ADMIN))
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
                f'**Deleted Authorised Users 🆑**\n<blockquote>`{" ".join(ids)}`</blockquote>',
                parse_mode="html"
            )
        else:
            await message.reply_text(
                "**INVALID USE OF COMMAND:**\n"
                "<blockquote>**➪ Check if the command is empty OR the added ID should be correct (10 digit numbers)**</blockquote>",
                parse_mode="html"
            )

    @app.on_message(filters.private & filters.command("autho_users") & filters.user(Config.ADMIN))
    async def authorise_user_list(client: Client, message: Message):
        autho_users = await get_all_autho_users()
        if autho_users:
            autho_users_str = "\n".join(map(str, autho_users))
            await message.reply_text(
                f"🚻 **AUTHORIZED USERS:** 🌀\n\n`{autho_users_str}`",
                parse_mode="html"
            )
        else:
            await message.reply_text("No authorized users found.", parse_mode="html")

    @app.on_message(filters.private & filters.command("check_autho"))
    async def check_authorise_user(client: Client, message: Message):
        user_id = message.from_user.id
        check = await is_autho_user_exist(user_id)
        if check:
            await message.reply_text(
                "**Yes, You are an Authorised user 🟢**\n"
                "<blockquote>You can send files to Rename, Convert to PDF/CBZ, or Set Thumbnails/Banners.</blockquote>",
                parse_mode="html"
            )
        else:
            await message.reply_text(
                f"**Nope, You are not an Authorised user 🔴**\n"
                f"<blockquote>You can't send files or set thumbnails/banners.</blockquote>\n"
                f"**Contact {Config.SUPPORT_CHAT} to get authorized.**",
                parse_mode="html"
            )

    @app.on_message(filters.private & filters.command("set_thumb"))
    async def set_thumbnail_handler(client: Client, message: Message):
        user_id = message.from_user.id
        check = await is_autho_user_exist(user_id) or user_id in Config.ADMIN
        if not check:
            await message.reply_text(
                f"<b>⚠️ You are not authorized to set a thumbnail ⚠️</b>\n"
                f"<blockquote>Contact {Config.SUPPORT_CHAT} to get authorized.</blockquote>",
                parse_mode="html"
            )
            return
        await message.reply_text(
            "📷 Please send an image to set as your thumbnail. You have 30 seconds.",
            parse_mode="html"
        )
        try:
            image_msg = await client.listen(
                message.chat.id,
                filters=filters.photo | filters.document & filters.create(
                    lambda _, __, m: m.document and m.document.mime_type.startswith("image/")
                ),
                timeout=30
            )
            with tempfile.TemporaryDirectory() as temp_dir:
                thumbnail_path = os.path.join(temp_dir, f"thumbnail_{user_id}.jpg")
                await image_msg.download(thumbnail_path)
                Image.open(thumbnail_path).convert("RGB").save(thumbnail_path, "JPEG")
                persistent_path = os.path.join("thumbnails", f"{user_id}.jpg")
                os.makedirs("thumbnails", exist_ok=True)
                shutil.copy(thumbnail_path, persistent_path)
                await set_thumbnail(user_id, persistent_path)
                await message.reply_text("✅ Thumbnail set successfully!", parse_mode="html")
        except asyncio.TimeoutError:
            await message.reply_text("⏰ Timeout: No image received within 30 seconds.", parse_mode="html")
        except Exception as e:
            await message.reply_text(f"❌ Error setting thumbnail: {e}", parse_mode="html")

    @app.on_message(filters.private & filters.command("see_thumb"))
    async def see_thumbnail_handler(client: Client, message: Message):
        user_id = message.from_user.id
        check = await is_autho_user_exist(user_id) or user_id in Config.ADMIN
        if not check:
            await message.reply_text(
                f"<b>⚠️ You are not authorized to view thumbnails ⚠️</b>\n"
                f"<blockquote>Contact {Config.SUPPORT_CHAT} to get authorized.</blockquote>",
                parse_mode="html"
            )
            return
        thumbnail_path = await get_thumbnail(user_id)
        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                await message.reply_photo(
                    photo=thumbnail_path,
                    caption="📷 This is your current thumbnail.",
                    parse_mode="html"
                )
            except Exception as e:
                await message.reply_text(f"❌ Error displaying thumbnail: {e}", parse_mode="html")
        else:
            await message.reply_text("🚫 No thumbnail set.", parse_mode="html")

    @app.on_message(filters.private & filters.command("del_thumb"))
    async def delete_thumbnail_handler(client: Client, message: Message):
        user_id = message.from_user.id
        check = await is_autho_user_exist(user_id) or user_id in Config.ADMIN
        if not check:
            await message.reply_text(
                f"<b>⚠️ You are not authorized to delete thumbnails ⚠️</b>\n"
                f"<blockquote>Contact {Config.SUPPORT_CHAT} to get authorized.</blockquote>",
                parse_mode="html"
            )
            return
        thumbnail_path = await get_thumbnail(user_id)
        if thumbnail_path:
            await delete_thumbnail(user_id)
            if os.path.exists(thumbnail_path):
                try:
                    os.remove(thumbnail_path)
                except:
                    pass
            await message.reply_text("🗑️ Thumbnail deleted successfully!", parse_mode="html")
        else:
            await message.reply_text("🚫 No thumbnail to delete.", parse_mode="html")

    @app.on_message(filters.private & filters.document & ~filters.regex(r"\.zip$"))
    async def handle_non_zip_file(client: Client, message: Message):
        user_id = message.from_user.id
        check = await is_autho_user_exist(user_id)
        if not check:
            await message.reply_text(
                f"<b>⚠️ You are not an Authorised User ⚠️</b>\n"
                f"<blockquote>Contact {Config.SUPPORT_CHAT} to get authorized.</blockquote>",
                parse_mode="html"
            )
            return
        file_name = message.document.file_name.lower()
        if file_name.endswith((".pdf", ".cbz", ".epub")):
            buttons = [
                [InlineKeyboardButton("Add Banner 📄", callback_data=f"add_banner_{message.message_id}")],
                [InlineKeyboardButton("Close ❌", callback_data="close")]
            ]
            await message.reply_text(
                "File received! Choose an option below:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="html"
            )

    @app.on_callback_query(filters.regex(r"add_banner_(\d+)"))
    async def add_banner_callback(client: Client, callback_query):
        user_id = callback_query.from_user.id
        message_id = int(callback_query.data.split("_")[2])
        check = await is_autho_user_exist(user_id)
        if not check:
            await callback_query.answer("You are not authorized.", show_alert=True)
            return
        message = callback_query.message.reply_to_message
        if not message or not message.document:
            await callback_query.answer("No document found.", show_alert=True)
            return
        document = message.document
        file_name = document.file_name.lower()
        if not file_name.endswith((".pdf", ".cbz", ".epub")):
            await callback_query.answer("Unsupported file format.", show_alert=True)
            return
        await callback_query.message.edit_text("📂 Processing your file...")
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, document.file_name)
            output_path = os.path.join(temp_dir, f"modified_{document.file_name}")
            try:
                await message.download(input_path)
                banner_status = await get_banner_status(user_id)
                if not banner_status:
                    await callback_query.message.edit_text("❌ Banner mode is disabled. Enable it with /banner.")
                    return
                banner_image = await get_banner_image(user_id)
                if not banner_image:
                    await callback_query.message.edit_text("❌ No banner image set. Set one with /banner.")
                    return
                banner_url = await get_banner_url(user_id)
                banner_position = await get_banner_position(user_id)
                banner_pdf = create_banner_pdf(banner_image, banner_url)
                if file_name.endswith(".pdf"):
                    add_banner_to_pdf(input_path, output_path, banner_pdf, banner_position)
                elif file_name.endswith(".cbz"):
                    with zipfile.ZipFile(input_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                    image_files = natural_sort([
                        os.path.join(temp_dir, f) for f in os.listdir(temp_dir)
                        if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".img"))
                    ])
                    await generate_cbz(image_files, output_path, banner_image, banner_position)
                elif file_name.endswith(".epub"):
                    add_banner_to_epub(input_path, output_path, banner_image, banner_position)
                await client.send_document(
                    chat_id=message.chat.id,
                    document=output_path,
                    caption=f"Here is your modified file: {os.path.basename(output_path)}",
                    reply_to_message_id=message_id
                )
                await callback_query.message.edit_text("✅ File processed with banner!")
            except Exception as e:
                await callback_query.message.edit_text(f"❌ Error processing file: {e}")

    @app.on_callback_query(filters.regex("close"))
    async def handle_close_callback(client: Client, callback_query):
        await callback_query.message.delete()
        await callback_query.answer("Message closed.")
