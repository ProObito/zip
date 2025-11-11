import os
import asyncio
import zipfile
from pyrogram import Client, filters
from pyrogram.types import Message
from PyPDF2 import PdfReader, PdfWriter
from helper.database import get_thumb

TEMP_DIR = "./downloads"
os.makedirs(TEMP_DIR, exist_ok=True)

user_waiting = {}  # store password waiting sessions


# ============ /addpass ==============
@Client.on_message(filters.command("addpass"))
async def addpass_cmd(bot, message: Message):
    user_id = message.from_user.id
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("📄 Reply to a PDF file to add password.")
    pdf_msg = message.reply_to_message
    pdf_path = await bot.download_media(pdf_msg)

    ask = await message.reply(
        "🔐 Send password for this PDF.\n"
        "⏳ You have **3 minutes**.\n"
        "❌ Type `cancel` to cancel."
    )
    user_waiting[user_id] = {"stage": "waiting_password", "pdf_path": pdf_path}

    try:
        for _ in range(180):  # wait up to 3 min
            await asyncio.sleep(1)
            if user_id not in user_waiting:
                raise asyncio.TimeoutError()
            if "password" in user_waiting[user_id]:
                break
        else:
            raise asyncio.TimeoutError()

        password = user_waiting[user_id]["password"]
        del user_waiting[user_id]

        if password.lower() == "cancel":
            await message.reply("🚫 Password setup cancelled.")
            os.remove(pdf_path)
            return

        reader = PdfReader(pdf_path)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.encrypt(password)

        out_path = os.path.join(TEMP_DIR, "protected.pdf")
        with open(out_path, "wb") as f:
            writer.write(f)

        thumb = await get_thumb(bot, user_id)
        await message.reply_document(
            out_path,
            caption=f"✅ Password added.\n🔑 `{password}`",
            thumb=thumb,
        )
    except asyncio.TimeoutError:
        if user_id in user_waiting:
            del user_waiting[user_id]
        await message.reply("❌ Timeout. No password received in 3 minutes.")
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        if os.path.exists(os.path.join(TEMP_DIR, "protected.pdf")):
            os.remove(os.path.join(TEMP_DIR, "protected.pdf"))


# ============ listener for password ============
@Client.on_message(filters.text & filters.private)
async def password_listener(bot, message: Message):
    uid = message.from_user.id
    if uid in user_waiting and user_waiting[uid]["stage"] == "waiting_password":
        user_waiting[uid]["password"] = message.text.strip()


# ============ /removepass ==============
@Client.on_message(filters.command("removepass"))
async def removepass_cmd(bot, message: Message):
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("📄 Reply to a locked PDF.")
    pdf_path = await bot.download_media(message.reply_to_message)

    await message.reply("🔓 Send PDF password to remove lock. You have **3 minutes**.")
    uid = message.from_user.id
    user_waiting[uid] = {"stage": "waiting_removepass"}

    try:
        for _ in range(180):
            await asyncio.sleep(1)
            if uid not in user_waiting:
                raise asyncio.TimeoutError()
            if "password" in user_waiting[uid]:
                break
        else:
            raise asyncio.TimeoutError()
        password = user_waiting[uid]["password"]
        del user_waiting[uid]

        reader = PdfReader(pdf_path)
        if reader.is_encrypted:
            reader.decrypt(password)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        out_path = os.path.join(TEMP_DIR, "unlocked.pdf")
        with open(out_path, "wb") as f:
            writer.write(f)

        thumb = await get_thumb(bot, uid)
        await message.reply_document(out_path, caption="✅ Password removed.", thumb=thumb)
    except asyncio.TimeoutError:
        await message.reply("❌ Timeout. No password received in 3 minutes.")
    except Exception as e:
        await message.reply(f"⚠️ Error: {e}")
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        if os.path.exists(os.path.join(TEMP_DIR, "unlocked.pdf")):
            os.remove(os.path.join(TEMP_DIR, "unlocked.pdf"))


