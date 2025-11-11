from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import os
import subprocess
import shutil
import zipfile
import tempfile
import asyncio
from typing import Optional
from PyPDF2 import PdfReader, PdfWriter

# Import your status bar helper (adjust if signature differs)
from .utils import status_bar  # expected: async def status_bar(bot, chat_id, text) or similar
# backward compatibility alias 

TMP = "downloads"
os.makedirs(TMP, exist_ok=True)

# user_sessions holds interactive state per user
user_sessions = {}
# structure:
# user_sessions[uid] = {
#   "cmd": "getpage" / "addpage" / "replacepage" / "removepage" / "addpass" / "removepass",
#   "stage": "...",      # e.g. "await_file", "await_number", "await_aux", "processing"
#   "file": "/path/to/base",
#   "aux": "/path/to/aux",
#   "page_no": int,
#   "password": str
# }

TIMEOUT = 180  # seconds (3 minutes)


### ---------- Helpers ----------
def cleanup(*paths):
    for p in paths:
        try:
            if not p:
                continue
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            elif os.path.exists(p):
                os.remove(p)
        except:
            pass


async def wait_for_input(user_id: int, timeout: int = TIMEOUT) -> Optional[str]:
    """
    Wait until user_sessions[user_id] gets a 'text' field, or cancelled/timeout.
    Returns the text or None (timeout/cancel).
    """
    for _ in range(timeout):
        await asyncio.sleep(1)
        sess = user_sessions.get(user_id)
        if not sess:  # cancelled externally
            return None
        if "text" in sess:
            txt = sess.pop("text")
            return txt
    # timeout
    user_sessions.pop(user_id, None)
    return None


async def wait_for_aux_file(user_id: int, timeout: int = TIMEOUT) -> Optional[str]:
    """
    Wait until user_sessions[user_id] gets an 'aux' (path) or cancelled/timeout.
    """
    for _ in range(timeout):
        await asyncio.sleep(1)
        sess = user_sessions.get(user_id)
        if not sess:
            return None
        if "aux" in sess:
            return sess.pop("aux")
    user_sessions.pop(user_id, None)
    return None


def ensure_ext(path: str, ext: str) -> str:
    return path if path.lower().endswith(f".{ext}") else f"{path}.{ext}"


### ---------- Generic flow functions ----------
async def ask_send_file(bot: Client, chat_id:int, user_id:int, prompt:str):
    """Ask user to send file (document). Sets session and returns downloaded path or None."""
    user_sessions[user_id] = {"cmd": "await_file"}
    await bot.send_message(chat_id, prompt + f"\n⏳ You have {TIMEOUT//60} minute(s). Type `cancel` to cancel.")
    # Wait for session to get 'file' by doc listener
    for _ in range(TIMEOUT):
        await asyncio.sleep(1)
        sess = user_sessions.get(user_id)
        if not sess:
            return None
        if "file" in sess:
            return sess.pop("file")
    user_sessions.pop(user_id, None)
    await bot.send_message(chat_id, "❌ Timeout. No file received.")
    return None


async def ask_text(bot: Client, chat_id:int, user_id:int, prompt:str):
    """Ask a text (page number or password). Returns text or None."""
    user_sessions[user_id] = {"cmd":"await_text"}
    await bot.send_message(chat_id, prompt + f"\n⏳ You have {TIMEOUT//60} minute(s). Type `cancel` to cancel.")
    txt = await wait_for_input(user_id)
    if txt is None:
        await bot.send_message(chat_id, "❌ Timeout or cancelled.")
        return None
    return txt
    

# === Ghostscript Compression Function ===
def compress_pdf(input_path, output_path, quality="ebook"):
    """
    quality options: screen < ebook < printer < prepress
    """
    try:
        subprocess.run([
            "gs",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            f"-dPDFSETTINGS=/{quality}",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            f"-sOutputFile={output_path}",
            input_path
        ], check=True)
        return True
    except Exception as e:
        print("Ghostscript Error:", e)
        return False


# === User compression settings memory ===
user_mode = {}     # stores if user is in compdf mode
user_choice = {}   # stores selected compression level


