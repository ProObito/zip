import os
import io
import zipfile
from PyPDF2 import PdfReader, PdfWriter
from pyrogram import Client, filters
from helper.database import db

TEMP_DIR = "temp"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)


async def get_thumb(bot, user_id):
    """Fetch thumbnail from DB or reuse"""
    thumb = await db.get_thumbnail(user_id)
    thumb_path = None
    if thumb:
        try:
            thumb_path = await bot.download_media(thumb)
        except Exception:
            thumb_path = None
    return thumb_path


# ================== ADD PASSWORD (PROTECT PDF) =====================
@Client.on_message(filters.command("addpass"))
async def addpass_cmd(bot, message):
    user_id = message.from_user.id
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("📄 Reply to a PDF file to add a password.")

    pdf_msg = message.reply_to_message
    pdf_path = await bot.download_media(pdf_msg)

    await message.reply("🔐 Send the password you want to set (within 60 seconds):")
    try:
        pwd_msg = await bot.wait_for_message(filters=filters.user(user_id), timeout=60)
        password = pwd_msg.text.strip()
    except Exception:
        return await message.reply("❌ Timeout. No password received.")

    try:
        reader = PdfReader(pdf_path)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.encrypt(password)

        out_path = os.path.join(TEMP_DIR, "protected.pdf")
        with open(out_path, "wb") as f:
            writer.write(f)

        thumb_path = await get_thumb(bot, user_id)

        await message.reply_document(
            out_path,
            caption=f"✅ Password added successfully.\n🔑 Password: `{password}`",
            thumb=thumb_path,
        )
    except Exception as e:
        await message.reply(f"❌ Error: {e}")
    finally:
        for f in [pdf_path, out_path]:
            if f and os.path.exists(f):
                os.remove(f)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)


# ================== REMOVE PASSWORD (UNPROTECT PDF) =====================
@Client.on_message(filters.command("removepass"))
async def removepass_cmd(bot, message):
    user_id = message.from_user.id
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("📄 Reply to a password-protected PDF to remove its password.")

    pdf_msg = message.reply_to_message
    pdf_path = await bot.download_media(pdf_msg)

    await message.reply("🔓 Send the current password for this PDF:")
    try:
        pwd_msg = await bot.wait_for_message(filters=filters.user(user_id), timeout=60)
        password = pwd_msg.text.strip()
    except Exception:
        return await message.reply("❌ Timeout. No password received.")

    try:
        reader = PdfReader(pdf_path)
        if reader.is_encrypted:
            reader.decrypt(password)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        out_path = os.path.join(TEMP_DIR, "unprotected.pdf")
        with open(out_path, "wb") as f:
            writer.write(f)

        thumb_path = await get_thumb(bot, user_id)

        await message.reply_document(
            out_path,
            caption="✅ Password removed successfully.",
            thumb=thumb_path,
        )
    except Exception as e:
        await message.reply(f"❌ Error: {e}")
    finally:
        for f in [pdf_path, out_path]:
            if f and os.path.exists(f):
                os.remove(f)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)


# ================== REMOVE PAGE =====================
@Client.on_message(filters.command("removepage"))
async def remove_page_cmd(bot, message):
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("📄 Reply to a PDF and use `/removepage <page_number>`")

    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return await message.reply("⚠️ Usage: `/removepage 2`")

    page_to_remove = int(args[1]) - 1
    pdf_path = await bot.download_media(message.reply_to_message)

    try:
        reader = PdfReader(pdf_path)
        writer = PdfWriter()

        for i, page in enumerate(reader.pages):
            if i != page_to_remove:
                writer.add_page(page)

        out_path = os.path.join(TEMP_DIR, "page_removed.pdf")
        with open(out_path, "wb") as f:
            writer.write(f)

        thumb_path = await get_thumb(bot, message.from_user.id)

        await message.reply_document(
            out_path, caption=f"🗑 Removed page {args[1]}", thumb=thumb_path
        )
    except Exception as e:
        await message.reply(f"❌ Error: {e}")
    finally:
        for f in [pdf_path, out_path]:
            if f and os.path.exists(f):
                os.remove(f)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)


# ================== ADD PAGE =====================
@Client.on_message(filters.command("addpage"))
async def add_page_cmd(bot, message):
    user_id = message.from_user.id
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("📄 Reply to a PDF file where you want to add a page.")

    await message.reply("📎 Send the page (PDF) you want to add:")
    try:
        page_msg = await bot.wait_for_message(filters=filters.user(user_id) & filters.document, timeout=60)
        new_page_path = await bot.download_media(page_msg)
    except Exception:
        return await message.reply("❌ Timeout or invalid file.")

    await message.reply("📄 Send the page number where you want to insert it:")
    try:
        num_msg = await bot.wait_for_message(filters=filters.user(user_id), timeout=60)
        page_number = int(num_msg.text.strip()) - 1
    except Exception:
        return await message.reply("❌ Invalid page number.")

    original_pdf = await bot.download_media(message.reply_to_message)
    try:
        reader = PdfReader(original_pdf)
        writer = PdfWriter()
        new_page_reader = PdfReader(new_page_path)

        for i in range(len(reader.pages)):
            if i == page_number:
                writer.add_page(new_page_reader.pages[0])
            writer.add_page(reader.pages[i])

        out_path = os.path.join(TEMP_DIR, "page_added.pdf")
        with open(out_path, "wb") as f:
            writer.write(f)

        thumb_path = await get_thumb(bot, user_id)

        await message.reply_document(out_path, caption=f"📘 Page added at {page_number + 1}", thumb=thumb_path)
    except Exception as e:
        await message.reply(f"❌ Error: {e}")
    finally:
        for f in [original_pdf, new_page_path, out_path]:
            if f and os.path.exists(f):
                os.remove(f)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)


# ================== EXTRACT ALL PAGES =====================
@Client.on_message(filters.command("extractall"))
async def extract_all_cmd(bot, message):
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("📄 Reply to a PDF to extract all pages as individual PDFs.")

    pdf_path = await bot.download_media(message.reply_to_message)
    reader = PdfReader(pdf_path)
    zip_path = os.path.join(TEMP_DIR, "extracted_pages.zip")

    with zipfile.ZipFile(zip_path, "w") as zipf:
        for i, page in enumerate(reader.pages):
            writer = PdfWriter()
            writer.add_page(page)
            page_file = os.path.join(TEMP_DIR, f"page_{i+1}.pdf")
            with open(page_file, "wb") as f:
                writer.write(f)
            zipf.write(page_file, f"page_{i+1}.pdf")
            os.remove(page_file)

    thumb_path = await get_thumb(bot, message.from_user.id)

    await message.reply_document(
        zip_path,
        caption="✅ All pages extracted successfully.",
        thumb=thumb_path,
    )

    for f in [pdf_path, zip_path]:
        if f and os.path.exists(f):
            os.remove(f)
    if thumb_path and os.path.exists(thumb_path):
        os.remove(thumb_path)
