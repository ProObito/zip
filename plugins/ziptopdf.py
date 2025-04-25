# +++ Made By Obito [telegram username: @i_killed_my_clan] +++ #
import os
import zipfile
import tempfile
import asyncio
import shutil
from PIL import Image
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import SUPPORT_CHAT
from database import is_autho_user_exist, get_thumbnail, get_banner_status, get_banner_image, get_banner_url, get_banner_position
from utils import natural_sort, remove_duplicates, create_banner_pdf, add_banner_to_pdf

async def generate_pdf(image_files, output_path, thumbnail_path=None, banner_path=None, banner_position="first"):
    image_iter = (Image.open(f).convert("RGB") for f in image_files)
    first = next(image_iter)
    first.save(
        output_path,
        save_all=True,
        append_images=image_iter,
        cover=Image.open(thumbnail_path).convert("RGB") if thumbnail_path else None
    )
    if banner_path:
        temp_pdf = output_path + ".temp.pdf"
        os.rename(output_path, temp_pdf)
        add_banner_to_pdf(temp_pdf, output_path, banner_path, banner_position)
        os.remove(temp_pdf)

async def generate_cbz(image_files, output_path, banner_path=None, banner_position="first"):
    with tempfile.TemporaryDirectory() as temp_dir:
        for i, img_path in enumerate(image_files):
            img = Image.open(img_path).convert("RGB")
            img.save(os.path.join(temp_dir, f"image_{i:03d}.jpg"), "JPEG")
        if banner_path and os.path.exists(banner_path):
            banner_img = Image.open(banner_path).convert("RGB")
            if banner_position in ["first", "both"]:
                banner_img.save(os.path.join(temp_dir, "image_000.jpg"), "JPEG")
            if banner_position in ["last", "both"]:
                banner_img.save(os.path.join(temp_dir, f"image_{len(image_files) + 1:03d}.jpg"), "JPEG")
        shutil.make_archive(output_path.replace(".cbz", ""), "zip", temp_dir)
        os.rename(output_path.replace(".cbz", ".zip"), output_path)

async def handle_zip_file(client: Client, message):
    user_id = message.from_user.id
    check = await is_autho_user_exist(user_id)
    if not check:
        await message.reply_text(
            f"<b>⚠️ You are not an Authorised User ⚠️</b>\n"
            f"<blockquote>Contact {SUPPORT_CHAT} to get authorized.</blockquote>",
            parse_mode="html"
        )
        return

    buttons = [
        [InlineKeyboardButton("Zip to PDF 📄", callback_data=f"zip_to_pdf_{message.message_id}")],
        [InlineKeyboardButton("Zip to CBZ 📚", callback_data=f"zip_to_cbz_{message.message_id}")],
        [InlineKeyboardButton("Unzip 📂", callback_data=f"unzip_{message.message_id}")],
        [InlineKeyboardButton("Merge ZIP 🔗", callback_data=f"merge_zip_{message.message_id}")],
        [InlineKeyboardButton("Rename ✏️", callback_data=f"rename_zip_{message.message_id}")],
        [InlineKeyboardButton("Remove Page 📃", callback_data=f"remove_page_{message.message_id}")],
        [InlineKeyboardButton("Close ❌", callback_data="close")]
    ]
    await message.reply_text(
        "File received! Choose an option below:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="html"
    )

