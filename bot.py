import asyncio
import os
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from motor.motor_asyncio import AsyncIOMotorClient
from config import API_ID, API_HASH, BOT_TOKEN, MONGO_DB_URI, OWNER_ID

# --- Database Setup (MongoDB) ---
mongo_client = AsyncIOMotorClient(MONGO_DB_URI)
db = mongo_client["ForwardBotDB"]
settings_col = db["settings"]

async def get_settings():
    settings = await settings_col.find_one({"_id": "config"})
    if not settings:
        new_settings = {
            "_id": "config",
            "source_id": None,
            "target_ids": [],
            "is_running": False,
            "waiting_for": None
        }
        try:
            await settings_col.insert_one(new_settings)
        except:
            pass
        return new_settings
    return settings

async def update_setting(key, value):
    await settings_col.update_one({"_id": "config"}, {"$set": {key: value}})

async def add_target(chat_id):
    await settings_col.update_one({"_id": "config"}, {"$addToSet": {"target_ids": chat_id}})

# --- Bot Client Setup ---
app = Client("forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- Web Server for Health Check (KOYEB FIX) ---
async def health_check(request):
    return web.Response(text="Bot is Running Properly!")

async def start_web_server():
    server = web.Application()
    server.add_routes([web.get('/', health_check)])
    runner = web.AppRunner(server)
    await runner.setup()
    # Koyeb Port 8000 par expect karta hai
    port = int(os.environ.get("PORT", 8000)) 
    await web.TCPSite(runner, "0.0.0.0", port).start()
    print(f"Web Server Started on Port {port}")

# --- Keyboards & Logic ---
def main_menu_keyboard(is_running):
    status_text = "✅ Running" if is_running else "🛑 Stopped"
    start_btn_text = "Stop Bot 🛑" if is_running else "Start Bot 🟢"
    
    buttons = [
        [InlineKeyboardButton("📝 Set Source Channel", callback_data="set_source")],
        [InlineKeyboardButton("🎯 Add Target Channel", callback_data="add_target")],
        [InlineKeyboardButton(start_btn_text, callback_data="toggle_start")]
    ]
    return InlineKeyboardMarkup(buttons)

@app.on_message(filters.command("start") & filters.private & filters.user(OWNER_ID))
async def start_command(client, message: Message):
    settings = await get_settings()
    text = (
        f"**🤖 Auto Forwarding Bot Manager**\n\n"
        f"**Status:** {'Active ✅' if settings['is_running'] else 'Inactive 🛑'}\n"
        f"**Source Channel:** `{settings['source_id']}`\n"
        f"**Targets:** `{len(settings['target_ids'])} channels`\n"
    )
    await message.reply_text(text, reply_markup=main_menu_keyboard(settings['is_running']))

@app.on_callback_query(filters.user(OWNER_ID))
async def handle_callbacks(client, callback: CallbackQuery):
    data = callback.data
    settings = await get_settings()

    if data == "set_source":
        await update_setting("waiting_for", "source")
        await callback.message.edit_text(
            "Target ID bhejein (Source Channel ID):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="cancel_input")]])
        )

    elif data == "add_target":
        await update_setting("waiting_for", "target")
        await callback.message.edit_text(
            "Target Channel ID bhejein:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="cancel_input")]])
        )

    elif data == "toggle_start":
        new_state = not settings['is_running']
        await update_setting("is_running", new_state)
        await start_command(client, callback.message)

    elif data == "cancel_input":
        await update_setting("waiting_for", None)
        await start_command(client, callback.message)

@app.on_message(filters.private & filters.user(OWNER_ID) & filters.text)
async def handle_input(client, message: Message):
    settings = await get_settings()
    waiting_for = settings.get("waiting_for")
    if not waiting_for: return

    try:
        chat_id = int(message.text)
        if waiting_for == "source":
            await update_setting("source_id", chat_id)
            await message.reply(f"Source Set: {chat_id}")
        elif waiting_for == "target":
            await add_target(chat_id)
            await message.reply(f"Target Added: {chat_id}")
        await update_setting("waiting_for", None)
    except:
        await message.reply("Invalid ID")

@app.on_message(filters.channel)
async def forward_messages(client, message: Message):
    settings = await get_settings()
    if not settings['is_running'] or message.chat.id != settings['source_id']:
        return

    for target_id in settings.get("target_ids", []):
        try:
            await message.copy(target_id)
        except Exception as e:
            print(f"Failed to send to {target_id}: {e}")

# --- Main Start Logic ---
async def main():
    # Pehle Web Server Start karein (Health Check ke liye)
    await start_web_server()
    
    # Phir Bot Start karein
    print("Bot Starting...")
    await app.start()
    print("Bot Started & Running!")
    await idle() # Bot ko roke rakhne ke liye
    await app.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    