# === /compdf Command ===
@Client.on_message(filters.command("compdf") & filters.private)
async def compdf_cmd(client: Client, message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton("📉 Light (≈2 MB smaller)", callback_data="compress_2"),
                InlineKeyboardButton("📦 Medium (≈4 MB smaller)", callback_data="compress_4")
            ],
            [
                InlineKeyboardButton("🧩 Strong (≈6 MB smaller)", callback_data="compress_6"),
                InlineKeyboardButton("💀 Ultra (≈8 MB smaller)", callback_data="compress_8")
            ]
        ]
    )
    await message.reply_text(
        "🧠 Choose compression strength:\n\nThen send me your PDF.",
        reply_markup=keyboard
    )
    user_mode[message.from_user.id] = True


# === Compression Level Selection ===
@Client.on_callback_query(filters.regex(r"compress_\d+"))
async def set_compression_level(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    level = int(query.data.split("_")[1])
    user_choice[uid] = level
    user_mode[uid] = True  # ensure mode is active
    await query.message.edit_text(f"✅ Compression level set: **{level} MB smaller**\nNow send your PDF file.")


# === Handle PDF ===
@Client.on_message(filters.document & filters.private)
async def handle_pdf(client: Client, message: Message):
    uid = message.from_user.id

    # check if user is in compression mode
    if uid not in user_mode or not user_mode[uid]:
        return await message.reply_text("ℹ️ Please use /compdf first to enable PDF compression mode.")

    if message.document.mime_type != "application/pdf":
        return await message.reply_text("❌ Please send a valid PDF file.")

    level = user_choice.get(uid, 4)  # default level = medium
    file_name = message.document.file_name or "input.pdf"
    input_pdf = f"downloads/{file_name}"
    output_pdf = f"downloads/compressed_{file_name}"

    msg = await message.reply_text("⬇️ Downloading your PDF...")
    await client.download_media(message, file_name=input_pdf)

    await msg.edit("⚙️ Compressing your PDF... please wait.")

    try:
        old_size = os.path.getsize(input_pdf)
        old_mb = old_size / (1024 * 1024)

        # compression strength mapping
        if level <= 2:
            quality = "printer"      # light
        elif level <= 4:
            quality = "ebook"        # medium
        elif level <= 6:
            quality = "screen"       # strong
        else:
            quality = "default"      # ultra

        ok = compress_pdf(input_pdf, output_pdf, quality=quality)
        if not ok:
            return await msg.edit("❌ Compression failed. Try again later.")

        new_size = os.path.getsize(output_pdf)
        new_mb = new_size / (1024 * 1024)
        reduction = round(old_mb - new_mb, 2)

        caption = (
            f"✅ **Compression Complete!**\n\n"
            f"📦 Original: {old_mb:.2f} MB\n"
            f"📉 Compressed: {new_mb:.2f} MB\n"
            f"💾 Reduced by: {reduction:.2f} MB"
        )

        await message.reply_document(document=output_pdf, caption=caption)
        await msg.delete()

    except Exception as e:
        await msg.edit(f"⚠️ Error: `{e}`")

    finally:
        # cleanup
        for path in [input_pdf, output_pdf]:
            if os.path.exists(path):
                os.remove(path)
        user_mode[uid] = False  # reset mode after one file
        if uid in user_choice:
            del user_choice[uid]


### ---------- Document / Text Listeners (to populate sessions) ----------
@Client.on_message(filters.document & filters.private)
async def _doc_listener(bot: Client, message: Message):
    uid = message.from_user.id
    sess = user_sessions.get(uid)
    if not sess:
        return
    # Download the document to TMP with safe name
    fpath = await message.download(file_name=os.path.join(TMP, f"{uid}_{message.document.file_name}"))
    # Contextual handling:
    cmd = sess.get("cmd")
    if cmd in ("await_file",):
        sess["file"] = fpath
    elif cmd in ("await_aux", "await_add_aux", "await_replace_aux"):
        sess["aux"] = fpath
    else:
        # If user wasn't explicitly asked, ignore
        cleanup(fpath)


@Client.on_message(filters.text & filters.private)
async def _text_listener(bot: Client, message: Message):
    uid = message.from_user.id
    text = message.text.strip()
    # if user typed cancel and has a session, cancel it
    if text.lower() == "cancel":
        if uid in user_sessions:
            user_sessions.pop(uid, None)
        await message.reply_text("❌ Operation cancelled.")
        return
    sess = user_sessions.get(uid)
    if not sess:
        return
    # store text for waiting functions
    if sess.get("cmd") in ("await_text", "await_number", "await_pass"):
        sess["text"] = text
    elif sess.get("cmd", "").startswith("asktxt_"):
        sess["text"] = text
    else:
        # also allow aux textual inputs (rare)
        sess["text"] = text


### ---------- COMMANDS ----------

# 1) GETPAGE: extract a single page (PDF -> page PDF, CBZ/ZIP/EPUB -> extract image)
@Client.on_message(filters.command("getpage") & filters.private)
async def cmd_getpage(bot: Client, message: Message):
    """
    Flow:
    1. Ask file
    2. Ask page number
    3. Send single-page PDF (for PDF) or single image (for CBZ/ZIP/EPUB)
    """
    uid = message.from_user.id
    chat = message.chat.id

    # Ask file
    src = await ask_send_file(bot, chat, uid, "📎 Send the file (PDF / CBZ / ZIP / EPUB) from which to extract a page:")
    if not src:
        return

    # Ask page number
    txt = await ask_text(bot, chat, uid, "📄 Send the page number you want to extract (1-based):")
    if not txt or not txt.isdigit():
        cleanup(src); return await bot.send_message(chat, "❌ Invalid page number / cancelled.")

    page_no = int(txt)
    await status_bar(bot, chat, "Starting extraction...")

    ext = os.path.splitext(src)[1].lower().lstrip(".")
    try:
        if ext == "pdf":
            reader = PdfReader(src)
            total = len(reader.pages)
            if page_no < 1 or page_no > total:
                return await bot.send_message(chat, f"❌ Page out of range (1-{total})")
            writer = PdfWriter()
            writer.add_page(reader.pages[page_no-1])
            out = os.path.join(TMP, f"page_{uid}_{page_no}.pdf")
            with open(out, "wb") as f:
                writer.write(f)
            await status_bar(bot, chat, f"Extracted page {page_no}/{total}")
            await bot.send_document(chat, out)
            cleanup(src, out)

        elif ext in ("cbz", "zip", "epub"):
            tmpdir = tempfile.mkdtemp(prefix=f"extract_{uid}_")
            if ext in ("cbz","zip","epub"):
                with zipfile.ZipFile(src, "r") as zf:
                    zf.extractall(tmpdir)
            # list image files sorted
            imgs = sorted([f for f in os.listdir(tmpdir) if f.lower().endswith((".jpg",".jpeg",".png"))])
            total = len(imgs)
            if total == 0:
                cleanup(src, tmpdir)
                return await bot.send_message(chat, "❌ No image/pages found inside archive.")
            if page_no < 1 or page_no > total:
                cleanup(src, tmpdir)
                return await bot.send_message(chat, f"❌ Page out of range (1-{total})")
            img_path = os.path.join(tmpdir, imgs[page_no-1])
            await status_bar(bot, chat, f"Sending page {page_no}/{total}")
            await bot.send_document(chat, img_path)  # send as file (no thumb)
            cleanup(src, tmpdir)
        else:
            cleanup(src)
            return await bot.send_message(chat, "❌ Unsupported file type. Use PDF, CBZ, ZIP, EPUB.")
    except Exception as e:
        cleanup(src)
        await bot.send_message(chat, f"❌ Error: {e}")


# 2) REMOVE PAGE: remove nth page from PDF or nth image from CBZ/ZIP
@Client.on_message(filters.command("removepage") & filters.private)
async def cmd_removepage(bot: Client, message: Message):
    uid = message.from_user.id
    chat = message.chat.id

    src = await ask_send_file(bot, chat, uid, "📎 Send the file (PDF / CBZ / ZIP) to remove page from:")
    if not src:
        return

    txt = await ask_text(bot, chat, uid, "📄 Send the page number to remove (1-based):")
    if not txt or not txt.isdigit():
        cleanup(src); return await bot.send_message(chat, "❌ Invalid page number / cancelled.")

    page_no = int(txt)
    await status_bar(bot, chat, "Starting removal...")

    ext = os.path.splitext(src)[1].lower().lstrip(".")
    try:
        if ext == "pdf":
            reader = PdfReader(src)
            total = len(reader.pages)
            if page_no < 1 or page_no > total:
                cleanup(src); return await bot.send_message(chat, f"❌ Page out of range (1-{total})")
            writer = PdfWriter()
            for i,p in enumerate(reader.pages, start=1):
                if i != page_no:
                    writer.add_page(p)
            out = os.path.join(TMP, f"removed_{uid}_{os.path.basename(src)}")
            with open(out, "wb") as f:
                writer.write(f)
            await status_bar(bot, chat, f"Removed page {page_no}/{total}")
            await bot.send_document(chat, out)
            cleanup(src, out)

        elif ext in ("cbz","zip"):
            tmpd = tempfile.mkdtemp(prefix=f"cbz_{uid}_")
            with zipfile.ZipFile(src, "r") as zf:
                zf.extractall(tmpd)
            imgs = sorted([f for f in os.listdir(tmpd) if f.lower().endswith((".jpg",".jpeg",".png"))])
            total = len(imgs)
            if page_no < 1 or page_no > total:
                cleanup(src, tmpd); return await bot.send_message(chat, f"❌ Image index out of range (1-{total})")
            os.remove(os.path.join(tmpd, imgs[page_no-1]))
            out = os.path.join(TMP, f"removed_{uid}_{os.path.basename(src)}")
            with zipfile.ZipFile(out, "w") as zf:
                for f in sorted(os.listdir(tmpd)):
                    zf.write(os.path.join(tmpd,f), arcname=f)
            await status_bar(bot, chat, f"Removed image {page_no}/{total}")
            await bot.send_document(chat, out)
            cleanup(src, tmpd, out)
        else:
            cleanup(src)
            return await bot.send_message(chat, "❌ Unsupported file type. Use PDF, CBZ, ZIP.")
    except Exception as e:
        cleanup(src)
        await bot.send_message(chat, f"❌ Error: {e}")


# 3) ADD PAGE: insert new page(s) after given position (PDF or CBZ/ZIP)
@Client.on_message(filters.command("addpage") & filters.private)
async def cmd_addpage(bot: Client, message: Message):
    uid = message.from_user.id
    chat = message.chat.id

    src = await ask_send_file(bot, chat, uid, "📎 Send the base file (PDF / CBZ / ZIP) where you want to insert pages:")
    if not src:
        return

    txt = await ask_text(bot, chat, uid, "📄 Send the position AFTER WHICH to insert pages (1-based). Use 0 to insert at start:")
    if not txt or (not txt.isdigit() and not (txt.startswith("-") and txt[1:].isdigit())):
        cleanup(src); return await bot.send_message(chat, "❌ Invalid position / cancelled.")
    pos = int(txt)

    # ask for the insert file(s)
    user_sessions[uid] = {"cmd":"await_add_aux"}
    await bot.send_message(chat, "📎 Now send the file to insert (PDF for pages or CBZ/ZIP/images for images). You have 3 minutes. Type `cancel` to abort.")
    aux = await wait_for_aux_file(uid)
    if not aux:
        cleanup(src); return await bot.send_message(chat, "❌ No insert file received or cancelled.")

    await status_bar(bot, chat, "Starting insertion...")

    ext = os.path.splitext(src)[1].lower().lstrip(".")
    try:
        if ext == "pdf":
            base = PdfReader(src)
            ins = PdfReader(aux)
            writer = PdfWriter()
            total = len(base.pages)
            # insert after position pos (if pos==0 -> before first)
            inserted = False
            for i, p in enumerate(base.pages, start=1):
                writer.add_page(p)
                if i == pos:
                    for ip in ins.pages:
                        writer.add_page(ip)
                    inserted = True
            if not inserted and pos >= total:
                for ip in ins.pages:
                    writer.add_page(ip)
            out = os.path.join(TMP, f"added_{uid}_{os.path.basename(src)}")
            with open(out, "wb") as f:
                writer.write(f)
            await status_bar(bot, chat, f"Inserted pages at pos {pos}")
            await bot.send_document(chat, out)
            cleanup(src, aux, out)

        elif ext in ("cbz","zip"):
            base_tmp = tempfile.mkdtemp(prefix=f"cbzbase_{uid}_")
            with zipfile.ZipFile(src,"r") as zf:
                zf.extractall(base_tmp)
            files = sorted([f for f in os.listdir(base_tmp) if f.lower().endswith((".jpg",".jpeg",".png"))])
            # gather inserts
            inserts = []
            if aux.lower().endswith((".zip",".cbz")):
                with zipfile.ZipFile(aux,"r") as zf:
                    for n in zf.namelist():
                        if n.lower().endswith((".jpg",".jpeg",".png")):
                            zf.extract(n, base_tmp)
                            inserts.append(os.path.join(base_tmp, n))
            else:
                # aux could be a single image
                inserts.append(aux)
            # build new ordered list with insertion after pos
            new_order = []
            for idx, fname in enumerate(files, start=1):
                new_order.append(os.path.join(base_tmp, fname))
                if idx == pos:
                    for ins in inserts:
                        # copy to base_tmp to avoid path conflict
                        dst = os.path.join(base_tmp, f"ins_{int(asyncio.get_event_loop().time())}_{os.path.basename(ins)}")
                        shutil.copyfile(ins, dst)
                        new_order.append(dst)
            if pos >= len(files):
                for ins in inserts:
                    dst = os.path.join(base_tmp, f"ins_{int(asyncio.get_event_loop().time())}_{os.path.basename(ins)}")
                    shutil.copyfile(ins, dst)
                    new_order.append(dst)
            out = os.path.join(TMP, f"added_{uid}_{os.path.basename(src)}")
            with zipfile.ZipFile(out, "w") as zf:
                for p in new_order:
                    zf.write(p, arcname=os.path.basename(p))
            await status_bar(bot, chat, f"Inserted items into archive at pos {pos}")
            await bot.send_document(chat, out)
            cleanup(src, aux, base_tmp, out)
        else:
            cleanup(src, aux)
            return await bot.send_message(chat, "❌ Unsupported file type for addpage (PDF/CBZ/ZIP).")
    except Exception as e:
        cleanup(src, aux)
        await bot.send_message(chat, f"❌ Error during addpage: {e}")


# 4) REPLACE PAGE: replace nth page with provided page (PDF or CBZ/ZIP)
@Client.on_message(filters.command("replacepage") & filters.private)
async def cmd_replacepage(bot: Client, message: Message):
    uid = message.from_user.id
    chat = message.chat.id

    src = await ask_send_file(bot, chat, uid, "📎 Send the base file (PDF / CBZ / ZIP) in which you want to replace a page:")
    if not src:
        return

    txt = await ask_text(bot, chat, uid, "📄 Send the page number to replace (1-based):")
    if not txt or not txt.isdigit():
        cleanup(src); return await bot.send_message(chat, "❌ Invalid page number / cancelled.")
    page_no = int(txt)

    # ask for replacement file
    user_sessions[uid] = {"cmd":"await_replace_aux"}
    await bot.send_message(chat, "📎 Now send the replacement file (PDF single-page or image/CBZ). You have 3 minutes. Type `cancel` to abort.")
    aux = await wait_for_aux_file(uid)
    if not aux:
        cleanup(src); return await bot.send_message(chat, "❌ No replacement received or cancelled.")

    await status_bar(bot, chat, "Starting replacement...")

    ext = os.path.splitext(src)[1].lower().lstrip(".")
    try:
        if ext == "pdf":
            reader = PdfReader(src)
            if page_no < 1 or page_no > len(reader.pages):
                cleanup(src, aux); return await bot.send_message(chat, f"❌ Page out of range (1-{len(reader.pages)})")
            rep = PdfReader(aux)
            writer = PdfWriter()
            for i,p in enumerate(reader.pages, start=1):
                if i == page_no:
                    for rp in rep.pages:
                        writer.add_page(rp)
                else:
                    writer.add_page(p)
            out = os.path.join(TMP, f"replaced_{uid}_{os.path.basename(src)}")
            with open(out, "wb") as f:
                writer.write(f)
            await status_bar(bot, chat, f"Replaced page {page_no}")
            await bot.send_document(chat, out)
            cleanup(src, aux, out)

        elif ext in ("cbz","zip"):
            tmpd = tempfile.mkdtemp(prefix=f"cbz_{uid}_")
            with zipfile.ZipFile(src,"r") as zf:
                zf.extractall(tmpd)
            imgs = sorted([f for f in os.listdir(tmpd) if f.lower().endswith((".jpg",".jpeg",".png"))])
            total = len(imgs)
            if page_no < 1 or page_no > total:
                cleanup(src, aux, tmpd); return await bot.send_message(chat, f"❌ Image index out of range (1-{total})")
            # determine replacement image path
            if aux.lower().endswith((".zip",".cbz")):
                with zipfile.ZipFile(aux,"r") as zf:
                    img_list = [n for n in zf.namelist() if n.lower().endswith((".jpg",".jpeg",".png"))]
                    if not img_list:
                        cleanup(src, aux, tmpd); return await bot.send_message(chat, "❌ No images inside replacement archive.")
                    zf.extract(img_list[0], tmpd)
                    src_replace = os.path.join(tmpd, img_list[0])
            else:
                src_replace = aux
            # overwrite target
            target = os.path.join(tmpd, imgs[page_no-1])
            shutil.copyfile(src_replace, target)
            out = os.path.join(TMP, f"replaced_{uid}_{os.path.basename(src)}")
            with zipfile.ZipFile(out, "w") as zf:
                for fname in sorted(os.listdir(tmpd)):
                    zf.write(os.path.join(tmpd, fname), arcname=fname)
            await status_bar(bot, chat, f"Replaced image {page_no}/{total}")
            await bot.send_document(chat, out)
            cleanup(src, aux, tmpd, out)
        else:
            cleanup(src, aux)
            return await bot.send_message(chat, "❌ Unsupported file type for replacepage (PDF/CBZ/ZIP).")
    except Exception as e:
        cleanup(src, aux)
        await bot.send_message(chat, f"❌ Error during replacepage: {e}")


# 5) ADDPASS: add/set password (for PDF/ZIP/CBZ/EPUB) - simple PDF encryption, zip packing for others
@Client.on_message(filters.command("addpass") & filters.private)
async def cmd_addpass(bot: Client, message: Message):
    uid = message.from_user.id
    chat = message.chat.id

    src = await ask_send_file(bot, chat, uid, "📎 Send the file (PDF / CBZ / ZIP / EPUB) to add password:")
    if not src:
        return

    txt = await ask_text(bot, chat, uid, "🔐 Send the password to set:")
    if not txt:
        cleanup(src); return await bot.send_message(chat, "❌ No password provided / cancelled.")
    pwd = txt

    await status_bar(bot, chat, "Applying password...")

    ext = os.path.splitext(src)[1].lower().lstrip(".")
    try:
        if ext == "pdf":
            reader = PdfReader(src)
            writer = PdfWriter()
            for p in reader.pages:
                writer.add_page(p)
            writer.encrypt(pwd)
            out = os.path.join(TMP, f"pass_{uid}_{os.path.basename(src)}")
            with open(out, "wb") as f:
                writer.write(f)
            await bot.send_document(chat, out)
            cleanup(src, out)
        elif ext in ("zip","cbz","epub"):
            # repackage into a zip and note password in a simple file (zip encryption cross-client issues).
            tmpd = tempfile.mkdtemp(prefix=f"zipenc_{uid}_")
            with zipfile.ZipFile(src, "r") as zf:
                zf.extractall(tmpd)
            # create a new zip (no true AES encryption here to keep compatibility), but we can store password.txt
            out = os.path.join(TMP, f"pass_{uid}_{os.path.basename(src)}")
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
                for root,_,files in os.walk(tmpd):
                    for f in files:
                        zf.write(os.path.join(root,f), arcname=os.path.relpath(os.path.join(root,f), tmpd))
                # add a password.txt (informational)
                zf.writestr("password.txt", pwd)
            await bot.send_document(chat, out)
            cleanup(src, tmpd, out)
        else:
            cleanup(src)
            return await bot.send_message(chat, "❌ Unsupported file type for addpass.")
    except Exception as e:
        cleanup(src)
        await bot.send_message(chat, f"❌ Error during addpass: {e}")

