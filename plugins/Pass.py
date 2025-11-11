import os
from pyrogram import Client, filters
from PyPDF2 import PdfReader, PdfWriter
from zipfile import ZipFile
from helper.database import db, get_thumbnail
from reportlab.pdfgen import canvas

# Helper functions for PDF operations
async def remove_page(pdf_path, page_num, output_path):
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    for i in range(len(reader.pages)):
        if i != page_num - 1:
            writer.add_page(reader.pages[i])
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path


async def add_page(pdf_path, page_num, output_path):
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    tmp_page = "temp_added_page.pdf"

    c = canvas.Canvas(tmp_page)
    c.drawString(250, 500, "New Added Page")
    c.save()

    add_reader = PdfReader(tmp_page)
    for i in range(len(reader.pages)):
        writer.add_page(reader.pages[i])
        if i == page_num - 1:
            writer.add_page(add_reader.pages[0])

    with open(output_path, "wb") as f:
        writer.write(f)
    os.remove(tmp_page)
    return output_path


async def extract_all(pdf_path, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    reader = PdfReader(pdf_path)
    for i, page in enumerate(reader.pages):
        writer = PdfWriter()
        writer.add_page(page)
        with open(f"{output_folder}/page_{i + 1}.pdf", "wb") as f:
            writer.write(f)
    return output_folder


# 🧩 Commands

@Client.on_message(filters.command("protect"))
async def protect_cmd(bot, message):
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply_text("Reply to a file to add password 🔒")

    user_id = message.from_user.id
    file = await message.reply_to_message.download()
    msg = await message.reply_text("🔐 Send the password to lock this file:")

    pwd_msg = await bot.listen(user_id)
    password = pwd_msg.text.strip()
    await msg.edit("🔄 Encrypting file...")

    out = f"downloads/protected_{message.reply_to_message.document.file_name}"
    reader = PdfReader(file)
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password)

    with open(out, "wb") as f:
        writer.write(f)

    thumb = await db.get_thumbnail(user_id)
    await message.reply_document(out, caption="✅ Password set successfully.", thumb=thumb)
    os.remove(file)
    os.remove(out)


@Client.on_message(filters.command("unprotect"))
async def unprotect_cmd(bot, message):
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply_text("Reply to a protected file 🔓")

    user_id = message.from_user.id
    file = await message.reply_to_message.download()
    msg = await message.reply_text("🔑 Send the password to unlock file:")

    pwd_msg = await bot.listen(user_id)
    password = pwd_msg.text.strip()
    await msg.edit("🔄 Decrypting file...")

    out = f"downloads/unlocked_{message.reply_to_message.document.file_name}"
    reader = PdfReader(file)
    if reader.is_encrypted:
        reader.decrypt(password)

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    with open(out, "wb") as f:
        writer.write(f)

    thumb = await db.get_thumbnail(user_id)
    await message.reply_document(out, caption="✅ Password removed successfully.", thumb=thumb)
    os.remove(file)
    os.remove(out)


@Client.on_message(filters.command("removepage"))
async def remove_page_cmd(bot, message):
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply_text("Reply to a PDF and enter page number to remove 📄❌")

    user_id = message.from_user.id
    file = await message.reply_to_message.download()
    msg = await message.reply_text("📄 Send page number to remove:")
    pg = await bot.listen(user_id)
    page_num = int(pg.text.strip())

    await msg.edit("🗑️ Removing page...")
    out = f"downloads/removed_{message.reply_to_message.document.file_name}"
    await remove_page(file, page_num, out)

    thumb = await db.get_thumbnail(user_id)
    await message.reply_document(out, caption=f"✅ Page {page_num} removed successfully.", thumb=thumb)
    os.remove(file)
    os.remove(out)


@Client.on_message(filters.command("addpage"))
async def add_page_cmd(bot, message):
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply_text("Reply to a PDF and enter page number to add 📄➕")

    user_id = message.from_user.id
    file = await message.reply_to_message.download()
    msg = await message.reply_text("📄 Send page number after which to add new page:")
    pg = await bot.listen(user_id)
    page_num = int(pg.text.strip())

    await msg.edit("➕ Adding new page...")
    out = f"downloads/added_{message.reply_to_message.document.file_name}"
    await add_page(file, page_num, out)

    thumb = await db.get_thumbnail(user_id)
    await message.reply_document(out, caption=f"✅ Page added after {page_num}.", thumb=thumb)
    os.remove(file)
    os.remove(out)


@Client.on_message(filters.command("extractall"))
async def extract_all_cmd(bot, message):
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply_text("Reply to a PDF to extract all pages 📂")

    user_id = message.from_user.id
    file = await message.reply_to_message.download()
    await message.reply_text("📦 Extracting all pages...")

    folder = f"downloads/extracted_{user_id}"
    await extract_all(file, folder)

    zip_path = f"{folder}.zip"
    with ZipFile(zip_path, "w") as zipf:
        for root, _, files in os.walk(folder):
            for f in files:
                zipf.write(os.path.join(root, f), f)

    thumb = await db.get_thumbnail(user_id)
    await message.reply_document(zip_path, caption="✅ All pages extracted successfully.", thumb=thumb)

    os.remove(file)
    os.remove(zip_path)
    for f in os.listdir(folder):
        os.remove(os.path.join(folder, f))
    os.rmdir(folder)
