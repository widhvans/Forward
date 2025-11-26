import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from motor.motor_asyncio import AsyncIOMotorClient
from config import API_ID, API_HASH, BOT_TOKEN, MONGO_DB_URI, OWNER_ID

# --- Database Setup (MongoDB) ---
mongo_client = AsyncIOMotorClient(MONGO_DB_URI)
db = mongo_client["ForwardBotDB"]
settings_col = db["settings"]

# Default Settings create karne ke liye
async def get_settings():
    settings = await settings_col.find_one({"_id": "config"})
    if not settings:
        new_settings = {
            "_id": "config",
            "source_id": None,
            "target_ids": [],
            "is_running": False,
            "waiting_for": None  # 'source' ya 'target' input lene ke liye state
        }
        await settings_col.insert_one(new_settings)
        return new_settings
    return settings

async def update_setting(key, value):
    await settings_col.update_one({"_id": "config"}, {"$set": {key: value}})

async def add_target(chat_id):
    await settings_col.update_one({"_id": "config"}, {"$addToSet": {"target_ids": chat_id}})

# --- Bot Client Setup ---
app = Client("forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- Keyboards ---
def main_menu_keyboard(is_running):
    status_text = "✅ Running" if is_running else "🛑 Stopped"
    start_btn_text = "Stop Bot 🛑" if is_running else "Start Bot 🟢"
    
    buttons = [
        [InlineKeyboardButton("📝 Set Source Channel", callback_data="set_source")],
        [InlineKeyboardButton("🎯 Add Target Channel", callback_data="add_target")],
        [InlineKeyboardButton(start_btn_text, callback_data="toggle_start")]
    ]
    return InlineKeyboardMarkup(buttons)

# --- Commands & Handlers ---

@app.on_message(filters.command("start") & filters.private & filters.user(OWNER_ID))
async def start_command(client, message: Message):
    settings = await get_settings()
    text = (
        f"**🤖 Auto Forwarding Bot Manager**\n\n"
        f"**Status:** {'Active ✅' if settings['is_running'] else 'Inactive 🛑'}\n"
        f"**Source Channel:** `{settings['source_id']}`\n"
        f"**Targets:** `{len(settings['target_ids'])} channels`\n\n"
        "Niche diye gaye buttons se bot configure karein:"
    )
    await message.reply_text(text, reply_markup=main_menu_keyboard(settings['is_running']))

# --- Button Callbacks ---

@app.on_callback_query(filters.user(OWNER_ID))
async def handle_callbacks(client, callback: CallbackQuery):
    data = callback.data
    settings = await get_settings()

    if data == "set_source":
        await update_setting("waiting_for", "source")
        await callback.message.edit_text(
            "**Setting Source Channel:**\n\n"
            "Kripya Source Channel ki **Channel ID** bhejein (e.g., -100123456789).\n"
            "Make sure bot wahan Admin ho.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="cancel_input")]])
        )

    elif data == "add_target":
        await update_setting("waiting_for", "target")
        await callback.message.edit_text(
            "**Adding Target Channel:**\n\n"
            "Kripya Target Channel ki **Channel ID** bhejein.\n"
            "Bot wahan Admin hona chahiye.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="cancel_input")]])
        )

    elif data == "toggle_start":
        # Toggle Running State
        new_state = not settings['is_running']
        await update_setting("is_running", new_state)
        
        status_msg = "Bot ab **START** ho gaya hai! ✅" if new_state else "Bot ab **STOP** ho gaya hai. 🛑"
        await callback.answer(status_msg, show_alert=True)
        
        # UI Refresh
        await start_command(client, callback.message)

    elif data == "cancel_input":
        await update_setting("waiting_for", None)
        await start_command(client, callback.message)

# --- Input Listener (For IDs) ---

@app.on_message(filters.private & filters.user(OWNER_ID) & filters.text)
async def handle_input(client, message: Message):
    settings = await get_settings()
    waiting_for = settings.get("waiting_for")

    if not waiting_for:
        return # Agar bot kuch wait nahi kar raha, toh ignore karein

    try:
        chat_id = int(message.text)
        if not str(chat_id).startswith("-100"):
            await message.reply("⚠️ Error: Channel ID `-100` se start honi chahiye.")
            return

        if waiting_for == "source":
            await update_setting("source_id", chat_id)
            await message.reply(f"✅ **Source Channel Set:** `{chat_id}`")
        
        elif waiting_for == "target":
            await add_target(chat_id)
            await message.reply(f"✅ **Target Added:** `{chat_id}`")

        # Reset waiting state
        await update_setting("waiting_for", None)
        await start_command(client, message)

    except ValueError:
        await message.reply("⚠️ Error: Valid numeric Chat ID bhejein.")

# --- The Forwarder Logic ---

@app.on_message(filters.channel)
async def forward_messages(client, message: Message):
    settings = await get_settings()
    
    # Check 1: Kya bot ON hai?
    if not settings['is_running']:
        return

    # Check 2: Kya message Source Channel se aaya hai?
    if message.chat.id != settings['source_id']:
        return

    # Forwarding Loop
    targets = settings.get("target_ids", [])
    if not targets:
        return

    for target_id in targets:
        try:
            # copy() use kar rahe hain taaki 'Forwarded from' tag na aaye (cleaner look)
            # Agar 'Forwarded from' chahiye to message.forward(target_id) use karein
            await message.copy(target_id)
        except Exception as e:
            print(f"Failed to send to {target_id}: {e}")

# --- Run App ---
print("Bot Started...")
app.run()
