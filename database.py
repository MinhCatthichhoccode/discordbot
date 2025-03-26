import sqlite3
import json
import logging
import threading
from datetime import datetime
from config import DATABASE_PATH, DEFAULT_BALANCE, RESET_BALANCE, HISTORY_SIZE

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Tạo local thread storage để lưu kết nối SQLite
local_storage = threading.local()

class Database:
    def __init__(self):
        """Initialize the database and create tables if they don't exist."""
        self.create_tables()
    
    def get_connection(self):
        """Get a connection to the database - thread-safe version."""
        # Tạo kết nối mới cho mỗi thread nếu chưa có
        if not hasattr(local_storage, 'conn'):
            local_storage.conn = sqlite3.connect(DATABASE_PATH)
            local_storage.conn.row_factory = sqlite3.Row
            logger.debug(f"Created new connection for thread {threading.get_ident()}")
        return local_storage.conn
    
    def create_tables(self):
        """Create the necessary tables if they don't exist."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Players table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            user_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            balance INTEGER DEFAULT 1000000,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Game history table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seed TEXT NOT NULL,
            md5_hash TEXT NOT NULL,
            dice_values TEXT NOT NULL,
            total_value INTEGER NOT NULL,
            result TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Bet history table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bet_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            game_id INTEGER NOT NULL,
            bet_amount INTEGER NOT NULL,
            bet_type TEXT NOT NULL,
            result TEXT NOT NULL,
            win_amount INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES players (user_id),
            FOREIGN KEY (game_id) REFERENCES game_history (id)
        )
        ''')
        
        conn.commit()
        logger.info("Database tables created successfully")
    
    def get_or_create_player(self, user_id, username):
        """Get a player or create if not exists."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
        player = cursor.fetchone()
        
        if player is None:
            cursor.execute(
                "INSERT INTO players (user_id, username, balance) VALUES (?, ?, ?)",
                (user_id, username, DEFAULT_BALANCE)
            )
            conn.commit()
            cursor.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
            player = cursor.fetchone()
            logger.info(f"Created new player: {username} with ID {user_id}")
        
        return dict(player)
    
    def update_player_balance(self, user_id, amount_change):
        """Update a player's balance."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT balance FROM players WHERE user_id = ?", (user_id,))
        player = cursor.fetchone()
        
        if player is None:
            return False
        
        new_balance = player['balance'] + amount_change
        
        # If player runs out of money, reset to RESET_BALANCE
        if new_balance <= 0:
            new_balance = RESET_BALANCE
            logger.info(f"Resetting balance for user {user_id} to {RESET_BALANCE}")
        
        cursor.execute(
            "UPDATE players SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (new_balance, user_id)
        )
        conn.commit()
        
        return new_balance
    
    def get_player_balance(self, user_id):
        """Get a player's current balance."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT balance FROM players WHERE user_id = ?", (user_id,))
        player = cursor.fetchone()
        
        if player is None:
            return None
        
        return player['balance']
    
    def save_game_result(self, seed, md5_hash, dice_values, total_value, result):
        """Save a game result to the database."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        dice_json = json.dumps(dice_values)
        
        cursor.execute(
            "INSERT INTO game_history (seed, md5_hash, dice_values, total_value, result) VALUES (?, ?, ?, ?, ?)",
            (seed, md5_hash, dice_json, total_value, result)
        )
        
        conn.commit()
        return cursor.lastrowid
    
    def save_bet(self, user_id, game_id, bet_amount, bet_type, result, win_amount):
        """Save a bet to the database."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT INTO bet_history 
               (user_id, game_id, bet_amount, bet_type, result, win_amount) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, game_id, bet_amount, bet_type, result, win_amount)
        )
        
        conn.commit()
        return cursor.lastrowid
    
    def get_game_history(self, limit=HISTORY_SIZE):
        """Get recent game history."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM game_history ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        
        history = [dict(row) for row in cursor.fetchall()]
        
        # Convert dice_values from JSON string to list
        for game in history:
            game['dice_values'] = json.loads(game['dice_values'])
        
        return history
    
    def get_player_bet_history(self, user_id, limit=HISTORY_SIZE):
        """Get a player's betting history."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """SELECT bh.*, gh.dice_values, gh.total_value, gh.result as game_result 
               FROM bet_history bh
               JOIN game_history gh ON bh.game_id = gh.id
               WHERE bh.user_id = ?
               ORDER BY bh.created_at DESC LIMIT ?""",
            (user_id, limit)
        )
        
        history = [dict(row) for row in cursor.fetchall()]
        
        # Convert dice_values from JSON string to list
        for bet in history:
            bet['dice_values'] = json.loads(bet['dice_values'])
        
        return history
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
