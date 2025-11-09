import os
import re
from pyrogram import Client, filters
from pyrogram.types import Message
from PyPDF2 import PdfMerger
from helper.database import save_thumbnail, get_thumbnail, delete_thumbnail

merge_mode = {}
user_pdfs = {}
user_steps = {}
temp_data = {}

# ==============================
# 🖼️ /setthumb
# ==============================
@Client.on_message(filters.command("setthumb") & filters.private)
async def set_thumbnail(client: Client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply_text("📸 Reply to a photo with `/setthumb` to save thumbnail.")

    uid = message.from_user.id
    thumb_path = f"downloads/{uid}_thumb.jpg"
    await message.reply_to_message.download(thumb_path)
    save_thumbnail(uid, thumb_path)
    await message.reply_text("✅ Thumbnail saved successfully!")
    if os.path.exists(thumb_path):
        os.remove(thumb_path)


# ==============================
# 📎 /merge
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
        "➡️ Send me multiple PDF files (with numeric names like 23.pdf, 24.pdf...)\n"
        "➡️ When done, type **/done**.\n"
        "➡️ Use **/cancel** to stop merging."
    )


# ==============================
# 📄 Collect PDFs
# ==============================
@Client.on_message(filters.document & filters.private)
async def collect_pdfs(client: Client, message: Message):
    uid = message.from_user.id
    if not merge_mode.get(uid):
        return

    doc = message.document
    if doc.mime_type != "application/pdf":
        return await message.reply_text("❌ Only PDF files are allowed.")

    filename = doc.file_name or f"{doc.file_id}.pdf"
    filepath = f"downloads/{uid}_{filename}"
    msg = await message.reply_text(f"⬇️ Downloading **{filename}** ...")
    await client.download_media(message, filepath)

    # extract numeric ID from file name
    match = re.search(r"(\d+)", filename)
    number = int(match.group(1)) if match else None

    user_pdfs[uid].append({"path": filepath, "name": filename, "number": number})
    await msg.edit_text(
        f"✅ Added: **{filename}**\n📄 Total Files: {len(user_pdfs[uid])}\n\nSend more or type /done."
    )


# ==============================
# 🏁 /done
# ==============================
@Client.on_message(filters.command("done") & filters.private)
async def done_command(client: Client, message: Message):
    uid = message.from_user.id
    if not merge_mode.get(uid):
        return await message.reply_text("❌ Use /merge first.")

    pdf_list = user_pdfs.get(uid, [])
    if len(pdf_list) < 2:
        return await message.reply_text("⚠️ Please send at least 2 PDFs before merging.")

    # sort PDFs by detected number
    numbered = [p for p in pdf_list if p["number"] is not None]
    unnumbered = [p for p in pdf_list if p["number"] is None]
    numbered.sort(key=lambda x: x["number"])

    if numbered:
        numbers = [p["number"] for p in numbered]
        min_num, max_num = min(numbers), max(numbers)
        missing = [i for i in range(min_num, max_num + 1) if i not in numbers]

        if missing:
            await message.reply_text(
                f"⚠️ Missing PDFs detected between {min_num}–{max_num}:\n"
                f"`{', '.join(map(str, missing))}`\n\n"
                "📥 Please send missing PDFs or type `/done` again to continue anyway."
            )
            temp_data[uid]["missing"] = missing
            temp_data[uid]["sorted"] = numbered + unnumbered
            return

    # ask for output name
    user_steps[uid] = "waiting_name"
    await message.reply_text("📝 Send a name for your merged PDF (without .pdf):")


# ==============================
# 🧠 Handle Filename
# ==============================
@Client.on_message(filters.text & filters.private)
async def handle_filename(client: Client, message: Message):
    uid = message.from_user.id
    if user_steps.get(uid) != "waiting_name":
        return

    pdf_name = message.text.strip().replace("/", "").replace("\\", "")
    if not pdf_name:
        return await message.reply_text("❌ Invalid name. Try again.")

    temp_data[uid]["name"] = pdf_name
    await message.reply_text("⚙️ Starting merge...")
    await merge_and_send_pdf(client, message)


# ==============================
# 🔄 Merge PDFs
# ==============================
async def merge_and_send_pdf(client: Client, message: Message):
    uid = message.from_user.id
    pdf_list = temp_data.get(uid, {}).get("sorted") or user_pdfs.get(uid, [])
    pdf_name = temp_data[uid].get("name", f"merged_{uid}")
    output_pdf = f"downloads/{pdf_name}.pdf"

    # get thumbnail
    thumb_path = get_thumbnail(uid)
    m = await message.reply_text("🔄 Merging your PDFs...")

    try:
        merger = PdfMerger()
        if all(isinstance(p, dict) for p in pdf_list):
            for p in sorted(pdf_list, key=lambda x: x["number"] or 999999):
                merger.append(p["path"])
        else:
            for path in pdf_list:
                merger.append(path)

        merger.write(output_pdf)
        merger.close()

        await message.reply_document(
            document=output_pdf,
            thumb=thumb_path if thumb_path else None,
            caption=f"✅ **Merged Successfully!**\n📄 `{pdf_name}.pdf`\n🧩 Total: {len(pdf_list)} PDFs"
        )
        await m.delete()
    except Exception as e:
        await m.edit_text(f"❌ Merge failed:\n`{e}`")
    finally:
        # cleanup
        for p in pdf_list:
            if isinstance(p, dict):
                path = p["path"]
            else:
                path = p
            if os.path.exists(path):
                os.remove(path)
        if os.path.exists(output_pdf):
            os.remove(output_pdf)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)

        merge_mode[uid] = False
        user_pdfs[uid] = []
        user_steps[uid] = None
        temp_data[uid] = {}


# ==============================
# 🗑️ /delthumb
# ==============================
@Client.on_message(filters.command("delthumb") & filters.private)
async def delete_thumb_cmd(client: Client, message: Message):
    uid = message.from_user.id
    delete_thumbnail(uid)
    await message.reply_text("🗑️ Thumbnail deleted!")


# ==============================
# 🛑 /cancel
# ==============================
@Client.on_message(filters.command("cancel") & filters.private)
async def cancel_merge(client: Client, message: Message):
    uid = message.from_user.id
    if not merge_mode.get(uid):
        return await message.reply_text("ℹ️ You're not merging any PDFs.")

    merge_mode[uid] = False
    for p in user_pdfs.get(uid, []):
        path = p["path"] if isinstance(p, dict) else p
        if os.path.exists(path):
            os.remove(path)
    user_pdfs[uid] = []
    user_steps[uid] = None
    temp_data[uid] = {}
    await message.reply_text("🚫 Merge cancelled and temporary files cleared.")
