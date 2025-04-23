import re
import zipfile
import tempfile
import asyncio
import shutil
from PIL import Image
from pyrogram import Client, filters
from pyrogram.types import Message
import os, re, zipfile, tempfile, asyncio

@Client.on_message(filters.private & filters.command("addautho_user") & filters.user(Config.ADMIN))
async def addauthorise_user(client, message):
    ids = message.text.removeprefix("/addautho_user").strip().split()
    check = 1

    try:
        if len(ids)>0:
            for id in ids:
                if len(id) == 10 and id.isdigit():
                    await madflixbotz.add_autho_user(int(id))
                else:
                    check = 0
                    break
        else:
            check = 0
    except ValueError:
        check = 0

    if check == 1:
        await message.reply_text(f'**Authorised Users Added ✅**\n<blockquote>`{" ".join(ids)}`</blockquote>')
    else:
        await message.reply_text(f"**INVALID USE OF COMMAND:**\n"
                                 "<blockquote>**➪ Check if the command is empty OR the added ID should be correct (10 digit numbers)**</blockquote>")

@Client.on_message(filters.private & filters.command("delautho_user") & filters.user(Config.ADMIN))
async def deleteauthorise_user(client, message):
    ids = message.text.removeprefix("/delautho_user").strip().split()
    check = 1

    try:
        if len(ids)>0:
            for id in ids:
                if len(id) == 10 and id.isdigit():
                    await madflixbotz.remove_autho_user(int(id))
                else:
                    check = 0
                    break
        else:
            check = 0
    except ValueError:
        check = 0

    if check == 1:
        await message.reply_text(f'**Delete Authorised Users 🆑**\n<blockquote>`{" ".join(ids)}`</blockquote>')
    else:
        await message.reply_text(f"**INVALID USE OF COMMAND:**\n"
                                 "<blockquote>**➪ Check if the command is empty OR the added ID should be correct (10 digit numbers)**</blockquote>\n")
                                

@Client.on_message(filters.private & filters.command("autho_users") & filters.user(Config.ADMIN))
async def authorise_user_list(client, message):
    autho_users = await madflixbotz.get_all_autho_users()
    if autho_users:
        autho_users_str = "\n".join(map(str, autho_users))
        await message.reply(f"🚻 **AUTHORIZED USERS:** 🌀\n\n`{autho_users_str}`")
    else:
        await message.reply("No authorized users found.")

    #list = await madflixbotz.get_autho_user
    #await message.reply_text(f"**AUTHORISED USER LIST 🌀**\n<blockquote>`{AUTHO_USER}`</blockquote>")

@Client.on_message(filters.private & filters.command("check_autho"))
async def check_authorise_user(client, message):
    user_id = message.from_user.id
    check = await madflixbotz.is_autho_user_exist(user_id)
    if check:
        await message.reply_text("**Yes, You are Authorised user 🟢**\n**<blockquote>You can send files to Rename..</blockquote>**")
    else:
        await message.reply_text("**Nope, You are not Authorised user 🔴**\n<blockquote>**You can't send files to Rename..**</blockquote>\n**Contact @i_killed_my_clan to add you as Authorised user**")
        

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
 user_id = message.from_user.id
 check = await madflixbotz.is_autho_user_exist(user_id)
 if not check:
    await message.reply_text("<b>⚠️ You are not Authorised User ⚠️<blockquote>If you want to use this bot, then please contact: @Shidoteshika1</blockquote></b>")
    return
 else:
    firstname = message.from_user.first_name
    format_template = await madflixbotz.get_format_template(user_id)
    media_preference = await madflixbotz.get_media_preference(user_id)

def natural_sort(files):
    return sorted(files, key=lambda f: [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', f)])

def remove_duplicates(file_list):
    """Keep base image (e.g., 1.jpg) and remove variants like 1t.jpg."""
    base_map = {}
    valid_extensions = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".img")

    for file in file_list:
        name, ext = os.path.splitext(os.path.basename(file))
        if ext.lower() not in valid_extensions:
            continue
        match = re.match(r"^(\d+)[a-zA-Z]?$", name)
        if match:
            base = match.group(1)
            if base not in base_map or not name.endswith("t"):  # Prefer base over variant
                base_map[base] = file
    return list(base_map.values())

def generate_pdf(image_files, output_path):
    image_iter = (Image.open(f).convert("RGB") for f in image_files)
    first = next(image_iter)
    first.save(output_path, save_all=True, append_images=image_iter)

def natural_sort(file_list):
    """Sorts file names naturally (e.g., img1, img2, img10 instead of img1, img10, img2)."""
    return sorted(file_list, key=lambda f: [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', f)])

@Client.on_message(filters.command("pdf") & filters.private & filters.user(ADMINS))
async def pdf_handler(bot: Client, message: Message):
    await message.reply_text("📂 Please send a ZIP file containing images. You have 30 seconds.")

    try:
        zip_msg = await bot.listen(
            message.chat.id, 
            filters.document & filters.create(lambda _, __, m: m.document and m.document.file_name.endswith(".zip")),
            timeout=30
        )
    except asyncio.TimeoutError:
        return await message.reply_text("⏰ Timeout: No ZIP file received within 30 seconds.")

    zip_name = os.path.splitext(zip_msg.document.file_name)[0]

    # Use temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, zip_msg.document.file_name)
        extract_folder = os.path.join(temp_dir, f"{zip_name}_extracted")
        pdf_path = os.path.join(temp_dir, f"{zip_name}.pdf")

        # Download ZIP file
        await zip_msg.download(zip_path)

        # Extract ZIP file
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_folder)
        except zipfile.BadZipFile:
            return await message.reply_text("❌ Invalid ZIP file.")

        # Supported image formats
        valid_extensions = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".img")

        # Get image files, sorted naturally
        image_files = natural_sort([
            os.path.join(extract_folder, f) for f in os.listdir(extract_folder)
            if f.lower().endswith(valid_extensions)
        ])

        if not image_files:
            return await message.reply_text("❌ No images found in the ZIP.")

        # Convert images to PDF without compression
        try:
            first_image = Image.open(image_files[0]).convert("RGB")

            # Open images without compression
            image_list = [Image.open(img).convert("RGB") for img in image_files[1:]]

            first_image.save(pdf_path, save_all=True, append_images=image_list)
        except Exception as e:
            return await message.reply_text(f"❌ Error converting to PDF: {e}")

        # Upload PDF with delay to avoid Telegram API rate limits
        await asyncio.sleep(2)  # Small delay
        await message.reply_document(pdf_path, caption=f"Here is your PDF: {zip_name}.pdf 📄")
