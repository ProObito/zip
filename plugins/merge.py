import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from PyPDF2 import PdfMerger

# In-memory storage for user session
merge_mode = {}
user_pdfs = {}

# === /merge Command ===
@Client.on_message(filters.command("merge") & filters.private)
async def merge_cmd(client: Client, message: Message):
    uid = message.from_user.id
    merge_mode[uid] = True
    user_pdfs[uid] = []

    await message.reply_text(
        "📎 **PDF Merge Mode Activated!**\n\n"
        "➡️ Send me **2 or more PDF files** one by one.\n"
        "➡️ When you’re done, type **/done** to merge them.\n"
        "➡️ Type **/cancel** to stop merging."
    )
    print(f"[DEBUG] User {uid} started merge mode.")


# === Collect PDFs ===
@Client.on_message(filters.document & filters.private)
async def collect_pdfs(client: Client, message: Message):
    uid = message.from_user.id

    # If merge mode not active
    if not merge_mode.get(uid):
        return await message.reply_text("ℹ️ Use /merge first to start merging PDFs.")

    # Only allow PDFs
    if message.document.mime_type != "application/pdf":
        return await message.reply_text("❌ Only PDF files are supported.")

    file_name = message.document.file_name or f"{message.document.file_id}.pdf"
    file_path = f"downloads/{uid}_{file_name}"

    msg = await message.reply_text(f"⬇️ Downloading **{file_name}** ...")
    await client.download_media(message, file_path)

    user_pdfs[uid].append(file_path)
    await msg.edit_text(f"✅ Added: **{file_name}**\n📄 Total Files: {len(user_pdfs[uid])}\n\nSend more or type /done.")
    print(f"[DEBUG] {file_name} added for user {uid}.")


# === /done Command ===
@Client.on_message(filters.command("done") & filters.private)
async def merge_pdfs(client: Client, message: Message):
    uid = message.from_user.id

    if not merge_mode.get(uid):
        return await message.reply_text("❌ You’re not in merge mode. Use /merge first.")

    pdf_list = user_pdfs.get(uid, [])
    if len(pdf_list) < 2:
        return await message.reply_text("⚠️ Please send at least 2 PDFs before merging.")

    output_pdf = f"downloads/merged_{uid}.pdf"
    m = await message.reply_text("🔄 Merging your PDFs, please wait...")

    try:
        merger = PdfMerger()
        for pdf in pdf_list:
            merger.append(pdf)
        merger.write(output_pdf)
        merger.close()

        await message.reply_document(
            document=output_pdf,
            caption=f"✅ Successfully merged **{len(pdf_list)} PDFs!**\nNo quality loss 🔥"
        )
        await m.delete()
        print(f"[DEBUG] User {uid} merged {len(pdf_list)} PDFs successfully.")
    except Exception as e:
        print(f"[ERROR] Merge failed for user {uid}: {e}")
        await m.edit_text(f"❌ Error during merge:\n`{e}`")
    finally:
        # Clean up temp files
        for f in pdf_list:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists(output_pdf):
            os.remove(output_pdf)
        merge_mode[uid] = False
        user_pdfs[uid] = []


# === /cancel Command ===
@Client.on_message(filters.command("cancel") & filters.private)
async def cancel_merge(client: Client, message: Message):
    uid = message.from_user.id
    if merge_mode.get(uid):
        merge_mode[uid] = False
        for f in user_pdfs.get(uid, []):
            if os.path.exists(f):
                os.remove(f)
        user_pdfs[uid] = []
        await message.reply_text("🚫 Merge mode cancelled. All temporary files deleted.")
        print(f"[DEBUG] Merge cancelled by user {uid}.")
    else:
        await message.reply_text("ℹ️ You’re not currently merging any PDFs.")