async def zip_to_pdf_callback(client: Client, callback_query):
    user_id = callback_query.from_user.id
    message_id = int(callback_query.data.split("_")[3])
    check = await is_autho_user_exist(user_id)
    if not check:
        await callback_query.answer("You are not authorized.", show_alert=True)
        return

    message = callback_query.message.reply_to_message
    if not message or not message.document:
        await callback_query.answer("No document found.", show_alert=True)
        return

    document = message.document
    if not document.file_name.endswith(".zip"):
        await callback_query.answer("Please send a ZIP file.", show_alert=True)
        return

    zip_name = os.path.splitext(document.file_name)[0]
    await callback_query.message.edit_text("📂 Processing your ZIP file...")

    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, document.file_name)
        extract_folder = os.path.join(temp_dir, f"{zip_name}_extracted")
        pdf_path = os.path.join(temp_dir, f"{zip_name}.pdf")

        try:
            await message.download(zip_path)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_folder)
        except Exception as e:
            await callback_query.message.edit_text(f"❌ Error processing ZIP: {e}")
            return

        valid_extensions = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".img")
        image_files = natural_sort([
            os.path.join(extract_folder, f) for f in os.listdir(extract_folder)
            if f.lower().endswith(valid_extensions)
        ])

        if not image_files:
            await callback_query.message.edit_text("❌ No images found in the ZIP.")
            return

        banner_status = await get_banner_status(user_id)
        banner_path = None
        if banner_status:
            banner_image = await get_banner_image(user_id)
            banner_url = await get_banner_url(user_id)
            if banner_image:
                banner_path = create_banner_pdf(banner_image, banner_url)

        thumbnail_path = await get_thumbnail(user_id)
        banner_position = await get_banner_position(user_id)

        try:
            await generate_pdf(image_files, pdf_path, thumbnail_path, banner_path, banner_position)
            await client.send_document(
                chat_id=message.chat.id,
                document=pdf_path,
                caption=f"Here is your PDF: {zip_name}.pdf 📄",
                reply_to_message_id=message_id
            )
            await callback_query.message.edit_text("✅ PDF generated and sent!")
        except Exception as e:
            await callback_query.message.edit_text(f"❌ Error generating PDF: {e}")

async def zip_to_cbz_callback(client: Client, callback_query):
    user_id = callback_query.from_user.id
    message_id = int(callback_query.data.split("_")[3])
    check = await is_autho_user_exist(user_id)
    if not check:
        await callback_query.answer("You are not authorized.", show_alert=True)
        return

    message = callback_query.message.reply_to_message
    if not message or not message.document:
        await callback_query.answer("No document found.", show_alert=True)
        return

    document = message.document
    if not document.file_name.endswith(".zip"):
        await callback_query.answer("Please send a ZIP file.", show_alert=True)
        return

    zip_name = os.path.splitext(document.file_name)[0]
    await callback_query.message.edit_text("📂 Processing your ZIP file...")

    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, document.file_name)
        extract_folder = os.path.join(temp_dir, f"{zip_name}_extracted")
        cbz_path = os.path.join(temp_dir, f"{zip_name}.cbz")

        try:
            await message.download(zip_path)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_folder)
        except Exception as e:
            await callback_query.message.edit_text(f"❌ Error processing ZIP: {e}")
            return

        valid_extensions = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".img")
        image_files = natural_sort([
            os.path.join(extract_folder, f) for f in os.listdir(extract_folder)
            if f.lower().endswith(valid_extensions)
        ])

        if not image_files:
            await callback_query.message.edit_text("❌ No images found in the ZIP.")
            return

        banner_status = await get_banner_status(user_id)
        banner_image = await get_banner_image(user_id) if banner_status else None
        banner_position = await get_banner_position(user_id)

        try:
            await generate_cbz(image_files, cbz_path, banner_image, banner_position)
            await client.send_document(
                chat_id=message.chat.id,
                document=cbz_path,
                caption=f"Here is your CBZ: {zip_name}.cbz 📚",
                reply_to_message_id=message_id
            )
            await callback_query.message.edit_text("✅ CBZ generated and sent!")
        except Exception as e:
            await callback_query.message.edit_text(f"❌ Error generating CBZ: {e}")

async def unzip_callback(client: Client, callback_query):
    user_id = callback_query.from_user.id
    message_id = int(callback_query.data.split("_")[1])
    check = await is_autho_user_exist(user_id)
    if not check:
        await callback_query.answer("You are not authorized.", show_alert=True)
        return

    message = callback_query.message.reply_to_message
    if not message or not message.document:
        await callback_query.answer("No document found.", show_alert=True)
        return

    document = message.document
    if not document.file_name.endswith(".zip"):
        await callback_query.answer("Please send a ZIP file.", show_alert=True)
        return

    zip_name = os.path.splitext(document.file_name)[0]
    await callback_query.message.edit_text("📂 Unzipping your file...")

    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, document.file_name)
        extract_folder = os.path.join(temp_dir, f"{zip_name}_extracted")

        try:
            await message.download(zip_path)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_folder)
            for file in os.listdir(extract_folder):
                file_path = os.path.join(extract_folder, file)
                await client.send_document(
                    chat_id=message.chat.id,
                    document=file_path,
                    caption=f"Unzipped file: {file}",
                    reply_to_message_id=message_id
                )
            await callback_query.message.edit_text("✅ Files unzipped and sent!")
        except Exception as e:
            await callback_query.message.edit_text(f"❌ Error unzipping: {e}")

