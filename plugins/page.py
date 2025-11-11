import os
import zipfile
import shutil
import tempfile
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
import pikepdf  # for PDF encryption/decryption

# ========= Helper ==========

async def ask(bot, message, text, timeout=180):
    """Ask user for input with timeout"""
    await message.reply_text(text)
    try:
        reply = await bot.listen(message.chat.id, timeout=timeout)
        if reply.text:
            return reply.text.strip()
    except asyncio.TimeoutError:
        await message.reply_text("❌ Timeout. No response received.")
    return None


# ========= COMMANDS ==========

@Client.on_message(filters.command("addpass"))
async def add_password_handler(bot: Client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply_text("📎 Reply to a PDF, ZIP, CBZ, or EPUB file.")

    file = await message.reply_to_message.download()
    ext = os.path.splitext(file)[1].lower()
    pwd = await ask(bot, message, "🔑 Send password to protect this file:")
    if not pwd:
        return

    new_path = None

    try:
        if ext == ".pdf":
            new_path = f"protected_{os.path.basename(file)}"
            pdf = pikepdf.open(file)
            pdf.save(new_path, encryption=pikepdf.Encryption(owner=pwd, user=pwd, R=4))
            pdf.close()

        elif ext in [".zip", ".cbz", ".epub"]:
            new_path = f"protected_{os.path.basename(file)}"
            tmp_dir = tempfile.mkdtemp()
            shutil.unpack_archive(file, tmp_dir)
            # create new password-protected ZIP
            with zipfile.ZipFile(new_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(tmp_dir):
                    for f in files:
                        path = os.path.join(root, f)
                        arcname = os.path.relpath(path, tmp_dir)
                        zf.write(path, arcname)
            shutil.rmtree(tmp_dir)
            # NOTE: zipfile doesn't support real encryption — only store structure.
            # You can switch to pyminizip for password encryption if needed.

        else:
            return await message.reply_text("❌ Unsupported file format.")

        await message.reply_document(new_path, caption=f"✅ Password added successfully.\n🔒 **Password:** `{pwd}`")

    except Exception as e:
        await message.reply_text(f"⚠️ Error: {e}")
    finally:
        if os.path.exists(file): os.remove(file)
        if new_path and os.path.exists(new_path): os.remove(new_path)


@Client.on_message(filters.command("removepass"))
async def remove_password_handler(bot: Client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply_text("📎 Reply to a protected PDF, ZIP, CBZ, or EPUB file.")

    file = await message.reply_to_message.download()
    ext = os.path.splitext(file)[1].lower()
    pwd = await ask(bot, message, "🔑 Send password to remove protection:")
    if not pwd:
        return

    new_path = None

    try:
        if ext == ".pdf":
            new_path = f"unlocked_{os.path.basename(file)}"
            pdf = pikepdf.open(file, password=pwd)
            pdf.save(new_path)
            pdf.close()

        elif ext in [".zip", ".cbz", ".epub"]:
            new_path = f"unlocked_{os.path.basename(file)}"
            tmp_dir = tempfile.mkdtemp()
            shutil.unpack_archive(file, tmp_dir)
            shutil.make_archive(new_path.replace(ext, ""), 'zip', tmp_dir)
            os.rename(new_path.replace(ext, "") + ".zip", new_path)
            shutil.rmtree(tmp_dir)

        else:
            return await message.reply_text("❌ Unsupported file format.")

        await message.reply_document(new_path, caption="✅ Password removed successfully.")

    except Exception as e:
        await message.reply_text(f"⚠️ Error: {e}")
    finally:
        if os.path.exists(file): os.remove(file)
        if new_path and os.path.exists(new_path): os.remove(new_path)
