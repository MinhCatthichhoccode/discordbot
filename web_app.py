import os
import logging
import threading
import time
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from database import Database
from patterns import PatternAnalyzer
from utils import format_currency

# Set up logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create Flask application
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_session_secret")

# Database 
db_handler = Database()

# Pattern analyzer
pattern_analyzer = PatternAnalyzer()

@app.route('/')
def home():
    # Get recent game history
    game_history = db_handler.get_game_history(20)  # Get last 20 games
    
    # Load patterns from history
    results = [game['result'] for game in game_history]
    pattern_analyzer.set_history(results)
    patterns = pattern_analyzer.analyze_patterns()
    
    # Reverse the history to show newest first
    game_history.reverse()
    
    # Stats
    tai_count = len([g for g in game_history if g['result'] == "Tài"])
    xiu_count = len([g for g in game_history if g['result'] == "Xỉu"])
    total_count = len(game_history)
    
    tai_percentage = (tai_count / total_count * 100) if total_count > 0 else 0
    xiu_percentage = (xiu_count / total_count * 100) if total_count > 0 else 0
    
    return render_template('home.html', 
                          game_history=game_history,
                          patterns=patterns,
                          tai_count=tai_count,
                          xiu_count=xiu_count,
                          total_count=total_count,
                          tai_percentage=tai_percentage, 
                          xiu_percentage=xiu_percentage)

@app.route('/players')
def players():
    # Get all players
    conn = db_handler.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM players ORDER BY balance DESC")
    players = [dict(row) for row in cursor.fetchall()]
    
    return render_template('players.html', players=players)

@app.route('/player/<user_id>')
def player_details(user_id):
    # Get player
    conn = db_handler.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
    player_row = cursor.fetchone()
    player = dict(player_row) if player_row else None
    
    if not player:
        flash('Player not found', 'error')
        return redirect(url_for('players'))
    
    # Get player bet history
    bet_history = db_handler.get_player_bet_history(user_id)
    
    # Calculate stats
    win_count = len([b for b in bet_history if b['result'] == 'win'])
    loss_count = len([b for b in bet_history if b['result'] == 'loss'])
    total_bets = win_count + loss_count
    
    win_rate = (win_count / total_bets * 100) if total_bets > 0 else 0
    
    total_win = sum([b['win_amount'] for b in bet_history if b['result'] == 'win'])
    total_loss = sum([abs(b['win_amount']) for b in bet_history if b['result'] == 'loss'])
    
    net_profit = total_win - total_loss
    
    return render_template('player_details.html',
                          player=player,
                          bet_history=bet_history,
                          win_count=win_count,
                          loss_count=loss_count,
                          total_bets=total_bets,
                          win_rate=win_rate,
                          total_win=total_win,
                          total_loss=total_loss,
                          net_profit=net_profit,
                          format_currency=format_currency)

@app.route('/stats')
def stats():
    # Get all games
    conn = db_handler.get_connection()
    cursor = conn.cursor()
    
    # Total games
    cursor.execute("SELECT COUNT(*) as count FROM game_history")
    total_games = cursor.fetchone()['count']
    
    # Tài vs Xỉu distribution
    cursor.execute("SELECT result, COUNT(*) as count FROM game_history GROUP BY result")
    result_distribution = {row['result']: row['count'] for row in cursor.fetchall()}
    
    # Dice value distribution
    cursor.execute("SELECT dice_values FROM game_history")
    all_dice = cursor.fetchall()
    
    dice_distribution = {i: 0 for i in range(1, 7)}
    for game in all_dice:
        dice_list = json.loads(game['dice_values'])
        for die in dice_list:
            dice_distribution[die] = dice_distribution.get(die, 0) + 1
    
    # Total value distribution
    cursor.execute("SELECT total_value, COUNT(*) as count FROM game_history GROUP BY total_value ORDER BY total_value")
    total_distribution = {row['total_value']: row['count'] for row in cursor.fetchall()}
    
    # Recent pattern occurrence
    game_history = db_handler.get_game_history(50)
    results = [game['result'] for game in game_history]
    
    pattern_analyzer.set_history(results)
    patterns = pattern_analyzer.analyze_patterns()
    
    return render_template('stats.html',
                          total_games=total_games,
                          result_distribution=result_distribution,
                          dice_distribution=dice_distribution,
                          total_distribution=total_distribution,
                          patterns=patterns)

@app.route('/api/game_history')
def api_game_history():
    limit = request.args.get('limit', 50, type=int)
    game_history = db_handler.get_game_history(limit)
    return jsonify(game_history)

@app.route('/api/patterns')
def api_patterns():
    game_history = db_handler.get_game_history(50)
    results = [game['result'] for game in game_history]
    
    pattern_analyzer.set_history(results)
    patterns = pattern_analyzer.analyze_patterns()
    
    return jsonify(patterns)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404