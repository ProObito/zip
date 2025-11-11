
import os
import shutil
import tempfile
import zipfile
import asyncio
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import Message
from PyPDF2 import PdfReader, PdfWriter
import pyzipper

TMP_DIR = "downloads"
os.makedirs(TMP_DIR, exist_ok=True)

# sessions: per-user interactive state
# session structure: { user_id: {"cmd": "addpass"/"removepass", "stage": "await_file"/"await_password", "file": "/path/to/file"} }
sessions: dict[int, dict] = {}
TIMEOUT = 180  # seconds (3 minutes)


def cleanup(*paths):
    for p in paths:
        if not p:
            continue
        try:
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            elif os.path.exists(p):
                os.remove(p)
        except Exception:
            pass


# ---------- Helpers ----------
async def wait_for_password(user_id: int, chat_id: int) -> Optional[str]:
    """
    Wait until the user sends a text message that should be treated as password,
    or user types 'cancel'. This function relies on the global `sessions` and
    the text handler which writes password into sessions[user_id]["password"].
    """
    for _ in range(TIMEOUT):
        await asyncio.sleep(1)
        sess = sessions.get(user_id)
        if not sess:
            return None
        if "password" in sess:
            return sess.pop("password")
    # timeout
    sessions.pop(user_id, None)
    return None


# ---------- Start commands ----------
@Client.on_message(filters.command("addpass") & filters.private)
async def cmd_addpass_start(bot: Client, message: Message):
    uid = message.from_user.id
    sessions[uid] = {"cmd": "addpass", "stage": "await_file"}
    await message.reply_text(
        "📂 *AddPass*: Reply to this message with the file you want to protect.\n\n"
        "Supported formats: `.pdf`, `.zip`, `.cbz`, `.epub`.\n"
        "You have 3 minutes. Type `cancel` to abort.",
        quote=True
    )


@Client.on_message(filters.command("removepass") & filters.private)
async def cmd_removepass_start(bot: Client, message: Message):
    uid = message.from_user.id
    sessions[uid] = {"cmd": "removepass", "stage": "await_file"}
    await message.reply_text(
        "📂 *RemovePass*: Reply to this message with the locked file you want to unlock.\n\n"
        "Supported formats: `.pdf`, `.zip`, `.cbz`, `.epub`.\n"
        "You have 3 minutes. Type `cancel` to abort.",
        quote=True
    )


# ---------- Document handler (receives the file) ----------
@Client.on_message(filters.document & filters.private)
async def document_receiver(bot: Client, message: Message):
    uid = message.from_user.id
    sess = sessions.get(uid)
    if not sess:
        return  # not expecting a file from this user

    # Only accept the file if user replied to the bot's prompt message OR we are in await_file stage
    # (some clients may not keep reply; we still accept if session exists and stage matches)
    if sess.get("stage") != "await_file":
        return

    # download file
    file_name = message.document.file_name or f"{uid}_file"
    dst = os.path.join(TMP_DIR, f"{uid}_{int(asyncio.get_event_loop().time())}_{file_name}")
    try:
        downloaded = await message.download(file_name=dst)
    except Exception as e:
        await message.reply_text(f"❌ Failed to download the file: {e}")
        sessions.pop(uid, None)
        return

    sess["file"] = downloaded
    sess["stage"] = "await_password"
    await message.reply_text(
        "🔐 File received. Now reply to this chat with the password to use (or current password to remove).\n"
        "Type `cancel` to abort. You have 3 minutes.",
        quote=True
    )

    # Optionally we could auto-wait here, but flow uses text listener to pick up password.


# ---------- Text handler (receives password or cancel) ----------
@Client.on_message(filters.text & filters.private)
async def text_receiver(bot: Client, message: Message):
    uid = message.from_user.id
    text = message.text.strip()
    sess = sessions.get(uid)
    if not sess:
        return

    # cancel
    if text.lower() == "cancel":
        sessions.pop(uid, None)
        await message.reply_text("❌ Operation cancelled.")
        return

    # if waiting for password, store and trigger processing
    if sess.get("stage") == "await_password":
        sessions[uid]["password"] = text
        # process in background so this handler can return quickly
        asyncio.create_task(process_session(bot, message.chat.id, uid))
        return

    # any other text while not expecting it -> ignore
    return


# ---------- Core processing ----------
async def process_session(bot: Client, chat_id: int, user_id: int):
    """
    Called after user provided file and password. Processes according to sessions[user_id]["cmd"].
    """
    sess = sessions.get(user_id)
    if not sess:
        return
    cmd = sess.get("cmd")
    file_path = sess.get("file")
    password = sess.pop("password", None)
    # mark as processing
    sess["stage"] = "processing"

    # remove session at end
    try:
        if not file_path or not os.path.exists(file_path):
            await bot.send_message(chat_id, "❌ File missing or failed to download.")
            return

        ext = os.path.splitext(file_path)[1].lower().lstrip(".")

        if cmd == "addpass":
            await handle_addpass(bot, chat_id, file_path, ext, password)
        elif cmd == "removepass":
            await handle_removepass(bot, chat_id, file_path, ext, password)
        else:
            await bot.send_message(chat_id, "❌ Unknown session command.")
    finally:
        # cleanup session
        sessions.pop(user_id, None)


