import asyncio
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from motor.motor_asyncio import AsyncIOMotorClient
from config import API_ID, API_HASH, BOT_TOKEN, MONGO_URL, OWNER_ID

# --- Database Setup ---
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["ForwardBotDB"]
settings_col = db["settings"]

# --- Bot Setup ---
app = Client("my_forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- Local State (Temporary memory for setting IDs) ---
# Format: {user_id: "setting_source" or "setting_target"}
user_states = {}

async def get_settings():
    """DB se settings fetch karne ka function"""
    settings = await settings_col.find_one({"_id": "main_settings"})
    if not settings:
        # Default settings
        settings = {"_id": "main_settings", "source": None, "target": None, "active": False}
        await settings_col.insert_one(settings)
    return settings

async def update_setting(key, value):
    """DB me settings update karne ka function"""
    await settings_col.update_one(
        {"_id": "main_settings"},
        {"$set": {key: value}},
        upsert=True
    )

# --- Command: /start ---
@app.on_message(filters.command("start") & filters.user(OWNER_ID))
async def start_command(client, message: Message):
    settings = await get_settings()
    
    status_text = (
        f"👋 **Bot Control Panel**\n\n"
        f"📂 **Source Channel:** `{settings.get('source', 'Not Set')}`\n"
        f"🎯 **Target Channel:** `{settings.get('target', 'Not Set')}`\n"
        f"🚀 **Status:** `{'Running ✅' if settings.get('active') else 'Stopped 🛑'}`"
    )

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔗 Connect Source Channel", callback_data="set_source"),
            InlineKeyboardButton("🔗 Connect Target Channel", callback_data="set_target")
        ],
        [
            InlineKeyboardButton(
                "▶️ Start Forwarding" if not settings.get('active') else "⏸️ Stop Forwarding", 
                callback_data="toggle_forward"
            )
        ]
    ])
    
    await message.reply_text(status_text, reply_markup=buttons)

# --- Callback Queries (Button Clicks) ---
@app.on_callback_query(filters.user(OWNER_ID))
async def handle_callbacks(client, callback: CallbackQuery):
    data = callback.data
    
    if data == "set_source":
        user_states[callback.from_user.id] = "waiting_source"
        await callback.message.edit_text("Send me the **Source Channel ID** (e.g., -100123456789)")
    
    elif data == "set_target":
        user_states[callback.from_user.id] = "waiting_target"
        await callback.message.edit_text("Send me the **Target Channel ID** (e.g., -100987654321)")
        
    elif data == "toggle_forward":
        settings = await get_settings()
        if not settings['source'] or not settings['target']:
            await callback.answer("⚠️ Pehle Source aur Target channels connect karein!", show_alert=True)
            return
            
        new_status = not settings['active']
        await update_setting("active", new_status)
        
        status_msg = "Forwarding Started! 🚀" if new_status else "Forwarding Stopped! 🛑"
        await callback.answer(status_msg)
        
        # Refresh the menu
        await start_command(client, callback.message)

# --- Handle Text Messages (For setting IDs) ---
@app.on_message(filters.text & filters.user(OWNER_ID))
async def handle_inputs(client, message: Message):
    state = user_states.get(message.from_user.id)
    
    if state in ["waiting_source", "waiting_target"]:
        try:
            channel_id = int(message.text)
            if str(channel_id).startswith("-100"): 
                # Valid channel ID basic check
                if state == "waiting_source":
                    await update_setting("source", channel_id)
                    await message.reply_text(f"✅ Source Channel Set to: `{channel_id}`\nDobara /start press karein.")
                else:
                    await update_setting("target", channel_id)
                    await message.reply_text(f"✅ Target Channel Set to: `{channel_id}`\nDobara /start press karein.")
                
                # Clear state
                user_states.pop(message.from_user.id, None)
            else:
                await message.reply_text("❌ Invalid ID format. Channel ID usually starts with -100.")
        except ValueError:
            await message.reply_text("❌ Please send a valid numeric Channel ID.")

# --- MAIN LOGIC: Forwarding ---
@app.on_message(filters.channel)
async def forward_logic(client, message: Message):
    settings = await get_settings()
    
    # Check 1: Kya forwarding ON hai?
    if not settings.get('active'):
        return

    # Check 2: Kya message Source Channel se aaya hai?
    if message.chat.id == settings.get('source'):
        target_id = settings.get('target')
        
        try:
            # Copy method use karenge taki original caption aur file aa jaye
            await message.copy(chat_id=target_id)
        except Exception as e:
            print(f"Error forwarding message: {e}")

# --- Run Bot ---
if __name__ == "__main__":
    print("Bot Starting...")
    app.run()
