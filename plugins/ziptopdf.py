import os
import re
import time
import zipfile
import io
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from PIL import Image, ImageDraw, ImageFont
import PyPDF2
import img2pdf
from config import Config

# Initialize Pyrogram client
app = Client(
    "BannerBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN
)

# Store user data (banner settings, temp files, etc.)
user_data = {}

# Default banner settings
DEFAULT_BANNER = {
    "status": False,
    "position": "first",
    "click_url": None,
    "image_path": None,
}

# Create default banner image with settings
def create_banner_image(user_id):
    img = Image.new("RGB", (595, 842), color="white")  # A4 size at 72 DPI
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()

    text = f"""
📄 PDF Banner Settings
▫️ Banner Status: {'✅ Enabled' if user_data.get(user_id, {}).get('banner', DEFAULT_BANNER)['status'] else '❌ Disabled'}
▫️ Current Position: {user_data.get(user_id, {}).get('banner', DEFAULT_BANNER)['position']}
▫️ Click URL: {user_data.get(user_id, {}).get('banner', DEFAULT_BANNER)['click_url'] or 'None'}

Configure your PDF banners:
1. Turn banner on/off
2. Set banner position
3. Add clickable URL
4. Upload banner image
"""
    draw.text((50, 50), text, fill="black", font=font)
    banner_path = f"banner_{user_id}.png"
    img.save(banner_path)
    return banner_path

# Add banner to PDF
def add_banner_to_pdf(input_path, output_path, banner_path, position):
    banner_pdf = None
    if banner_path.endswith((".png", ".jpg", ".jpeg")):
        with open(banner_path, "rb") as img_file:
            banner_pdf = img2pdf.convert(img_file.read())
        banner_pdf = io.BytesIO(banner_pdf)
    elif banner_path.endswith(".pdf"):
        banner_pdf = open(banner_path, "rb")

    input_pdf = PyPDF2.PdfReader(input_path)
    output_pdf = PyPDF2.PdfWriter()

    banner_reader = PyPDF2.PdfReader(banner_pdf)
    banner_page = banner_reader.pages[0]

    if position in ["first", "both"]:
        output_pdf.add_page(banner_page)
    for page in input_pdf.pages:
        output_pdf.add_page(page)
    if position in ["last", "both"]:
        output_pdf.add_page(banner_page)

    with open(output_path, "wb") as f:
        output_pdf.write(f)

    if banner_path.endswith(".pdf"):
        banner_pdf.close()

