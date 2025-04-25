# plugins/start_&_cb.py
import random
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply, CallbackQuery
from helper.database import add_autho_user, is_autho_user_exist
from config import Config, Txt

async def check_subscription(client: Client, user_id: int, channel: str) -> bool:
    """Check if a user is subscribed to a channel."""
    try:
        member = await client.get_chat_member(channel, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False

@Client.on_message(filters.private & filters.command("start"))
async def start(client, message):
    user = message.from_user

    # Check force subscriptions
    sub_1 = await check_subscription(client, user.id, f"@{Config.FORCE_SUB_1}")
    sub_2 = await check_subscription(client, user.id, f"@{Config.FORCE_SUB_2}")

    if not (sub_1 and sub_2):
        buttons = []
        if not sub_1:
            buttons.append([InlineKeyboardButton(f"Join {Config.FORCE_SUB_1}", url=f"https://t.me/{Config.FORCE_SUB_1}")])
        if not sub_2:
            buttons.append([InlineKeyboardButton(f"Join {Config.FORCE_SUB_2}", url=f"https://t.me/{Config.FORCE_SUB_2}")])
        buttons.append([InlineKeyboardButton("✅ I Joined", callback_data="check_sub")])

        await message.reply_photo(
            photo=Config.START_PIC,
            caption="To use this bot, please join the required channels below:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="html"
        )
        return

    # Add user to database
    await add_autho_user(user.id, user.username, user.first_name, user.last_name)

    # Authorized user check
    is_autho = await is_autho_user_exist(user.id)
    autho_text = "You are an authorized user! 🎉" if is_autho else f"Contact {Config.SUPPORT_CHAT} to get authorized."

    button = InlineKeyboardMarkup([
        [InlineKeyboardButton("Hᴏᴡ ᴛᴏ Usᴇ", callback_data='help')],
        [
            InlineKeyboardButton('Uᴩᴅᴀᴛᴇꜱ', url=f"https://t.me/i_killed_my_clan"),
            InlineKeyboardButton('Sᴜᴩᴩᴏʀᴛ', url='https://t.me/ahss_help_zone')
        ],
        [
            InlineKeyboardButton('Aʙᴏᴜᴛ', callback_data='about'),
            InlineKeyboardButton('Dᴏɴᴀᴛᴇ', callback_data='donate')
        ]
    ])

    await message.reply_photo(
        photo=Config.START_PIC,
        caption=Txt.START_TXT.format(user.mention, autho_text),
        reply_markup=button,
        parse_mode="html"
    )

@Client.on_callback_query()
async def cb_handler(client, query: CallbackQuery):
    data = query.data
    user = query.from_user

    if data == "check_sub":
        sub_1 = await check_subscription(client, user.id, f"@{Config.FORCE_SUB_1}")
        sub_2 = await check_subscription(client, user.id, f"@{Config.FORCE_SUB_2}")

        if sub_1 and sub_2:
            await query.message.delete()
            is_autho = await is_autho_user_exist(user.id)
            autho_text = "You are an authorized user! 🎉" if is_autho else f"Contact {Config.SUPPORT_CHAT} to get authorized."
            button = InlineKeyboardMarkup([
                [InlineKeyboardButton("Hᴏᴡ ᴛᴏ Usᴇ", callback_data='help')],
                [
                    InlineKeyboardButton('Uᴩᴅᴀᴛᴇꜱ', url=f"https://t.me/i_killed_my_clan"),
                    InlineKeyboardButton('Sᴜᴩᴩᴏʀᴛ', url='https://t.me/ahss_help_zone')
                ],
                [
                    InlineKeyboardButton('Aʙᴏᴜᴛ', callback_data='about'),
                    InlineKeyboardButton('Dᴏɴᴀᴛᴇ', callback_data='donate')
                ]
            ])
            await query.message.reply_photo(
                photo=Config.START_PIC,
                caption=Txt.START_TXT.format(user.mention, autho_text),
                reply_markup=button,
                parse_mode="html"
            )
        else:
            await query.answer("Please join all required channels!", show_alert=True)

    elif data == "start":
        await query.message.edit_text(
            text=Txt.START_TXT.format(user.mention, f"Contact {Config.SUPPORT_CHAT} to get authorized."),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Hᴏᴡ ᴛᴏ Usᴇ", callback_data='help')],
                [
                    InlineKeyboardButton('Uᴩᴅᴀᴛᴇꜱ', url=f"https://t.me/i_killed_my_clan"),
                    InlineKeyboardButton('Sᴜᴩᴩᴏʀᴛ', url='https://t.me/ahss_help_zone')
                ],
                [
                    InlineKeyboardButton('Aʙᴏᴜᴛ', callback_data='about'),
                    InlineKeyboardButton('Dᴏɴᴀᴛᴇ', callback_data='donate')
                ]
            ])
        )

    elif data == "donate":
        await query.message.edit_text(
            text=Txt.DONATE_TXT.format(user.mention),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Cʟᴏꜱᴇ", callback_data="close"),
                 InlineKeyboardButton("Bᴀᴄᴋ", callback_data="start")]
            ])
        )

    elif data == "help":
        await query.message.edit_text(
            text=Txt.HELP_TXT.format(client.mention),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Metadata", callback_data="metainfo")],
                [
                    InlineKeyboardButton("Captions", callback_data="caption"),
                    InlineKeyboardButton("Thumbnails", callback_data="thumbnail")
                ],
                [InlineKeyboardButton("Suffix & Prefix", callback_data="suffix_prefix")],
                [
                    InlineKeyboardButton("Cʟᴏꜱᴇ", callback_data="close"),
                    InlineKeyboardButton("Bᴀᴄᴋ", callback_data="start")
                ]
            ])
        )

    elif data == "about":
        await query.message.edit_text(
            text=Txt.ABOUT_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Cʟᴏꜱᴇ", callback_data="close"),
                 InlineKeyboardButton("Bᴀᴄᴋ", callback_data="start")]
            ])
        )

    elif data == "caption":
        await query.message.edit_text(
            text="""<b><u>ᴛᴏ ꜱᴇᴛ ᴄᴜꜱᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ ᴀɴᴅ ᴍᴇᴅɪᴀ ᴛʏᴘᴇ</u></b>
**ᴠᴀʀɪᴀʙʟᴇꜱ :**         
ꜱɪᴢᴇ: {ꜰɪʟᴇꜱɪᴢᴇ}
ᴅᴜʀᴀᴛɪᴏɴ: {duration}
ꜰɪʟᴇɴᴀᴍᴇ: {ꜰɪʟᴇɴᴀᴍᴇ}
**➜ /set_caption:** ᴛᴏ ꜱᴇᴛ ᴀ ᴄᴜꜱᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ.
**➜ /see_caption:** ᴛᴏ ᴠɪᴇᴡ ʏᴏᴜʀ ᴄᴜꜱᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ.
**➜ /del_caption:** ᴛᴏ ᴅᴇʟᴇᴛᴇ ʏᴏᴜʀ ᴄᴜꜱᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ.

**ᴇxᴀᴍᴘʟᴇ: /set_caption** ꜰɪʟᴇ ɴᴀᴍᴇ: {ꜰɪʟᴇɴᴀᴍᴇ}
            """,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Hᴏᴍᴇ", callback_data="start"),
                 InlineKeyboardButton("Bᴀᴄᴋ", callback_data="help")]
            ])
        )

    elif data == "thumbnail":
        await query.message.edit_text(
            text="""<b>ᴛᴏ ꜱᴇᴛ ᴄᴜꜱᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ</b>

**➜ /set_thumb:** ꜱᴇɴᴅ ᴀɴʏ ᴘʜᴏᴛᴏ ᴛᴏ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ꜱᴇᴛ ɪᴛ ᴀꜱ ᴀ ᴛʜᴜᴍʙɴᴀɪʟ.
**➜ /del_thumb:** ᴜꜱᴇ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ᴛᴏ ᴅᴇʟᴇᴛᴇ ʏᴏᴜʀ ᴏʟᴅ ᴛʜᴜᴍʙɴᴀɪʟ.
**➜ /see_thumb:** ᴜꜱᴇ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ᴛᴏ ᴠɪᴇᴡ ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴛʜᴜᴍʙɴᴀɪʟ.

ɴᴏᴛᴇ: ɪꜰ ɴᴏ ᴛʜᴜᴍʙɴᴀɪʟ ꜱᴀᴠᴇᴅ ɪɴ ʙᴏᴛ ᴛʜᴇɴ, ɪᴛ ᴡɪʟʟ ᴜꜱᴇ ᴛʜᴜᴍʙɴᴀɪʟ ᴏꜰ ᴛʜᴇ ᴏʀɪɢɪɴᴀʟ ꜰɪʟᴇ ᴛᴏ ꜱᴇᴛ ɪɴ ʀᴇɴᴀᴍᴇᴅ ꜰɪʟᴇ
            """,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Hᴏᴍᴇ", callback_data="start"),
                 InlineKeyboardButton("Bᴀᴄᴋ", callback_data="help")]
            ])
        )

    elif data == "suffix_prefix":
        await query.message.edit_text(
            text="""<b>ᴛᴏ ꜱᴇᴛ ᴄᴜꜱᴛᴏᴍ ꜱᴜғғɪx & ᴘʀᴇғɪx</b>

**➜ /set_prefix:** ᴛᴏ ꜱᴇᴛ ᴀ ᴄᴜꜱᴛᴏᴍ ᴘʀᴇғɪx.
**➜ /del_prefix:** ᴛᴏ ᴅᴇʟᴇᴛᴇ ʏᴏᴜʀ ᴄᴜꜱᴛᴏᴍ ᴘʀᴇғɪx.
**➜ /see_prefix:** ᴛᴏ ᴠɪᴇᴡ ʏᴏᴜʀ ᴄᴜꜱᴛᴏᴍ ᴘʀᴇғɪx.

**➜ /set_suffix:** ᴛᴏ ꜱᴇᴛ ᴀ ᴄᴜꜱᴛᴏᴍ ꜱᴜғғɪx.
**➜ /del_suffix:** ᴛᴏ ᴅᴇʟᴇᴛᴇ ʏᴏᴜʀ ᴄᴜꜱᴛᴏᴍ ꜱᴜғғɪx.
**➜ /see_suffix:** ᴛᴏ ᴠɪᴇᴡ ʏᴏᴜʀ ᴄᴜꜱᴛᴏᴍ ꜱᴜғғɪx.

ᴇxᴀᴍᴘʟᴇ: /set_prefix [AS] | /set_suffix [Animesociety]
            """,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Hᴏᴍᴇ", callback_data="start"),
                 InlineKeyboardButton("Bᴀᴄᴋ", callback_data="help")]
            ])
        )

    elif data == "metainfo":
        await query.message.edit_text(
            text="""<b>ᴛᴏ ꜱᴇᴛ ᴍᴇᴛᴀᴅᴀᴛᴀ</b>

**➜ /banner:** ᴛᴏ ᴄᴏɴꜰɪɢᴜʀᴇ ʙᴀɴɴᴇʀ ꜱᴇᴛᴛɪɴɢꜱ ꜰᴏʀ ᴘᴅꜰꜱ/ᴄʙᴢ/ᴇᴘᴜʙ.
**➜ /addautho_user:** ᴛᴏ ᴀᴅᴅ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜꜱᴇʀꜱ (ᴀᴅᴍɪɴ ᴏɴʟʏ).
**➜ /delautho_user:** ᴛᴏ ʀᴇᴍᴏᴠᴇ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜꜱᴇʀꜱ (ᴀᴅᴍɪɴ ᴏɴʟʏ).
**➜ /autho_users:** ᴛᴏ ʟɪꜱᴛ ᴀʟʟ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜꜱᴇʀꜱ (ᴀᴅᴍɪɴ ᴏɴʟʏ).
**➜ /check_autho:** ᴛᴏ ᴄʜᴇᴄᴋ ɪꜰ ʏᴏᴜ ᴀʀᴇ ᴀɴ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜꜱᴇʀ.

ɴᴏᴛᴇ: ᴏɴʟʏ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜꜱᴇʀꜱ ᴄᴀɴ ᴜꜱᴇ ʙᴀɴɴᴇʀ ᴀɴᴅ ᴢɪᴘ ᴄᴏɴᴠᴇʀꜱɪᴏɴ ꜰᴇᴀᴛᴜʀᴇꜱ.
            """,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Hᴏᴍᴇ", callback_data="start"),
                 InlineKeyboardButton("Bᴀᴄᴋ", callback_data="help")]
            ])
        )

    elif data == "close":
        try:
            await query.message.delete()
            await query.message.reply_to_message.delete()
        except:
            await query.message.delete()
