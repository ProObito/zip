import os
import shutil
import zipfile
import asyncio
import tempfile
from typing import Optional, List
from pyrogram import Client, filters
from pyrogram.types import Message
from PyPDF2 import PdfReader, PdfWriter
from helper.database import get_thumbnail

# temp dir
TMP = "downloads"
os.makedirs(TMP, exist_ok=True)

# session store for interactive flows
user_sessions = {}
# session structure examples:
# user_sessions[uid] = {
#   "cmd": "addpage_pdf" / "replacepage_cbz" / "await_newname",
#   "base_path": "/tmp/..",
#   "aux_path": "/tmp/..",            # for insert/replace (if any)
#   "page_no": 3,
#   "result_path": "/tmp/..",
#   "timeout_task": task
# }

# ---------- helpers ----------
async def ask_for_text(bot: Client, chat_id: int, user_id: int, prompt: str, timeout: int = 180) -> Optional[str]:
    """
    Ask the user a text input; waits up to timeout seconds or until user sends 'cancel'.
    Uses user_sessions to mark waiting state; caller must cleanup session entries.
    """
    marker = f"asktxt_{user_id}_{int(asyncio.get_event_loop().time())}"
    user_sessions[user_id] = {"cmd": marker}
    await bot.send_message(chat_id, prompt + f"\n⏳ You have {timeout//60} minute(s). Type `cancel` to cancel.")
    try:
        for _ in range(timeout):
            await asyncio.sleep(1)
            sess = user_sessions.get(user_id)
            if not sess:
                return None
            # if user wrote direct text into session (listener sets it), return
            if "text" in sess:
                text = sess.pop("text")
                user_sessions.pop(user_id, None)
                if text.lower() == "cancel":
                    await bot.send_message(chat_id, "❌ Operation cancelled.")
                    return None
                return text
        # timeout
        user_sessions.pop(user_id, None)
        await bot.send_message(chat_id, "❌ Timeout. No input received.")
        return None
    except Exception:
        user_sessions.pop(user_id, None)
        return None

def cleanup_paths(*paths):
    for p in paths:
        try:
            if p and os.path.exists(p):
                if os.path.isdir(p):
                    shutil.rmtree(p)
                else:
                    os.remove(p)
        except:
            pass

async def send_with_newname_and_thumb(bot: Client, chat_id:int, user_id:int, file_path: str, suggested_ext: str):
    """
    After an operation, ask user for new file name and send file with that name and user's thumbnail.
    If user provides empty name or 'skip', default name will be used.
    """
    base_suggest = f"result{int(asyncio.get_event_loop().time())}"
    prompt = "Send a new name for the final file (without extension), or type `skip` to use default."
    name = await ask_for_text(bot, chat_id, user_id, prompt, timeout=180)
    if name is None:
        # cancelled or timeout already handled by ask_for_text
        # still try to send with default name
        out_name = f"{base_suggest}.{suggested_ext}"
    elif name.strip().lower() == "skip" or name.strip() == "":
        out_name = f"{base_suggest}.{suggested_ext}"
    else:
        safe = name.strip().replace("/", "_").replace("\\", "_")
        out_name = f"{safe}.{suggested_ext}"

    # get thumb
    thumb = await get_thumbnail(user_id)
    thumb_path = None
    if thumb:
        # get_thumbnail already returns a local path per your helper (downloads/<id>_thumb.jpg)
        thumb_path = thumb if os.path.exists(thumb) else None

    # send file
    await bot.send_document(chat_id, document=file_path, caption=f"✅ Done: `{out_name}`", thumb=thumb_path)

    # no rename needed on disk as send_document supports caption; but user asked for name - better to rename before sending
    # We'll send using a file copy with desired filename (pyrogram uses filename from path; to control it we can provide file as (file, filename) tuple)
    # However Pyrogram send_document allows 'document' param as file path; to set filename we can create a copy with the desired name
    try:
        tmp_named = os.path.join(TMP, out_name)
        shutil.copyfile(file_path, tmp_named)
        await bot.send_document(chat_id, document=tmp_named, caption=f"✅ Sent as `{out_name}`", thumb=thumb_path)
        cleanup_paths(tmp_named)
    except Exception:
        # fallback: already sent original file above
        pass

    # cleanup
    cleanup_paths(file_path, thumb_path)

