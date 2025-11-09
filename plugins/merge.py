from pyrogram import Client, filters
from pyrogram.types import Message
from PyPDF2 import PdfMerger
import os
import asyncio

# Memory for storing which users are merging + their PDFs
merge_mode = {}
user_pdfs = {}

# === /merge Command ===
@Bot.on_message(filters.command("merge") & filters.private)
async def merge_cmd(client: Client, message: Message):
    uid = message.from_user.id
    merge_mode[uid] = True
    user_pdfs[uid] = []
    await message.reply_text(
        "📎 Send me 2 or more PDF files to merge.\n\n"
        "When you're done, type **/done** to start merging."
    )

# === Handle PDF Uploads ===
@Bot.on_message(filters.document & filters.private)
async def collect_pdfs(client: Client, message: Message):
    uid = message.from_user.id

    # Check if user is in merge mode
    if uid not in merge_mode or not merge_mode[uid]:
        return await message.reply_text("ℹ️ Use /merge first to start PDF merging mode.")

    # Only accept PDFs
    if message.document.mime_type != "application/pdf":
        return await message.reply_text("❌ Please send only PDF files.")

    # Download and store file path
    file_name = message.document.file_name or f"{message.document.file_id}.pdf"
    file_path = f"downloads/{file_name}"
    await message.download(file_path)
    user_pdfs[uid].append(file_path)

    await message.reply_text(f"✅ Added: **{file_name}** ({len(user_pdfs[uid])} file(s) total)\nSend more or type /done to merge.")

# === /done Command (to merge PDFs) ===
@Bot.on_message(filters.command("done") & filters.private)
async def merge_pdfs(client: Client, message: Message):
    uid = message.from_user.id

    # Check mode
    if uid not in merge_mode or not merge_mode[uid]:
        return await message.reply_text("❌ You are not in merge mode. Use /merge first.")

    pdf_list = user_pdfs.get(uid, [])
    if len(pdf_list) < 2:
        return await message.reply_text("⚠️ You need at least 2 PDFs to merge.")

    output_pdf = f"downloads/merged_{uid}.pdf"
    m = await message.reply_text("🔄 Merging your PDFs...")

    try:
        merger = PdfMerger()
        for pdf in pdf_list:
            merger.append(pdf)
        merger.write(output_pdf)
        merger.close()

        await message.reply_document(
            document=output_pdf,
            caption=f"✅ Successfully merged {len(pdf_list)} PDFs!"
        )
        await m.delete()
    except Exception as e:
        await m.edit(f"❌ Error while merging: `{e}`")
    finally:
        # Clean up
        for path in pdf_list:
            if os.path.exists(path):
                os.remove(path)
        if os.path.exists(output_pdf):
            os.remove(output_pdf)
        merge_mode[uid] = False
        user_pdfs[uid] = []
