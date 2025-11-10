import os
import asyncio
import pypandoc
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from helper.database import get_thumbnail, save_thumbnail, delete_thumbnail

# Track user state
convert_mode = {}
user_file = {}
user_steps = {}
convert_data = {}

# ==============================
# 📦 /convert
# ==============================
@Client.on_message(filters.command("convert") & filters.private)
async def convert_command(client: Client, message: Message):
    uid = message.from_user.id
    convert_mode[uid] = True
    user_steps[uid] = "waiting_file"
    convert_data[uid] = {}
    await message.reply_text(
        "📁 **Conversion Mode Activated!**\n\n"
        "➡️ Send any supported document (e.g., `.pdf`, `.epub`, `.docx`, `.txt`, `.zip`...)\n"
        "➡️ Then select which format to convert it to.\n\n"
        "Type `/cancel` anytime to stop."
    )

# ==============================
# 📄 Collect file
# ==============================
@Client.on_message(filters.document & filters.private)
async def collect_file(client: Client, message: Message):
    uid = message.from_user.id
    if not convert_mode.get(uid) or user_steps.get(uid) != "waiting_file":
        return

    file = message.document
    filename = file.file_name
    filepath = f"downloads/{uid}_{filename}"

    msg = await message.reply_text(f"⬇️ Downloading **{filename}** ...")
    await client.download_media(message, filepath)
    await msg.edit_text(f"✅ File downloaded: **{filename}**")

    user_file[uid] = filepath
    user_steps[uid] = "waiting_format"

    # Show inline format options
    buttons = [
        [
            InlineKeyboardButton("📄 PDF", callback_data=f"to_pdf"),
            InlineKeyboardButton("📚 EPUB", callback_data=f"to_epub"),
        ],
        [
            InlineKeyboardButton("📝 DOCX", callback_data=f"to_docx"),
            InlineKeyboardButton("📜 TXT", callback_data=f"to_txt"),
        ],
        [
            InlineKeyboardButton("📦 ZIP", callback_data=f"to_zip"),
        ]
    ]

    await message.reply_text(
        "🔽 **Choose the format you want to convert to:**",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ==============================
# 🎛️ Handle inline format buttons
# ==============================
@Client.on_callback_query(filters.regex("^to_"))
async def handle_format_selection(client: Client, callback_query):
    uid = callback_query.from_user.id
    if not convert_mode.get(uid) or user_steps.get(uid) != "waiting_format":
        return await callback_query.answer("⚠️ No active conversion!", show_alert=True)

    fmt = callback_query.data.replace("to_", "")
    convert_data[uid]["format"] = fmt
    user_steps[uid] = "waiting_name"
    await callback_query.message.delete()
    await callback_query.message.reply_text("📝 Send a **new name** for the converted file (without extension):")

# ==============================
# ⚙️ Handle name
# ==============================
@Client.on_message(filters.text & filters.private)
async def handle_name(client: Client, message: Message):
    uid = message.from_user.id
    if not convert_mode.get(uid):
        return

    if user_steps.get(uid) == "waiting_name":
        name = message.text.strip().replace("/", "").replace("\\", "")
        if not name:
            return await message.reply_text("❌ Invalid name. Try again.")
        convert_data[uid]["name"] = name

        m = await message.reply_text("⚙️ Starting conversion...")
        await convert_and_send(client, message, m)

# ==============================
# 🔄 Convert & Send
# ==============================
async def convert_and_send(client: Client, message: Message, m: Message):
    uid = message.from_user.id
    src_path = user_file.get(uid)
    target_fmt = convert_data[uid].get("format")
    name = convert_data[uid].get("name", f"converted_{uid}")
    if not src_path or not target_fmt:
        await m.delete()
        return await message.reply_text("❌ Missing file or format.")

    output_path = f"downloads/{name}.{target_fmt}"
    thumb_path = await get_thumbnail(uid)

    try:
        # Pandoc conversion
        text_content = ""
        with open(src_path, "r", encoding="utf-8", errors="ignore") as f:
            text_content = f.read()

        pypandoc.convert_text(
            text_content,
            target_fmt,
            format="auto",
            outputfile=output_path,
            extra_args=['--standalone']
        )

        # Send converted file with thumbnail
        try:
            await message.reply_document(
                document=output_path,
                thumb=thumb_path if (thumb_path and os.path.exists(thumb_path)) else None,
                caption=f"✅ **Converted Successfully!**\n📄 `{name}.{target_fmt}`"
            )
        except Exception:
            await message.reply_document(
                document=output_path,
                caption=f"✅ **Converted Successfully (No Thumbnail)**\n📄 `{name}.{target_fmt}`"
            )

        await m.delete()
    except Exception as e:
        await m.edit_text(f"❌ Conversion failed:\n`{e}`")
        await asyncio.sleep(5)
        await m.delete()
    finally:
        # Cleanup
        if os.path.exists(src_path):
            os.remove(src_path)
        if os.path.exists(output_path):
            os.remove(output_path)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)
        convert_mode.pop(uid, None)
        user_file.pop(uid, None)
        user_steps.pop(uid, None)
        convert_data.pop(uid, None)

# ==============================
# 🛑 /cancel
# ==============================
@Client.on_message(filters.command("cancel") & filters.private)
async def cancel_convert(client: Client, message: Message):
    uid = message.from_user.id
    if not convert_mode.get(uid):
        return await message.reply_text("ℹ️ No active conversion.")
    convert_mode.pop(uid, None)
    if uid in user_file and os.path.exists(user_file[uid]):
        os.remove(user_file[uid])
    user_file.pop(uid, None)
    user_steps.pop(uid, None)
    convert_data.pop(uid, None)
    await message.reply_text("🚫 Conversion cancelled and temp files cleared.")
