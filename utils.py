import hashlib
import random
import string
import time
from datetime import datetime
from config import DICE_MIN, DICE_MAX, NUM_DICE, TAI_MIN, XI_MAX

def generate_seed(length=16):
    """Generate a random seed string."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def generate_md5_hash(seed):
    """Generate an MD5 hash from a seed."""
    # Add a timestamp to make it unique
    seed_with_time = f"{seed}_{time.time()}"
    return hashlib.md5(seed_with_time.encode()).hexdigest()

def extract_dice_values(md5_hash):
    """Extract dice values from an MD5 hash."""
    dice_values = []
    
    # Use different parts of the hash to generate each die
    for i in range(NUM_DICE):
        # Take a 2-character chunk from the hash
        chunk = md5_hash[i*2:(i+1)*2]
        # Convert to an integer and map to dice range
        value = (int(chunk, 16) % (DICE_MAX - DICE_MIN + 1)) + DICE_MIN
        dice_values.append(value)
    
    return dice_values

def determine_result(dice_values):
    """Determine if the result is Tài (High) or Xỉu (Low)."""
    total = sum(dice_values)
    
    if total >= TAI_MIN:
        return "Tài", total  # High
    else:
        return "Xỉu", total  # Low

def format_currency(amount):
    """Format an amount as currency."""
    return f"{amount:,}đ"

def is_valid_bet_amount(amount, balance):
    """Check if a bet amount is valid."""
    from config import MIN_BET, MAX_BET
    
    if not isinstance(amount, int):
        return False
    
    if amount < MIN_BET or amount > MAX_BET:
        return False
    
    if amount > balance:
        return False
    
    return True

def calculate_winnings(bet_amount, bet_type, result):
    """Calculate winnings based on bet and result."""
    if bet_type == result:
        # Win - 2:1 payout (doubled)
        return bet_amount * 2
    else:
        # Loss
        return -bet_amount