# ---------- Handlers for formats ----------
async def handle_addpass(bot: Client, chat_id: int, path: str, ext: str, password: str):
    out_path = None
    try:
        if ext == "pdf":
            # PDF encrypt
            reader = PdfReader(path)
            writer = PdfWriter()
            for p in reader.pages:
                writer.add_page(p)
            writer.encrypt(password)
            out_path = path + ".locked.pdf"
            with open(out_path, "wb") as f:
                writer.write(f)
            await bot.send_document(chat_id, out_path, caption="✅ PDF password added.")

        elif ext in ("zip", "cbz", "epub"):
            # Use pyzipper AES encryption for zip-like formats
            out_path = path + ".locked.zip"
            with pyzipper.AESZipFile(out_path, 'w', compression=pyzipper.ZIP_DEFLATED,
                                     encryption=pyzipper.WZ_AES) as zf_out:
                zf_out.setpassword(password.encode())
                # If original is a zip-like, copy entries
                if ext in ("zip", "cbz", "epub"):
                    # read entries from original zip if zip-like
                    try:
                        with zipfile.ZipFile(path, 'r') as zf_in:
                            for info in zf_in.infolist():
                                data = zf_in.read(info.filename)
                                zf_out.writestr(info.filename, data)
                    except zipfile.BadZipFile:
                        # if not actually zip (rare), just add the file itself
                        with open(path, 'rb') as f:
                            zf_out.writestr(os.path.basename(path), f.read())
            await bot.send_document(chat_id, out_path, caption="✅ Archive password added (AES zip).")

        else:
            await bot.send_message(chat_id, "❌ Unsupported file type for addpass. Use PDF/ZIP/CBZ/EPUB.")
    except Exception as e:
        await bot.send_message(chat_id, f"⚠️ addpass failed: {e}")
    finally:
        # cleanup originals and output (keep short-lived)
        try:
            if os.path.exists(path):
                os.remove(path)
        except: pass
        # leave out_path for user to download then remove it after sending
        if out_path and os.path.exists(out_path):
            try:
                # give a short delay to ensure upload started/completed
                await asyncio.sleep(1)
                os.remove(out_path)
            except: pass


async def handle_removepass(bot: Client, chat_id: int, path: str, ext: str, password: str):
    out_path = None
    tmpdir = None
    try:
        if ext == "pdf":
            reader = PdfReader(path)
            if reader.is_encrypted:
                try:
                    reader.decrypt(password)
                except Exception:
                    # PyPDF2 sometimes doesn't raise; try alternative
                    await bot.send_message(chat_id, "❌ Wrong password or cannot decrypt PDF.")
                    return
            writer = PdfWriter()
            for p in reader.pages:
                writer.add_page(p)
            out_path = path + ".unlocked.pdf"
            with open(out_path, "wb") as f:
                writer.write(f)
            await bot.send_document(chat_id, out_path, caption="✅ PDF unlocked (password removed).")

        elif ext in ("zip", "cbz", "epub"):
            # Try to open with pyzipper using password; extract and rezip without password
            tmpdir = tempfile.mkdtemp(prefix="unzip_")
            try:
                with pyzipper.AESZipFile(path, 'r') as zf:
                    zf.pwd = password.encode()
                    zf.extractall(tmpdir)
            except RuntimeError as re:
                await bot.send_message(chat_id, "❌ Wrong password or cannot decrypt archive.")
                cleanup(tmpdir)
                return
            # rezip without password
            out_path = os.path.join(TMP_DIR, os.path.basename(path) + ".unlocked.zip")
            with zipfile.ZipFile(out_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf_out:
                for root, _, files in os.walk(tmpdir):
                    for fname in files:
                        full = os.path.join(root, fname)
                        arcname = os.path.relpath(full, tmpdir)
                        zf_out.write(full, arcname=arcname)
            await bot.send_document(chat_id, out_path, caption="✅ Archive unlocked (password removed).")
        else:
            await bot.send_message(chat_id, "❌ Unsupported file type for removepass. Use PDF/ZIP/CBZ/EPUB.")
    except Exception as e:
        await bot.send_message(chat_id, f"⚠️ removepass failed: {e}")
    finally:
        # cleanup
        try:
            if os.path.exists(path):
                os.remove(path)
        except: pass
        if tmpdir:
            cleanup(tmpdir)
        if out_path and os.path.exists(out_path):
            try:
                await asyncio.sleep(1)
                os.remove(out_path)
            except: pass
