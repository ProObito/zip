import os
from pyrogram import Client, filters
from pyrogram.types import Message
from PyPDF2 import PdfMerger
from helper.database import save_thumbnail, get_thumbnail, delete_thumbnail

# Temporary storage
merge_mode = {}
user_pdfs = {}
user_steps = {}
temp_data = {}

# ==============================
# 🖼️ /setthumb Command
# ==============================
@Client.on_message(filters.command("setthumb") & filters.private)
async def set_thumbnail(client: Client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply_text("📸 Reply to a photo using `/setthumb` to set your thumbnail.")

    uid = message.from_user.id
    thumb_path = f"downloads/{uid}_thumb.jpg"
    await message.reply_to_message.download(thumb_path)

    save_thumbnail(uid, thumb_path)
    await message.reply_text("✅ Thumbnail saved successfully! It will be used automatically next time.")
    print(f"[DEBUG] Thumbnail set for user {uid}")

    if os.path.exists(thumb_path):
        os.remove(thumb_path)


# ==============================
# 📎 /merge Command
# ==============================
@Client.on_message(filters.command("merge") & filters.private)
async def merge_cmd(client: Client, message: Message):
    uid = message.from_user.id
    merge_mode[uid] = True
    user_pdfs[uid] = []
    user_steps[uid] = None
    temp_data[uid] = {}

    await message.reply_text(
        "📎 **PDF Merge Mode Activated!**\n\n"
        "➡️ Send me **2 or more PDF files** one by one.\n"
        "➡️ When done, type **/done**.\n"
        "➡️ Use **/cancel** to stop merging."
    )
    print(f"[DEBUG] User {uid} started merge mode.")


# ==============================
# 📄 Collect PDFs
# ==============================
@Client.on_message(filters.document & filters.private)
async def collect_pdfs(client: Client, message: Message):
    uid = message.from_user.id

    if not merge_mode.get(uid):
        return

    if message.document.mime_type != "application/pdf":
        return await message.reply_text("❌ Only PDF files are allowed.")

    file_name = message.document.file_name or f"{message.document.file_id}.pdf"
    file_path = f"downloads/{uid}_{file_name}"

    msg = await message.reply_text(f"⬇️ Downloading **{file_name}** ...")
    await client.download_media(message, file_path)

    user_pdfs[uid].append(file_path)
    await msg.edit_text(f"✅ Added: **{file_name}**\n📄 Total Files: {len(user_pdfs[uid])}\n\nSend more or type /done.")
    print(f"[DEBUG] {file_name} added for user {uid}.")


# ==============================
# 🏁 /done Command
# ==============================
@Client.on_message(filters.command("done") & filters.private)
async def done_command(client: Client, message: Message):
    uid = message.from_user.id

    if not merge_mode.get(uid):
        return await message.reply_text("❌ Use /merge first.")

    pdf_list = user_pdfs.get(uid, [])
    if len(pdf_list) < 2:
        return await message.reply_text("⚠️ Please send at least 2 PDFs before merging.")

    # Ask for custom file name
    user_steps[uid] = "waiting_name"
    await message.reply_text("📝 Send me the name for your merged PDF (without .pdf):")
    print(f"[DEBUG] Waiting for file name from user {uid}")


# ==============================
# 🧠 Handle PDF Name
# ==============================
@Client.on_message(filters.text & filters.private)
async def handle_filename(client: Client, message: Message):
    uid = message.from_user.id

    if user_steps.get(uid) == "waiting_name":
        pdf_name = message.text.strip().replace("/", "").replace("\\", "")
        if not pdf_name:
            return await message.reply_text("❌ Invalid name. Try again.")

        temp_data[uid]["name"] = pdf_name
        await message.reply_text("⚙️ Starting merge...")
        await merge_and_send_pdf(client, message)


# ==============================
# 🔄 Merge & Send PDF
# ==============================
async def merge_and_send_pdf(client: Client, message: Message):
    uid = message.from_user.id
    pdf_list = user_pdfs.get(uid, [])
    pdf_name = temp_data[uid].get("name", f"merged_{uid}")
    output_pdf = f"downloads/{pdf_name}.pdf"
    m = await message.reply_text("🔄 Merging your PDFs...")

    # get user's saved thumbnail
    thumb_path = get_thumbnail(uid)

    try:
        merger = PdfMerger()
        for pdf in pdf_list:
            merger.append(pdf)
        merger.write(output_pdf)
        merger.close()

        await message.reply_document(
            document=output_pdf,
            thumb=thumb_path if thumb_path else None,
            caption=f"✅ **Merged Successfully!**\n📄 File: `{pdf_name}.pdf`\n🧩 Total PDFs: {len(pdf_list)}"
        )
        await m.delete()
        print(f"[DEBUG] Merge success for user {uid}.")
    except Exception as e:
        print(f"[ERROR] Merge failed for user {uid}: {e}")
        await m.edit_text(f"❌ Merge failed:\n`{e}`")
    finally:
        for f in pdf_list:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists(output_pdf):
            os.remove(output_pdf)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)

        merge_mode[uid] = False
        user_pdfs[uid] = []
        user_steps[uid] = None
        temp_data[uid] = {}


# ==============================
# 🗑️ /delthumb Command
# ==============================
@Client.on_message(filters.command("delthumb") & filters.private)
async def delete_thumb_cmd(client: Client, message: Message):
    uid = message.from_user.id
    delete_thumbnail(uid)
    await message.reply_text("🗑️ Thumbnail deleted successfully!")
    print(f"[DEBUG] Deleted thumbnail for user {uid}")


# ==============================
# 🛑 Cancel Merge
# ==============================
@Client.on_message(filters.command("cancel") & filters.private)
async def cancel_merge(client: Client, message: Message):
    uid = message.from_user.id
    if merge_mode.get(uid):
        merge_mode[uid] = False
        for f in user_pdfs.get(uid, []):
            if os.path.exists(f):
                os.remove(f)
        user_pdfs[uid] = []
        temp_data[uid] = {}
        user_steps[uid] = None
        await message.reply_text("🚫 Merge cancelled and temp files cleared.")
        print(f"[DEBUG] Merge cancelled by user {uid}.")
    else:
        await message.reply_text("ℹ️ You’re not currently merging any PDFs.")
