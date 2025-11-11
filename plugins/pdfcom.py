from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import os


# === Ghostscript Compression Function ===
def compress_pdf(input_path, output_path, quality="ebook"):
    """
    quality options: screen < ebook < printer < prepress
    """
    try:
        subprocess.run([
            "gs",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            f"-dPDFSETTINGS=/{quality}",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            f"-sOutputFile={output_path}",
            input_path
        ], check=True)
        return True
    except Exception as e:
        print("Ghostscript Error:", e)
        return False


# === User compression settings memory ===
user_mode = {}     # stores if user is in compdf mode
user_choice = {}   # stores selected compression level


# === /compdf Command ===
@Client.on_message(filters.command("compdf") & filters.private)
async def compdf_cmd(client: Client, message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton("📉 Light (≈2 MB smaller)", callback_data="compress_2"),
                InlineKeyboardButton("📦 Medium (≈4 MB smaller)", callback_data="compress_4")
            ],
            [
                InlineKeyboardButton("🧩 Strong (≈6 MB smaller)", callback_data="compress_6"),
                InlineKeyboardButton("💀 Ultra (≈8 MB smaller)", callback_data="compress_8")
            ]
        ]
    )
    await message.reply_text(
        "🧠 Choose compression strength:\n\nThen send me your PDF.",
        reply_markup=keyboard
    )
    user_mode[message.from_user.id] = True


# === Compression Level Selection ===
@Client.on_callback_query(filters.regex(r"compress_\d+"))
async def set_compression_level(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    level = int(query.data.split("_")[1])
    user_choice[uid] = level
    user_mode[uid] = True  # ensure mode is active
    await query.message.edit_text(f"✅ Compression level set: **{level} MB smaller**\nNow send your PDF file.")


# === Handle PDF ===
@Client.on_message(filters.document & filters.private)
async def handle_pdf(client: Client, message: Message):
    uid = message.from_user.id

    # check if user is in compression mode
    if uid not in user_mode or not user_mode[uid]:
        return await message.reply_text("ℹ️ Please use /compdf first to enable PDF compression mode.")

    if message.document.mime_type != "application/pdf":
        return await message.reply_text("❌ Please send a valid PDF file.")

    level = user_choice.get(uid, 4)  # default level = medium
    file_name = message.document.file_name or "input.pdf"
    input_pdf = f"downloads/{file_name}"
    output_pdf = f"downloads/compressed_{file_name}"

    msg = await message.reply_text("⬇️ Downloading your PDF...")
    await client.download_media(message, file_name=input_pdf)

    await msg.edit("⚙️ Compressing your PDF... please wait.")

    try:
        old_size = os.path.getsize(input_pdf)
        old_mb = old_size / (1024 * 1024)

        # compression strength mapping
        if level <= 2:
            quality = "printer"      # light
        elif level <= 4:
            quality = "ebook"        # medium
        elif level <= 6:
            quality = "screen"       # strong
        else:
            quality = "default"      # ultra

        ok = compress_pdf(input_pdf, output_pdf, quality=quality)
        if not ok:
            return await msg.edit("❌ Compression failed. Try again later.")

        new_size = os.path.getsize(output_pdf)
        new_mb = new_size / (1024 * 1024)
        reduction = round(old_mb - new_mb, 2)

        caption = (
            f"✅ **Compression Complete!**\n\n"
            f"📦 Original: {old_mb:.2f} MB\n"
            f"📉 Compressed: {new_mb:.2f} MB\n"
            f"💾 Reduced by: {reduction:.2f} MB"
        )

        await message.reply_document(document=output_pdf, caption=caption)
        await msg.delete()

    except Exception as e:
        await msg.edit(f"⚠️ Error: `{e}`")

    finally:
        # cleanup
        for path in [input_pdf, output_pdf]:
            if os.path.exists(path):
                os.remove(path)
        user_mode[uid] = False  # reset mode after one file
        if uid in user_choice:
            del user_choice[uid]

