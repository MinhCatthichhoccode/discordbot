import os

# Bot configuration
TOKEN = os.getenv("DISCORD_BOT_TOKEN", "your_discord_bot_token")
DEFAULT_BALANCE = 1000000  # 1 million
MIN_BET = 10000  # 10k
MAX_BET = 1000000  # 1 million
RESET_BALANCE = 1000000  # Amount to reset to when player runs out
BETTING_WINDOW = 40  # 40 seconds
HISTORY_SIZE = 50  # Show 50 most recent results

# Game constants
TAI_MIN = 11  # Minimum value for "Tài" (High)
XI_MAX = 10   # Maximum value for "Xỉu" (Low)
DICE_MIN = 1  # Minimum value on a die
DICE_MAX = 6  # Maximum value on a die
NUM_DICE = 3  # Number of dice to roll

# Database
DATABASE_PATH = "tai_xiu.db"
