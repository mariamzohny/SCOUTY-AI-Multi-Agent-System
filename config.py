import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
BASE_DIR = Path(__file__).resolve().parent
(BASE_DIR / "data").mkdir(exist_ok=True)
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8050"))
SQLITE_DB_PATH = BASE_DIR / "data" / "scouty_users.db"
