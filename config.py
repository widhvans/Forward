import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "38364162")) # Apna API ID daalein
API_HASH = os.getenv("API_HASH", "6802312a466d3b34133ebd5de3374524") # Apna API Hash daalein
BOT_TOKEN = os.getenv("BOT_TOKEN", "8368477494:AAEX-ndxDVt9F_EyfMCQc8tAQNObH-TH51Y") # Bot Father se mila token
MONGO_DB_URI = os.getenv("MONGO_DB_URI", "mongodb+srv://soniji:chaloji@cluster0.i5zy74f.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0") # MongoDB URL
OWNER_ID = int(os.getenv("OWNER_ID", "8303569508")) # Aapki khud ki Telegram ID (admin control ke liye)