# ============ /removepage ==============
@Client.on_message(filters.command("removepage"))
async def removepage_cmd(bot, message: Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return await message.reply("📄 Use: `/removepage 2` replying to a PDF")
    page_no = int(args[1]) - 1
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("📄 Reply to a PDF file.")
    pdf_path = await bot.download_media(message.reply_to_message)

    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i != page_no:
            writer.add_page(page)
    out_path = os.path.join(TEMP_DIR, "removed_page.pdf")
    with open(out_path, "wb") as f:
        writer.write(f)
    thumb = await get_thumb(bot, message.from_user.id)
    await message.reply_document(out_path, caption="🗑️ Page removed.", thumb=thumb)
    os.remove(pdf_path)
    os.remove(out_path)


# ============ /addpage ==============
@Client.on_message(filters.command("addpage"))
async def addpage_cmd(bot, message: Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return await message.reply("📄 Use: `/addpage 2` replying to main PDF.")
    page_no = int(args[1]) - 1
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("📄 Reply to the main PDF first.")
    pdf_path = await bot.download_media(message.reply_to_message)
    await message.reply("📄 Now reply to me with the PDF page to insert.")
    uid = message.from_user.id
    user_waiting[uid] = {"stage": "waiting_addpage", "pdf_path": pdf_path, "page_no": page_no}


@Client.on_message(filters.document & filters.private)
async def addpage_listener(bot, message: Message):
    uid = message.from_user.id
    if uid in user_waiting and user_waiting[uid]["stage"] == "waiting_addpage":
        insert_pdf = await bot.download_media(message)
        pdf_path = user_waiting[uid]["pdf_path"]
        page_no = user_waiting[uid]["page_no"]
        del user_waiting[uid]

        reader = PdfReader(pdf_path)
        insert_reader = PdfReader(insert_pdf)
        writer = PdfWriter()
        for i, page in enumerate(reader.pages):
            if i == page_no:
                writer.add_page(insert_reader.pages[0])
            writer.add_page(page)
        out_path = os.path.join(TEMP_DIR, "page_added.pdf")
        with open(out_path, "wb") as f:
            writer.write(f)
        thumb = await get_thumb(bot, uid)
        await message.reply_document(out_path, caption="➕ Page added.", thumb=thumb)
        os.remove(pdf_path)
        os.remove(insert_pdf)
        os.remove(out_path)


# ============ /replacepage ==============
@Client.on_message(filters.command("replacepage"))
async def replacepage_cmd(bot, message: Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return await message.reply("📄 Use: `/replacepage 3` replying to main PDF.")
    page_no = int(args[1]) - 1
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("📄 Reply to main PDF first.")
    pdf_path = await bot.download_media(message.reply_to_message)
    await message.reply("📄 Now reply with replacement page PDF.")
    uid = message.from_user.id
    user_waiting[uid] = {"stage": "waiting_replacepage", "pdf_path": pdf_path, "page_no": page_no}


@Client.on_message(filters.document & filters.private)
async def replace_listener(bot, message: Message):
    uid = message.from_user.id
    if uid in user_waiting and user_waiting[uid]["stage"] == "waiting_replacepage":
        replace_pdf = await bot.download_media(message)
        pdf_path = user_waiting[uid]["pdf_path"]
        page_no = user_waiting[uid]["page_no"]
        del user_waiting[uid]

        reader = PdfReader(pdf_path)
        replace_reader = PdfReader(replace_pdf)
        writer = PdfWriter()
        for i, page in enumerate(reader.pages):
            if i == page_no:
                writer.add_page(replace_reader.pages[0])
            else:
                writer.add_page(page)
        out_path = os.path.join(TEMP_DIR, "page_replaced.pdf")
        with open(out_path, "wb") as f:
            writer.write(f)
        thumb = await get_thumb(bot, uid)
        await message.reply_document(out_path, caption="♻️ Page replaced.", thumb=thumb)
        os.remove(pdf_path)
        os.remove(replace_pdf)
        os.remove(out_path)


# ============ /extractall ==============
@Client.on_message(filters.command("extractall"))
async def extract_all_cmd(bot, message: Message):
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("📄 Reply to a PDF to extract all pages.")
    pdf_path = await bot.download_media(message.reply_to_message)
    reader = PdfReader(pdf_path)
    zip_path = os.path.join(TEMP_DIR, "pages.zip")

    with zipfile.ZipFile(zip_path, "w") as zipf:
        for i, page in enumerate(reader.pages, 1):
            writer = PdfWriter()
            writer.add_page(page)
            page_file = os.path.join(TEMP_DIR, f"page_{i}.pdf")
            with open(page_file, "wb") as f:
                writer.write(f)
            zipf.write(page_file, f"page_{i}.pdf")
            os.remove(page_file)

    thumb = await get_thumb(bot, message.from_user.id)
    await message.reply_document(zip_path, caption="✅ All pages extracted.", thumb=thumb)
    os.remove(pdf_path)
    os.remove(zip_path)