async def merge_zip_callback(client: Client, callback_query):
    user_id = callback_query.from_user.id
    message_id = int(callback_query.data.split("_")[2])
    check = await is_autho_user_exist(user_id)
    if not check:
        await callback_query.answer("You are not authorized.", show_alert=True)
        return

    await callback_query.message.edit_text(
        "📂 Send additional ZIP files to merge. You have 60 seconds to send at least one more ZIP."
    )

    zip_files = [callback_query.message.reply_to_message.document]
    try:
        while True:
            zip_msg = await client.listen(
                callback_query.message.chat.id,
                filters=filters.document & filters.create(
                    lambda _, __, m: m.document and m.document.file_name.endswith(".zip")
                ),
                timeout=60
            )
            zip_files.append(zip_msg.document)
            await zip_msg.reply_text("ZIP received. Send another or wait 10 seconds to proceed.")
            await asyncio.sleep(10)
    except asyncio.TimeoutError:
        pass

    if len(zip_files) < 2:
        await callback_query.message.edit_text("❌ At least two ZIP files are required to merge.")
        return

    await callback_query.message.edit_text("📂 Merging ZIP files...")

    with tempfile.TemporaryDirectory() as temp_dir:
        merged_folder = os.path.join(temp_dir, "merged")
        os.makedirs(merged_folder)
        for i, doc in enumerate(zip_files):
            zip_path = os.path.join(temp_dir, f"zip_{i}.zip")
            extract_folder = os.path.join(temp_dir, f"extract_{i}")
            await doc.download(zip_path)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_folder)
            for root, _, files in os.walk(extract_folder):
                for file in files:
                    src = os.path.join(root, file)
                    dst = os.path.join(merged_folder, file)
                    shutil.copy(src, dst)

        merged_zip_path = os.path.join(temp_dir, "merged.zip")
        shutil.make_archive(os.path.splitext(merged_zip_path)[0], "zip", merged_folder)

        try:
            await client.send_document(
                chat_id=callback_query.message.chat.id,
                document=merged_zip_path,
                caption="Here is your merged ZIP file.",
                reply_to_message_id=message_id
            )
            await callback_query.message.edit_text("✅ ZIP files merged and sent!")
        except Exception as e:
            await callback_query.message.edit_text(f"❌ Error sending merged ZIP: {e}")

async def rename_zip_callback(client: Client, callback_query):
    user_id = callback_query.from_user.id
    message_id = int(callback_query.data.split("_")[2])
    check = await is_autho_user_exist(user_id)
    if not check:
        await callback_query.answer("You are not authorized.", show_alert=True)
        return

    message = callback_query.message.reply_to_message
    if not message or not message.document:
        await callback_query.answer("No document found.", show_alert=True)
        return

    document = message.document
    if not document.file_name.endswith(".zip"):
        await callback_query.answer("Please send a ZIP file.", show_alert=True)
        return

    await callback_query.message.edit_text(
        "✏️ Please send the new file name (including .zip extension) within 60 seconds."
    )

    try:
        rename_msg = await client.listen(
            callback_query.message.chat.id,
            filters=filters.text,
            timeout=60
        )
        new_name = rename_msg.text.strip()
        if not new_name.endswith(".zip"):
            await callback_query.message.edit_text("❌ File name must end with .zip.")
            return

        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, document.file_name)
            new_zip_path = os.path.join(temp_dir, new_name)
            await message.download(zip_path)
            shutil.copy(zip_path, new_zip_path)

            banner_status = await get_banner_status(user_id)
            if banner_status:
                banner_image = await get_banner_image(user_id)
                banner_url = await get_banner_url(user_id)
                banner_position = await get_banner_position(user_id)
                if banner_image:
                    extract_folder = os.path.join(temp_dir, "extracted")
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_folder)
                    valid_extensions = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".img")
                    image_files = natural_sort([
                        os.path.join(extract_folder, f) for f in os.listdir(extract_folder)
                        if f.lower().endswith(valid_extensions)
                    ])
                    if image_files:
                        pdf_path = os.path.join(temp_dir, f"{os.path.splitext(new_name)[0]}.pdf")
                        banner_path = create_banner_pdf(banner_image, banner_url)
                        await generate_pdf(image_files, pdf_path, banner_path=banner_path, banner_position=banner_position)
                        await client.send_document(
                            chat_id=message.chat.id,
                            document=pdf_path,
                            caption=f"Here is your renamed file with banner: {os.path.basename(pdf_path)}",
                            reply_to_message_id=message_id
                        )
                        await callback_query.message.edit_text("✅ File renamed and banner added!")
                        return

            await client.send_document(
                chat_id=message.chat.id,
                document=new_zip_path,
                caption=f"Here is your renamed file: {new_name}",
                reply_to_message_id=message_id
            )
            await callback_query.message.edit_text("✅ File renamed and sent!")
    except asyncio.TimeoutError:
        await callback_query.message.edit_text("⏰ Timeout: No file name received within 60 seconds.")
    except Exception as e:
        await callback_query.message.edit_text(f"❌ Error renaming file: {e}")