# ---------- COMMANDS ----------

# ---------- EXTRACT ALL ----------
@Client.on_message(filters.command("extractall") & filters.reply)
async def cmd_extractall(bot: Client, message: Message):
    """Reply to PDF / ZIP / CBZ / EPUB -> extract contents/pages and zip them"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    doc = message.reply_to_message.document
    if not doc:
        return await message.reply("Reply to a document (PDF/ZIP/CBZ/EPUB).")

    src = await message.reply_to_message.download(file_name=os.path.join(TMP, f"{user_id}_{doc.file_name}"))
    ext = os.path.splitext(src)[1].lower().lstrip(".")

    workdir = tempfile.mkdtemp(prefix="extract_")
    try:
        if ext == "pdf":
            reader = PdfReader(src)
            for i, page in enumerate(reader.pages, start=1):
                writer = PdfWriter()
                writer.add_page(page)
                outp = os.path.join(workdir, f"page_{i}.pdf")
                with open(outp, "wb") as f:
                    writer.write(f)

        elif ext in ("zip", "cbz"):
            with zipfile.ZipFile(src, "r") as zf:
                zf.extractall(workdir)

        elif ext == "epub":
            # treat epub as zip, extract internal xhtml assets
            with zipfile.ZipFile(src, "r") as zf:
                for name in zf.namelist():
                    # save only html/xhtml and images
                    if name.lower().endswith((".xhtml", ".html", ".htm", ".jpg", ".jpeg", ".png")):
                        zf.extract(name, path=workdir)
        else:
            return await message.reply("Unsupported format for extraction. Supported: PDF, ZIP, CBZ, EPUB.")

        # package extracted into zip
        out_zip = os.path.join(TMP, f"extracted_{user_id}.zip")
        shutil.make_archive(out_zip.replace(".zip",""), 'zip', workdir)
        out_zip = out_zip  # path already endswith .zip

        # ask for new name and send
        await message.reply_text("✅ Extraction complete. Now choose a name for the resulting ZIP file.")
        await send_with_newname_and_thumb(bot, chat_id, user_id, out_zip, "zip")

    except Exception as e:
        await message.reply(f"❌ Extraction failed: {e}")
    finally:
        cleanup_paths(src)
        cleanup_paths(workdir)


# ---------- REMOVE PAGE (PDF or CBZ) ----------
@Client.on_message(filters.command("removepage") & filters.reply)
async def cmd_removepage(bot: Client, message: Message):
    """Usage: reply to a PDF or CBZ with /removepage <n>"""
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return await message.reply("Usage: /removepage <page_number> (reply to PDF or CBZ)")

    page_no = int(args[1])
    doc = message.reply_to_message.document
    src = await message.reply_to_message.download(file_name=os.path.join(TMP, f"{message.from_user.id}_{doc.file_name}"))
    ext = os.path.splitext(src)[1].lower().lstrip(".")

    try:
        if ext == "pdf":
            reader = PdfReader(src)
            total = len(reader.pages)
            if page_no < 1 or page_no > total:
                return await message.reply(f"Page out of range (1 - {total}).")
            writer = PdfWriter()
            for i, p in enumerate(reader.pages, start=1):
                if i != page_no:
                    writer.add_page(p)
            outp = os.path.join(TMP, f"removed_{os.path.basename(src)}")
            with open(outp, "wb") as f:
                writer.write(f)
            await message.reply_text("✅ Page removed. Send a new name for the final file.")
            await send_with_newname_and_thumb(bot, message.chat.id, message.from_user.id, outp, "pdf")

        elif ext in ("cbz","zip"):
            # treat as archive of images; remove nth image (sorted by name)
            tmpd = tempfile.mkdtemp(prefix="cbz_")
            with zipfile.ZipFile(src, "r") as zf:
                zf.extractall(tmpd)
            # list image-like files sorted
            files = [f for f in os.listdir(tmpd) if f.lower().endswith((".jpg",".jpeg",".png"))]
            files.sort()
            total = len(files)
            if page_no < 1 or page_no > total:
                cleanup_paths(src, tmpd)
                return await message.reply(f"Image index out of range (1 - {total}).")
            # remove target
            to_remove = files[page_no-1]
            os.remove(os.path.join(tmpd, to_remove))
            # rezip into cbz
            outp = os.path.join(TMP, f"removed_{os.path.basename(src)}")
            with zipfile.ZipFile(outp, "w") as zf:
                for f in sorted(os.listdir(tmpd)):
                    zf.write(os.path.join(tmpd,f), arcname=f)
            await message.reply_text("✅ Image removed from archive. Choose a name for the result.")
            await send_with_newname_and_thumb(bot, message.chat.id, message.from_user.id, outp, ext)
            cleanup_paths(tmpd)

        else:
            return await message.reply("Unsupported file type for removepage. Only PDF/CBZ/ZIP supported.")

    except Exception as e:
        await message.reply(f"❌ Error: {e}")
    finally:
        cleanup_paths(src)


# ---------- ADD PAGE (PDF or CBZ) ----------
@Client.on_message(filters.command("addpage") & filters.reply)
async def cmd_addpage(bot: Client, message: Message):
    """Usage for PDF: reply to main PDF with /addpage <n> then send the insert PDF
       Usage for CBZ: reply to CBZ with /addpage <n> then send image(s) as files or a CBZ to insert
    """
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return await message.reply("Usage: /addpage <position> (reply to the main file). The new pages will be inserted AFTER this position.")

    pos = int(args[1])
    doc = message.reply_to_message.document
    src = await message.reply_to_message.download(file_name=os.path.join(TMP, f"{message.from_user.id}_{doc.file_name}"))
    ext = os.path.splitext(src)[1].lower().lstrip(".")

    # ask user to send insertion file(s)
    await message.reply("Now reply with the file(s) to insert:\n- For PDF: send a PDF (can be multi-page)\n- For CBZ/ZIP: send images or a CBZ archive\nYou have 3 minutes. Type `cancel` to abort.")
    # set session and wait for document or text cancel
    user_sessions[message.from_user.id] = {"cmd":"await_addfile", "base": src, "ext": ext, "pos": pos}
    # wait until session updated by listeners (document listener below) or timeout
    try:
        for _ in range(180):
            await asyncio.sleep(1)
            sess = user_sessions.get(message.from_user.id)
            if not sess:
                # cancelled by user via text 'cancel'
                cleanup_paths(src)
                return
            if "aux" in sess:
                aux_path = sess.pop("aux")
                ses = user_sessions.pop(message.from_user.id, None)
                break
        else:
            user_sessions.pop(message.from_user.id, None)
            cleanup_paths(src)
            return await message.reply("❌ Timeout waiting for insert file.")
    except Exception:
        user_sessions.pop(message.from_user.id, None)
        cleanup_paths(src)
        return await message.reply("❌ Interrupted.")

    # aux_path available
    try:
        if ext == "pdf":
            # insert PDF pages
            base_reader = PdfReader(src)
            insert_reader = PdfReader(aux_path)
            writer = PdfWriter()
            for i, p in enumerate(base_reader.pages, start=1):
                writer.add_page(p)
                if i == pos:
                    for ip in insert_reader.pages:
                        writer.add_page(ip)
            # if pos beyond end, append
            if pos > len(base_reader.pages):
                for ip in insert_reader.pages:
                    writer.add_page(ip)
            outp = os.path.join(TMP, f"added_{os.path.basename(src)}")
            with open(outp, "wb") as f:
                writer.write(f)
            await message.reply_text("✅ Pages inserted. Choose a name for final file.")
            await send_with_newname_and_thumb(bot, message.chat.id, message.from_user.id, outp, "pdf")

        elif ext in ("cbz","zip"):
            # insert images into archive
            tmpd = tempfile.mkdtemp(prefix="cbz_")
            with zipfile.ZipFile(src, "r") as zf:
                zf.extractall(tmpd)
            files = sorted([f for f in os.listdir(tmpd) if f.lower().endswith((".jpg",".jpeg",".png"))])
            # handle aux: if aux is a zip/cbz -> extract images; if aux is image file -> single image
            inserts = []
            if aux_path.lower().endswith((".zip",".cbz")):
                with zipfile.ZipFile(aux_path, "r") as zf:
                    for name in zf.namelist():
                        if name.lower().endswith((".jpg",".jpeg",".png")):
                            zf.extract(name, path=tmpd)
                            inserts.append(os.path.join(tmpd, name))
            else:
                # aux_path may be an image or a pdf (we assume image)
                inserts.append(aux_path)
            # build new list with insertion after pos
            new_list = []
            for idx, fname in enumerate(files, start=1):
                new_list.append(os.path.join(tmpd, fname))
                if idx == pos:
                    # copy inserts into tmpd with unique names
                    for ins in inserts:
                        dst = os.path.join(tmpd, f"insert_{int(asyncio.get_event_loop().time())}_{os.path.basename(ins)}")
                        shutil.copyfile(ins, dst)
                        new_list.append(dst)
            # if pos beyond last, append
            if pos >= len(files):
                for ins in inserts:
                    dst = os.path.join(tmpd, f"insert_{int(asyncio.get_event_loop().time())}_{os.path.basename(ins)}")
                    shutil.copyfile(ins, dst)
                    new_list.append(dst)
            # rezip
            outp = os.path.join(TMP, f"added_{os.path.basename(src)}")
            with zipfile.ZipFile(outp, "w") as zf:
                for p in new_list:
                    zf.write(p, arcname=os.path.basename(p))
            await message.reply_text("✅ Items inserted into archive. Choose a name for final file.")
            await send_with_newname_and_thumb(bot, message.chat.id, message.from_user.id, outp, ext)
            cleanup_paths(tmpd)
        else:
            await message.reply("Unsupported file type for addpage (PDF/CBZ/ZIP supported).")
    except Exception as e:
        await message.reply(f"❌ Error during addpage: {e}")
    finally:
        cleanup_paths(src, aux_path)

# document listener to capture auxiliary files or cancel texts
@Client.on_message(filters.document & filters.private)
async def doc_aux_listener(bot: Client, message: Message):
    uid = message.from_user.id
    sess = user_sessions.get(uid)
    if not sess:
        return
    # if waiting for an aux document for addpage/replace
    if sess.get("cmd") == "await_addfile":
        aux = await message.download(file_name=os.path.join(TMP, f"{uid}_aux_{message.document.file_name}"))
        sess["aux"] = aux
    elif sess.get("cmd") == "await_replacefile":
        aux = await message.download(file_name=os.path.join(TMP, f"{uid}_aux_{message.document.file_name}"))
        sess["aux"] = aux

@Client.on_message(filters.text & filters.private)
async def text_session_listener(bot: Client, message: Message):
    uid = message.from_user.id
    sess = user_sessions.get(uid)
    if not sess:
        return
    # if user types cancel while waiting
    if message.text.strip().lower() == "cancel":
        user_sessions.pop(uid, None)
        await message.reply_text("❌ Operation cancelled by user.")
        return
    # store plain text for generic ask_for_text usage
    if sess.get("cmd", "").startswith("asktxt_") or sess.get("cmd","").startswith("await_"):
        sess["text"] = message.text.strip()
        return


# ---------- REPLACE PAGE (PDF / CBZ) ----------
@Client.on_message(filters.command("replacepage") & filters.reply)
async def cmd_replacepage(bot: Client, message: Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return await message.reply("Usage: /replacepage <page_number> (reply to main file)")
    page_no = int(args[1])
    doc = message.reply_to_message.document
    src = await message.reply_to_message.download(file_name=os.path.join(TMP, f"{message.from_user.id}_{doc.file_name}"))
    ext = os.path.splitext(src)[1].lower().lstrip(".")

    # ask user to send replacement
    await message.reply("Now reply with the replacement file (single-page PDF for PDF, image or CBZ for CBZ). You have 3 minutes. Type `cancel` to abort.")
    user_sessions[message.from_user.id] = {"cmd": "await_replacefile", "base": src, "ext": ext, "page_no": page_no}

    try:
        for _ in range(180):
            await asyncio.sleep(1)
            sess = user_sessions.get(message.from_user.id)
            if not sess:
                cleanup_paths(src)
                return
            if "aux" in sess:
                aux = sess.pop("aux")
                user_sessions.pop(message.from_user.id, None)
                break
        else:
            user_sessions.pop(message.from_user.id, None)
            cleanup_paths(src)
            return await message.reply("❌ Timeout waiting for replacement file.")
    except Exception:
        user_sessions.pop(message.from_user.id, None)
        cleanup_paths(src)
        return await message.reply("❌ Interrupted.")

    try:
        if ext == "pdf":
            reader = PdfReader(src)
            if page_no < 1 or page_no > len(reader.pages):
                cleanup_paths(src, aux)
                return await message.reply("Page number out of range.")
            replace_reader = PdfReader(aux)
            writer = PdfWriter()
            for i, p in enumerate(reader.pages, start=1):
                if i == page_no:
                    for rp in replace_reader.pages:
                        writer.add_page(rp)
                else:
                    writer.add_page(p)
            outp = os.path.join(TMP, f"replaced_{os.path.basename(src)}")
            with open(outp, "wb") as f:
                writer.write(f)
            await message.reply_text("✅ Page replaced. Choose new name for final file.")
            await send_with_newname_and_thumb(bot, message.chat.id, message.from_user.id, outp, "pdf")

        elif ext in ("cbz", "zip"):
            tmpd = tempfile.mkdtemp(prefix="cbz_")
            with zipfile.ZipFile(src, "r") as zf:
                zf.extractall(tmpd)
            images = sorted([f for f in os.listdir(tmpd) if f.lower().endswith((".jpg", ".jpeg", ".png"))])
            if page_no < 1 or page_no > len(images):
                cleanup_paths(src, aux, tmpd)
                return await message.reply("Image index out of range.")

            target = os.path.join(tmpd, images[page_no - 1])

            # determine replacement image
            if aux.lower().endswith((".zip", ".cbz")):
                with zipfile.ZipFile(aux, "r") as zf:
                    img_list = [n for n in zf.namelist() if n.lower().endswith((".jpg", ".jpeg", ".png"))]
                    if not img_list:
                        cleanup_paths(src, aux, tmpd)
                        return await message.reply("No image found inside replacement archive.")
                    zf.extract(img_list[0], tmpd)
                    src_replace = os.path.join(tmpd, img_list[0])
            else:
                src_replace = aux

            shutil.copyfile(src_replace, target)

            outp = os.path.join(TMP, f"replaced_{os.path.basename(src)}")
            with zipfile.ZipFile(outp, "w") as zf:
                for fname in sorted(os.listdir(tmpd)):
                    zf.write(os.path.join(tmpd, fname), arcname=fname)

            await message.reply_text("✅ Image replaced. Choose new name for final file.")
            await send_with_newname_and_thumb(bot, message.chat.id, message.from_user.id, outp, ext)
            cleanup_paths(tmpd)
        else:
            await message.reply("Unsupported file type for replacepage (PDF/CBZ/ZIP supported).")

    except Exception as e:
        await message.reply(f"❌ Error during replace: {e}")
    finally:
        cleanup_paths(src, aux)
