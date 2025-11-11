from pyrogram import Client, filters
from helper.database import save_password, get_password, delete_password
import os, fitz

print("✅ password.py loaded")

@Client.on_message(filters.command("addpass"))
async def add_pass(_, m):
    if len(m.command) < 2:
        return await m.reply("⚠️ Usage: `/addpass <password>`")
    password = m.text.split(" ", 1)[1]
    await save_password(m.from_user.id, password)
    await m.reply("✅ Password saved successfully!")

@Client.on_message(filters.command("removepass"))
async def remove_pass(_, m):
    await delete_password(m.from_user.id)
    await m.reply("🗑️ Password removed successfully!")

@Client.on_message(filters.command("extractall"))
async def extract_all(_, m):
    if not m.reply_to_message or not m.reply_to_message.document:
        return await m.reply("⚠️ Reply to a PDF file to extract all pages.")
    
    file = await m.reply_to_message.download()
    try:
        pdf = fitz.open(file)
        folder = f"downloads/{m.from_user.id}_pages"
        os.makedirs(folder, exist_ok=True)
        for i, page in enumerate(pdf):
            img_path = f"{folder}/page_{i+1}.png"
            pix = page.get_pixmap(dpi=150)
            pix.save(img_path)
        await m.reply("✅ All pages extracted as PNG images!")
    except Exception as e:
        await m.reply(f"❌ Error: {e}")
    finally:
        os.remove(file)