async def remove_page_callback(client: Client, callback_query):
    user_id = callback_query.from_user.id
    message_id = int(callback_query.data.split("_")[2])
    check = await is_autho_user_exist(user_id)
    if not check:
        await callback_query.answer("You are not authorized.", show_alert=True)
        return

    message = callback_query.message.reply_to_message
    if not message or not message.document:
        await callback_query.answer("No document found.", show_alert=True)
        return

    document = message.document
    if not document.file_name.endswith(".zip"):
        await callback_query.answer("Please send a ZIP file.", show_alert=True)
        return

    await callback_query.message.edit_text(
        "📃 Please send the page number to remove (0-based index) within 60 seconds."
    )

    try:
        page_msg = await client.listen(
            callback_query.message.chat.id,
            filters=filters.text & filters.create(lambda _, __, m: m.text.strip().isdigit()),
            timeout=60
        )
        page_number = int(page_msg.text.strip())
        zip_name = os.path.splitext(document.file_name)[0]

        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, document.file_name)
            extract_folder = os.path.join(temp_dir, f"{zip_name}_extracted")
            pdf_path = os.path.join(temp_dir, f"{zip_name}.pdf")
            output_pdf = os.path.join(temp_dir, f"{zip_name}_modified.pdf")

            await message.download(zip_path)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_folder)

            valid_extensions = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".img")
            image_files = natural_sort([
                os.path.join(extract_folder, f) for f in os.listdir(extract_folder)
                if f.lower().endswith(valid_extensions)
            ])

            if not image_files:
                await callback_query.message.edit_text("❌ No images found in the ZIP.")
                return

            await generate_pdf(image_files, pdf_path)
            remove_page_from_pdf(pdf_path, output_pdf, page_number)

            await client.send_document(
                chat_id=message.chat.id,
                document=output_pdf,
                caption=f"Here is your PDF with page {page_number} removed: {os.path.basename(output_pdf)}",
                reply_to_message_id=message_id
            )
            await callback_query.message.edit_text("✅ Page removed and PDF sent!")
    except asyncio.TimeoutError:
        await callback_query.message.edit_text("⏰ Timeout: No page number received within 60 seconds.")
    except Exception as e:
        await callback_query.message.edit_text(f"❌ Error removing page: {e}")

def register_handlers(app: Client):
    app.on_message(filters.private & filters.document & filters.regex(r"\.zip$"))(handle_zip_file)
    app.on_callback_query(filters.regex(r"zip_to_pdf_\d+"))(zip_to_pdf_callback)
    app.on_callback_query(filters.regex(r"zip_to_cbz_\d+"))(zip_to_cbz_callback)
    app.on_callback_query(filters.regex(r"unzip_\d+"))(unzip_callback)
    app.on_callback_query(filters.regex(r"merge_zip_\d+"))(merge_zip_callback)
    app.on_callback_query(filters.regex(r"rename_zip_\d+"))(rename_zip_callback)
    app.on_callback_query(filters.regex(r"remove_page_\d+"))(remove_page_callback)