# Check if user is subscribed to force-sub channels
async def check_subscription(client, user_id):
    for channel in [Config.FORCE_SUB_1, Config.FORCE_SUB_2]:
        try:
            member = await client.get_chat_member(channel, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True

# Handle /start command
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user_id = message.from_user.id
    if not await check_subscription(client, user_id):
        keyboard = [
            [InlineKeyboardButton("Join Channel 1", url=f"https://t.me/{Config.FORCE_SUB_1}")],
            [InlineKeyboardButton("Join Channel 2", url=f"https://t.me/{Config.FORCE_SUB_2}")],
            [InlineKeyboardButton("Check Subscription", callback_data="check_sub")]
        ]
        await message.reply_photo(
            photo=Config.START_PIC,
            caption="Please join both channels to use this bot!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    await message.reply_photo(
        photo=Config.START_PIC,
        caption="Welcome! Use /banner to configure banner settings."
    )
    await client.send_message(Config.LOG_CHANNEL, f"User {user_id} started the bot.")

# Handle /banner command (admin-only)
@app.on_message(filters.command("banner") & filters.private)
async def banner_command(client, message):
    user_id = message.from_user.id
    if user_id not in Config.ADMIN:
        await message.reply("This command is for admins only!")
        return

    if not await check_subscription(client, user_id):
        await message.reply("Please join the required channels first! Use /start to check.")
        return

    if user_id not in user_data:
        user_data[user_id] = {"banner": DEFAULT_BANNER.copy()}

    keyboard = [
        [InlineKeyboardButton("Turn Banner On/Off", callback_data="toggle_banner")],
        [InlineKeyboardButton("Set Banner Position", callback_data="set_position")],
        [InlineKeyboardButton("Add Clickable URL", callback_data="set_url")],
        [InlineKeyboardButton("Upload Banner Image", callback_data="upload_banner")],
        [InlineKeyboardButton("Close", callback_data="close")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await message.reply(
        "Configure your banner settings:", reply_markup=reply_markup
    )
    await client.send_message(Config.LOG_CHANNEL, f"User {user_id} accessed /banner.")

# Handle inline button callbacks
@app.on_callback_query()
async def button_callback(client, query):
    user_id = query.from_user.id
    data = query.data

    if data == "check_sub":
        if await check_subscription(client, user_id):
            await query.message.edit_caption(
                caption="You're subscribed! Use /banner to configure settings.",
                reply_markup=None
            )
        else:
            await query.answer("You haven't joined both channels yet!")
        return

    if user_id not in Config.ADMIN:
        await query.answer("This action is for admins only!")
        return

    if user_id not in user_data:
        user_data[user_id] = {"banner": DEFAULT_BANNER.copy()}

    if data == "toggle_banner":
        user_data[user_id]["banner"]["status"] = not user_data[user_id]["banner"]["status"]
        status = "Enabled" if user_data[user_id]["banner"]["status"] else "Disabled"
        await query.message.reply(f"Banner {status}")
        await query.message.edit_reply_markup(reply_markup=get_main_menu())
        await client.send_message(Config.LOG_CHANNEL, f"User {user_id} toggled banner to {status}.")

    elif data == "set_position":
        keyboard = [
            [InlineKeyboardButton("First Page", callback_data="pos_first")],
            [InlineKeyboardButton("Last Page", callback_data="pos_last")],
            [InlineKeyboardButton("Both", callback_data="pos_both")],
            [InlineKeyboardButton("Back", callback_data="back")]
        ]
        await query.message.edit_reply_markup(InlineKeyboardMarkup(keyboard))

    elif data.startswith("pos_"):
        position = data.split("_")[1]
        user_data[user_id]["banner"]["position"] = position
        await query.message.reply(f"Banner position set to: {position}")
        await query.message.edit_reply_markup(reply_markup=get_main_menu())
        await client.send_message(Config.LOG_CHANNEL, f"User {user_id} set banner position to {position}.")

    elif data == "set_url":
        await query.message.reply("Please send the URL for the banner:")
        user_data[user_id]["awaiting"] = "url"

    elif data == "upload_banner":
        await query.message.reply("Please upload the banner image (within 60 seconds):")
        user_data[user_id]["awaiting"] = "banner_image"
        user_data[user_id]["banner_upload_time"] = time.time()

    elif data == "remove_banner":
        user_data[user_id]["banner"]["image_path"] = None
        await query.message.reply("Banner image removed")
        await query.message.edit_reply_markup(reply_markup=get_main_menu())
        await client.send_message(Config.LOG_CHANNEL, f"User {user_id} removed banner image.")

    elif data == "change_banner":
        await query.message.reply("Please upload the new banner image (within 60 seconds):")
        user_data[user_id]["awaiting"] = "banner_image"
        user_data[user_id]["banner_upload_time"] = time.time()

    elif data == "back" or data == "close":
        await query.message.edit_reply_markup(reply_markup=get_main_menu())

    elif data.startswith("zip_to_pdf_"):
        zip_path = data.split("_", 3)[-1]
        output_pdf = f"output_{user_id}.pdf"
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            images = [f for f in zip_ref.namelist() if f.lower().endswith((".png", ".jpg", ".jpeg"))]
            with open(output_pdf, "wb") as f:
                f.write(img2pdf.convert([zip_ref.read(img) for img in images]))
        await query.message.reply_document(document=output_pdf, filename="converted.pdf")
        os.remove(zip_path)
        os.remove(output_pdf)
        await client.send_message(Config.LOG_CHANNEL, f"User {user_id} converted ZIP to PDF.")

    elif data.startswith("zip_to_cbz_"):
        zip_path = data.split("_", 3)[-1]
        cbz_path = f"output_{user_id}.cbz"
        os.rename(zip_path, cbz_path)
        await query.message.reply_document(document=cbz_path, filename="converted.cbz")
        os.remove(cbz_path)
        await client.send_message(Config.LOG_CHANNEL, f"User {user_id} converted ZIP to CBZ.")

    elif data.startswith("unzip_"):
        zip_path = data.split("_", 2)[-1]
        extract_path = f"extracted_{user_id}"
        os.makedirs(extract_path, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_path)
        for file in os.listdir(extract_path):
            await query.message.reply_document(document=os.path.join(extract_path, file), filename=file)
        os.remove(zip_path)
        os.system(f"rm -rf {extract_path}")
        await client.send_message(Config.LOG_CHANNEL, f"User {user_id} unzipped a file.")

    elif data.startswith("merge_zip_"):
        await query.message.reply("Please upload another ZIP file to merge:")
        user_data[user_id]["awaiting"] = "merge_zip"
        user_data[user_id]["first_zip"] = data.split("_", 3)[-1]

    elif data == "close":
        await query.message.delete()

# Get main menu keyboard
def get_main_menu():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Turn Banner On/Off", callback_data="toggle_banner")],
            [InlineKeyboardButton("Set Banner Position", callback_data="set_position")],
            [InlineKeyboardButton("Add Clickable URL", callback_data="set_url")],
            [InlineKeyboardButton("Upload Banner Image", callback_data="upload_banner")],
            [InlineKeyboardButton("Close", callback_data="close")]
        ]
    )

# Handle text input (e.g., URL)
@app.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    if user_id in user_data and user_data[user_id].get("awaiting") == "url":
        url = message.text
        user_data[user_id]["banner"]["click_url"] = url
        user_data[user_id]["awaiting"] = None
        await message.reply(f"URL set to: {url}")
        await client.send_message(Config.LOG_CHANNEL, f"User {user_id} set banner URL to {url}.")

# Handle file uploads (PDF, ZIP, images, etc.)
@app.on_message(filters.document & filters.private)
async def handle_document(client, message):
    user_id = message.from_user.id
    if not await check_subscription(client, user_id):
        await message.reply("Please join the required channels first! Use /start to check.")
        return

    document = message.document
    file_name = document.file_name
    file_ext = os.path.splitext(file_name)[1].lower()

    if user_id not in user_data:
        user_data[user_id] = {"banner": DEFAULT_BANNER.copy()}

    # Handle banner image upload
    if user_data[user_id].get("awaiting") == "banner_image":
        if file_ext in [".png", ".jpg", ".jpeg"]:
            if time.time() - user_data[user_id].get("banner_upload_time", 0) > 60:
                await message.reply("Upload timed out. Please try again.")
                user_data[user_id]["awaiting"] = None
                return
            banner_path = f"banner_{user_id}{file_ext}"
            await message.download(file_name=banner_path)
            user_data[user_id]["banner"]["image_path"] = banner_path
            user_data[user_id]["awaiting"] = None

            keyboard = [
                [InlineKeyboardButton("Remove Banner", callback_data="remove_banner")],
                [InlineKeyboardButton("Change Banner", callback_data="change_banner")],
                [InlineKeyboardButton("Close", callback_data="close")]
            ]
            await message.reply(
                "Banner image set!", reply_markup=InlineKeyboardMarkup(keyboard)
            )
            await client.send_message(Config.LOG_CHANNEL, f"User {user_id} uploaded a banner image.")
        else:
            await message.reply("Please upload a PNG or JPG image.")
        return

    # Handle ZIP file
    if file_ext == ".zip":
        if user_data[user_id].get("awaiting") == "merge_zip":
            second_zip = f"second_{user_id}.zip"
            await message.download(file_name=second_zip)

            output_zip = f"merged_{user_id}.zip"
            with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as merged:
                for zip_path in [user_data[user_id]["first_zip"], second_zip]:
                    with zipfile.ZipFile(zip_path, "r") as z:
                        for file in z.namelist():
                            merged.write(file, z.read(file))

            await message.reply_document(document=output_zip, filename="merged.zip")
            await client.send_message(Config.LOG_CHANNEL, f"User {user_id} merged two ZIP files.")

            os.remove(user_data[user_id]["first_zip"])
            os.remove(second_zip)
            os.remove(output_zip)
            user_data[user_id]["awaiting"] = None
            return

        zip_path = f"input_{user_id}.zip"
        await message.download(file_name=zip_path)

        keyboard = [
            [InlineKeyboardButton("Zip to PDF", callback_data=f"zip_to_pdf_{zip_path}")],
            [InlineKeyboardButton("Zip to CBZ", callback_data=f"zip_to_cbz_{zip_path}")],
            [InlineKeyboardButton("Unzip", callback_data=f"unzip_{zip_path}")],
            [InlineKeyboardButton("Merge Zip", callback_data=f"merge_zip_{zip_path}")],
            [InlineKeyboardButton("Close", callback_data="close")]
        ]
        await message.reply(
            "Choose an action for the ZIP file:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await client.send_message(Config.LOG_CHANNEL, f"User {user_id} uploaded a ZIP file.")
        return

    # Handle PDF, CBZ, EPUB
    if file_ext in [".pdf", ".cbz", ".epub"]:
        if user_id not in Config.ADMIN:
            await message.reply("File processing is for admins only!")
            return

        input_path = f"input_{user_id}{file_ext}"
        await message.download(file_name=input_path)

        if user_data[user_id]["banner"]["status"]:
            banner_path = user_data[user_id]["banner"]["image_path"] or create_banner_image(user_id)
            output_path = f"output_{user_id}{file_ext}"
            add_banner_to_pdf(input_path, output_path, banner_path, user_data[user_id]["banner"]["position"])
            await message.reply_document(document=output_path, filename=f"modified_{file_name}")
            await client.send_message(Config.LOG_CHANNEL, f"User {user_id} processed a {file_ext} file with banner.")
            os.remove(input_path)
            os.remove(output_path)
            if not user_data[user_id]["banner"]["image_path"]:
                os.remove(banner_path)
        else:
            await message.reply("Banner is disabled. Enable it using /banner.")

if __name__ == "__main__":
    app.run()
