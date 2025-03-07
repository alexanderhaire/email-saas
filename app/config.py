import os
from dotenv import load_dotenv

load_dotenv()

IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
EMAIL_POLL_INTERVAL = int(os.getenv("EMAIL_POLL_INTERVAL", "300"))  # seconds between polls
TRAIN_EPOCHS = int(os.getenv("TRAIN_EPOCHS", "3"))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./emails.db")
MODEL_STORAGE_DIR = os.getenv("MODEL_STORAGE_DIR", "./models")
