import os
from PyPDF2 import PdfReader, PdfWriter
from pyrogram import Client, filters
from pyrogram.types import Message
from helper.database import get_thumbnail

TMP = "downloads"
os.makedirs(TMP, exist_ok=True)

# ======= GET SINGLE PAGE =======
@Client.on_message(filters.command("getpage") & filters.reply)
async def getpage_cmd(bot: Client, message: Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.reply("⚠️ Usage: `/getpage 3` (reply to PDF)")
    page_num = int(args[1])
    doc = message.reply_to_message.document
    if not doc or not doc.file_name.endswith(".pdf"):
        return await message.reply("❌ Reply to a PDF file.")
    file = await message.reply_to_message.download(file_name=os.path.join(TMP, f"{message.from_user.id}_{doc.file_name}"))
    out = os.path.join(TMP, f"page_{page_num}.pdf")

    try:
        reader = PdfReader(file)
        if page_num < 1 or page_num > len(reader.pages):
            return await message.reply("❌ Invalid page number.")
        writer = PdfWriter()
        writer.add_page(reader.pages[page_num - 1])
        with open(out, "wb") as f:
            writer.write(f)

        thumb = await get_thumbnail(message.from_user.id)
        await bot.send_document(message.chat.id, out, caption=f"✅ Extracted page {page_num}.", thumb=thumb)
    finally:
        os.remove(file)
        if os.path.exists(out):
            os.remove(out)


# ======= REMOVE PAGE =======
@Client.on_message(filters.command("removepage") & filters.reply)
async def removepage_cmd(bot: Client, message: Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.reply("⚠️ Usage: `/removepage 2` (reply to PDF)")
    page_num = int(args[1])
    doc = message.reply_to_message.document
    if not doc or not doc.file_name.endswith(".pdf"):
        return await message.reply("❌ Reply to a PDF file.")
    file = await message.reply_to_message.download(file_name=os.path.join(TMP, f"{message.from_user.id}_{doc.file_name}"))
    out = os.path.join(TMP, f"removed_{os.path.basename(file)}")

    try:
        reader = PdfReader(file)
        writer = PdfWriter()
        for i, page in enumerate(reader.pages):
            if i != page_num - 1:
                writer.add_page(page)
        with open(out, "wb") as f:
            writer.write(f)
        thumb = await get_thumbnail(message.from_user.id)
        await bot.send_document(message.chat.id, out, caption=f"✅ Removed page {page_num}.", thumb=thumb)
    finally:
        os.remove(file)
        if os.path.exists(out):
            os.remove(out)


# ======= ADD PAGE =======
@Client.on_message(filters.command("addpage") & filters.reply)
async def addpage_cmd(bot: Client, message: Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.reply("⚠️ Usage: `/addpage 3` (reply to PDF and send page PDF next)")
    pos = int(args[1])
    doc = message.reply_to_message.document
    if not doc or not doc.file_name.endswith(".pdf"):
        return await message.reply("❌ Reply to a PDF file first.")
    file = await message.reply_to_message.download(file_name=os.path.join(TMP, f"{message.from_user.id}_{doc.file_name}"))

    await message.reply("📄 Now send the new page (PDF format). You have 2 minutes.")
    try:
        new_msg = await bot.listen(message.chat.id, timeout=120)
    except asyncio.TimeoutError:
        return await message.reply("❌ Timeout. No new page received.")

    new_doc = new_msg.document
    if not new_doc or not new_doc.file_name.endswith(".pdf"):
        return await message.reply("❌ Only PDF pages are allowed.")
    new_file = await new_doc.download(file_name=os.path.join(TMP, f"new_{new_doc.file_name}"))
    out = os.path.join(TMP, f"added_{os.path.basename(file)}")

    reader = PdfReader(file)
    new_reader = PdfReader(new_file)
    writer = PdfWriter()

    for i, page in enumerate(reader.pages):
        if i == pos - 1:
            writer.add_page(new_reader.pages[0])
        writer.add_page(page)

    with open(out, "wb") as f:
        writer.write(f)
    thumb = await get_thumbnail(message.from_user.id)
    await bot.send_document(message.chat.id, out, caption=f"✅ Added new page at position {pos}.", thumb=thumb)
    os.remove(file)
    os.remove(new_file)
    os.remove(out)


# ======= REPLACE PAGE =======
@Client.on_message(filters.command("replacepage") & filters.reply)
async def replacepage_cmd(bot: Client, message: Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.reply("⚠️ Usage: `/replacepage 3` (reply to PDF and send new page next)")
    pos = int(args[1])
    doc = message.reply_to_message.document
    if not doc or not doc.file_name.endswith(".pdf"):
        return await message.reply("❌ Reply to a PDF file first.")
    file = await message.reply_to_message.download(file_name=os.path.join(TMP, f"{message.from_user.id}_{doc.file_name}"))

    await message.reply("📄 Now send the replacement page (PDF format). You have 2 minutes.")
    try:
        new_msg = await bot.listen(message.chat.id, timeout=120)
    except asyncio.TimeoutError:
        return await message.reply("❌ Timeout. No page received.")

    new_doc = new_msg.document
    if not new_doc or not new_doc.file_name.endswith(".pdf"):
        return await message.reply("❌ Only PDF pages are allowed.")
    new_file = await new_doc.download(file_name=os.path.join(TMP, f"replace_{new_doc.file_name}"))
    out = os.path.join(TMP, f"replaced_{os.path.basename(file)}")

    reader = PdfReader(file)
    new_reader = PdfReader(new_file)
    writer = PdfWriter()

    for i, page in enumerate(reader.pages):
        if i == pos - 1:
            writer.add_page(new_reader.pages[0])
        else:
            writer.add_page(page)

    with open(out, "wb") as f:
        writer.write(f)

    thumb = await get_thumbnail(message.from_user.id)
    await bot.send_document(message.chat.id, out, caption=f"✅ Replaced page {pos}.", thumb=thumb)
    os.remove(file)
    os.remove(new_file)
    os.remove(out)
