import os
import tempfile
import zipfile
import pypandoc
from PyPDF2 import PdfReader, PdfWriter
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from helper.database import get_thumbnail, get_user_data

# 🔹 Auto-install Pandoc if missing (Heroku safe)
def ensure_pandoc():
    try:
        pypandoc.get_pandoc_version()
    except OSError:
        print("[INFO] Pandoc not found. Downloading...")
        pypandoc.download_pandoc()
        print("[INFO] Pandoc installed successfully!")

ensure_pandoc()

# ─────────────────────────────────────────────
# ⚙️ /convert Command
# ─────────────────────────────────────────────
@Client.on_message(filters.command("convert") & filters.reply)
async def convert_file(bot, message):
    replied = message.reply_to_message
    if not replied.document:
        return await message.reply("📂 Reply to a valid document to convert it.")

    file = await replied.download()
    base, ext = os.path.splitext(file)
    ext = ext.lower()

    # 🔘 Inline format buttons
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📘 To PDF", callback_data=f"to_pdf|{file}")],
        [InlineKeyboardButton("📚 To EPUB", callback_data=f"to_epub|{file}")],
        [InlineKeyboardButton("📦 To ZIP", callback_data=f"to_zip|{file}")],
        [InlineKeyboardButton("🖼️ To CBZ", callback_data=f"to_cbz|{file}")],
    ])

    await message.reply("📤 Choose a format to convert:", reply_markup=keyboard)

# ─────────────────────────────────────────────
# 🧩 Conversion Handler
# ─────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^to_(pdf|epub|zip|cbz)\|"))
async def handle_conversion(bot, query):
    _, target_fmt, file = query.data.split("_", 1)[1].split("|", 1)
    msg = await query.message.edit_text(f"⚙️ Converting to **{target_fmt.upper()}**...")

    user_id = query.from_user.id
    thumb_path = await get_thumbnail(user_id)

    output_path = f"{os.path.splitext(file)[0]}.{target_fmt}"

    try:
        if target_fmt in ["pdf", "epub"]:
            pypandoc.convert_file(file, target_fmt, outputfile=output_path)
        elif target_fmt in ["zip", "cbz"]:
            with zipfile.ZipFile(output_path, "w") as zipf:
                zipf.write(file, os.path.basename(file))
        else:
            return await msg.edit_text("❌ Invalid format.")
    except Exception as e:
        return await msg.edit_text(f"❌ Conversion failed:\n`{e}`")

    caption = f"✅ Converted to **{target_fmt.upper()}**"
    await bot.send_document(
        query.message.chat.id,
        output_path,
        caption=caption,
        thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None
    )

    await msg.delete()
    os.remove(file)
    os.remove(output_path)

# ─────────────────────────────────────────────
# ✂️ /remove_page Command
# ─────────────────────────────────────────────
@Client.on_message(filters.command("remove_page") & filters.reply)
async def remove_page(bot, message):
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("📄 Reply to a PDF to remove a page.\nUsage: `/remove_page 3`")

    try:
        page_num = int(message.text.split(maxsplit=1)[1]) - 1
    except:
        return await message.reply("⚠️ Invalid page number.")

    file = await message.reply_to_message.download()
    output_file = tempfile.mktemp(suffix=".pdf")

    try:
        reader = PdfReader(file)
        writer = PdfWriter()

        for i in range(len(reader.pages)):
            if i != page_num:
                writer.add_page(reader.pages[i])

        with open(output_file, "wb") as f:
            writer.write(f)

        await message.reply_document(output_file, caption=f"🗑️ Page {page_num + 1} removed.")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")
    finally:
        os.remove(file)
        if os.path.exists(output_file):
            os.remove(output_file)

# ─────────────────────────────────────────────
# ➕ /add_page Command
# ─────────────────────────────────────────────
@Client.on_message(filters.command("add_page") & filters.reply)
async def add_page(bot, message):
    if len(message.command) < 2:
        return await message.reply("Usage: `/add_page 2` (reply to the PDF where page will be added)")

    try:
        page_num = int(message.command[1]) - 1
    except:
        return await message.reply("⚠️ Invalid page number.")

    replied = message.reply_to_message
    if not replied or not replied.document:
        return await message.reply("📄 Reply to a PDF file where you want to insert a page.")

    # Ask user to send page PDF
    await message.reply("📥 Now send the PDF page you want to insert (single page).")

    @bot.on_message(filters.document & filters.user(message.from_user.id))
    async def add_page_handler(bot, msg):
        new_page_file = await msg.download()
        main_file = await replied.download()
        output_file = tempfile.mktemp(suffix=".pdf")

        try:
            reader_main = PdfReader(main_file)
            reader_new = PdfReader(new_page_file)
            writer = PdfWriter()

            for i in range(len(reader_main.pages) + 1):
                if i == page_num:
                    writer.add_page(reader_new.pages[0])
                if i < len(reader_main.pages):
                    writer.add_page(reader_main.pages[i])

            with open(output_file, "wb") as f:
                writer.write(f)

            await bot.send_document(message.chat.id, output_file, caption=f"📄 Added new page at {page_num + 1}.")
        except Exception as e:
            await bot.send_message(message.chat.id, f"❌ Error: {e}")
        finally:
            os.remove(main_file)
            os.remove(new_page_file)
            if os.path.exists(output_file):
                os.remove(output_file)
