import os
import tempfile
import asyncio
import zipfile
from PyPDF2 import PdfReader, PdfWriter
from pyrogram import Client, filters
from pyrogram.types import Message
from helper.database import get_thumbnail

TMP = "downloads"
os.makedirs(TMP, exist_ok=True)

# ================= PASSWORD ADD =================
@Client.on_message(filters.command("passadd") & filters.reply)
async def passadd_cmd(bot: Client, message: Message):
    doc = message.reply_to_message.document
    if not doc or not doc.file_name.endswith(".pdf"):
        return await message.reply("❌ Reply to a PDF file to add password.")
    file = await message.reply_to_message.download(file_name=os.path.join(TMP, f"{message.from_user.id}_{doc.file_name}"))

    await message.reply("🔐 Send password for this PDF (type `cancel` to abort). You have 3 minutes.")
    try:
        pwd_msg = await bot.listen(message.chat.id, timeout=180)
    except asyncio.TimeoutError:
        return await message.reply("❌ Timeout. No password received.")

    if not pwd_msg.text or pwd_msg.text.lower() == "cancel":
        return await message.reply("❌ Cancelled.")
    password = pwd_msg.text.strip()

    try:
        reader = PdfReader(file)
        writer = PdfWriter()
        for p in reader.pages:
            writer.add_page(p)
        writer.encrypt(password)

        out = os.path.join(TMP, f"protected_{os.path.basename(file)}")
        with open(out, "wb") as f:
            writer.write(f)

        thumb = await get_thumbnail(message.from_user.id)
        await bot.send_document(message.chat.id, out, caption="✅ Password added successfully.", thumb=thumb)
    except Exception as e:
        await message.reply(f"❌ Error: {e}")
    finally:
        try: os.remove(file)
        except: pass


# ================= PASSWORD REMOVE =================
@Client.on_message(filters.command("passremove") & filters.reply)
async def passremove_cmd(bot: Client, message: Message):
    doc = message.reply_to_message.document
    if not doc or not doc.file_name.endswith(".pdf"):
        return await message.reply("❌ Reply to a PDF file to remove password.")
    file = await message.reply_to_message.download(file_name=os.path.join(TMP, f"{message.from_user.id}_{doc.file_name}"))

    await message.reply("🔓 Send current password to unlock this PDF (type `cancel` to abort). You have 3 minutes.")
    try:
        pwd_msg = await bot.listen(message.chat.id, timeout=180)
    except asyncio.TimeoutError:
        return await message.reply("❌ Timeout. No password received.")

    if not pwd_msg.text or pwd_msg.text.lower() == "cancel":
        return await message.reply("❌ Cancelled.")
    password = pwd_msg.text.strip()

    try:
        reader = PdfReader(file)
        if reader.is_encrypted:
            reader.decrypt(password)
        writer = PdfWriter()
        for p in reader.pages:
            writer.add_page(p)

        out = os.path.join(TMP, f"unlocked_{os.path.basename(file)}")
        with open(out, "wb") as f:
            writer.write(f)

        thumb = await get_thumbnail(message.from_user.id)
        await bot.send_document(message.chat.id, out, caption="✅ Password removed successfully.", thumb=thumb)
    except Exception as e:
        await message.reply(f"❌ Error: {e}")
    finally:
        try: os.remove(file)
        except: pass


# ================= EXTRACT ALL PAGES =================
@Client.on_message(filters.command("extractall") & filters.reply)
async def extractall_cmd(bot: Client, message: Message):
    doc = message.reply_to_message.document
    if not doc:
        return await message.reply("❌ Reply to a PDF or CBZ/ZIP file.")

    file = await message.reply_to_message.download(file_name=os.path.join(TMP, f"{message.from_user.id}_{doc.file_name}"))
    ext = os.path.splitext(file)[1].lower().lstrip(".")
    thumb = await get_thumbnail(message.from_user.id)

    try:
        out_dir = tempfile.mkdtemp(prefix="extract_")
        if ext == "pdf":
            import fitz  # PyMuPDF
            pdf_doc = fitz.open(file)
            for i in range(len(pdf_doc)):
                page = pdf_doc.load_page(i)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # High-res
                pix.save(os.path.join(out_dir, f"page_{i+1}.png"))

        elif ext in ("cbz", "zip"):
            with zipfile.ZipFile(file, "r") as zf:
                zf.extractall(out_dir)
        else:
            return await message.reply("❌ Unsupported file type.")

        zip_path = os.path.join(TMP, f"extracted_{os.path.basename(file)}.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for fname in os.listdir(out_dir):
                zf.write(os.path.join(out_dir, fname), arcname=fname)

        await bot.send_document(message.chat.id, zip_path, caption="✅ Pages extracted successfully.", thumb=thumb)
    except Exception as e:
        await message.reply(f"❌ Error: {e}")
    finally:
        try: os.remove(file)
        except: pass
