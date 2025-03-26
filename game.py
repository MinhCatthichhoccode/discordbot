import asyncio
import discord
import random
import time
import logging
from datetime import datetime, timedelta
from discord import app_commands, Embed, Color

from config import (
    BETTING_WINDOW, MIN_BET, MAX_BET, DEFAULT_BALANCE, 
    TAI_MIN, XI_MAX, RESET_BALANCE, HISTORY_SIZE
)
from database import Database
from utils import (
    generate_seed, generate_md5_hash, extract_dice_values, 
    determine_result, format_currency, is_valid_bet_amount, 
    calculate_winnings
)
from patterns import PatternAnalyzer

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TaiXiuGame:
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.active_sessions = {}
        self.session_count = 0
        self.pattern_analyzer = PatternAnalyzer()
        
        # Load game history for pattern analysis
        self._load_history()
    
    def _load_history(self):
        """Load game history for pattern analysis."""
        history = self.db.get_game_history()
        results = [game['result'] for game in history]
        self.pattern_analyzer.set_history(results)
        logger.info(f"Loaded {len(results)} game results for pattern analysis")
    
    async def start_session(self, interaction):
        """Start a new Tài Xỉu game session."""
        # Create a unique session ID
        self.session_count += 1
        session_id = f"session_{self.session_count}_{int(time.time())}"
        
        # Create a new session
        session = {
            "id": session_id,
            "channel_id": interaction.channel_id,
            "start_time": datetime.now(),
            "end_time": datetime.now() + timedelta(seconds=BETTING_WINDOW),
            "bets": {},  # {user_id: {"amount": amount, "type": "Tài/Xỉu"}}
            "result": None,
            "dice_values": None,
            "total": None,
            "message": None
        }
        
        # Store the session
        self.active_sessions[session_id] = session
        
        # Send initial message
        embed = self._create_session_embed(session)
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        session["message"] = message
        
        # Schedule updates
        self.bot.loop.create_task(self._update_session(session_id))
        
        logger.info(f"Started session {session_id} in channel {interaction.channel_id}")
        
        return session_id
    
    async def _update_session(self, session_id):
        """Update a session message and end it when time runs out."""
        session = self.active_sessions.get(session_id)
        if not session:
            return
        
        try:
            # Cập nhật tin nhắn thường xuyên hơn để hiển thị thời gian chính xác
            update_times = [
                BETTING_WINDOW - 5, BETTING_WINDOW - 10, BETTING_WINDOW - 15, 
                BETTING_WINDOW - 20, BETTING_WINDOW - 25, BETTING_WINDOW - 30, 
                BETTING_WINDOW - 35
            ]
            
            # Thêm cảnh báo khi gần hết thời gian
            time_warnings = {
                10: "⚠️ **Chỉ còn 10 giây để đặt cược!**",
                5: "⚠️ **Chỉ còn 5 giây cuối! Nhanh lên!**"
            }
            
            await asyncio.sleep(1)  # Đợi một chút để đảm bảo tin nhắn đã được gửi
            
            # Cập nhật thời gian còn lại
            now = datetime.now()
            session_time_left = int((session["end_time"] - now).total_seconds())
            
            while session_time_left > 0:
                # Cập nhật tin nhắn thường xuyên hơn khi gần đến thời hạn
                if session_time_left in time_warnings:
                    session["warning_message"] = time_warnings[session_time_left]
                
                if session_time_left in update_times or session_time_left <= 10:
                    embed = self._create_session_embed(session)
                    await session["message"].edit(embed=embed)
                
                # Đợi 1 giây và cập nhật thời gian còn lại
                await asyncio.sleep(1)
                now = datetime.now()
                new_time_left = int((session["end_time"] - now).total_seconds())
                
                # Nếu thời gian đã thay đổi, cập nhật giá trị
                if new_time_left != session_time_left:
                    session_time_left = new_time_left
            
            # Wait until the betting window ends
            now = datetime.now()
            session_time_left = (session["end_time"] - now).total_seconds()
            
            if session_time_left > 0:
                await asyncio.sleep(session_time_left)
            
            # End the session
            await self._end_session(session_id)
            
        except Exception as e:
            logger.error(f"Error updating session {session_id}: {e}")
            # Try to end the session anyway
            await self._end_session(session_id)
    
    async def _end_session(self, session_id):
        """End a game session and determine results."""
        session = self.active_sessions.get(session_id)
        if not session:
            return
        
        try:
            # Generate result
            seed = generate_seed()
            md5_hash = generate_md5_hash(seed)
            dice_values = extract_dice_values(md5_hash)
            result, total = determine_result(dice_values)
            
            # Update session
            session["result"] = result
            session["dice_values"] = dice_values
            session["total"] = total
            
            # Save game result to database
            game_id = self.db.save_game_result(seed, md5_hash, dice_values, total, result)
            
            # Process bets
            winners = []
            losers = []
            
            for user_id, bet_info in session["bets"].items():
                bet_amount = bet_info["amount"]
                bet_type = bet_info["type"]
                username = bet_info["username"]
                
                # Calculate winnings
                winnings = calculate_winnings(bet_amount, bet_type, result)
                
                # Update user balance
                new_balance = self.db.update_player_balance(user_id, winnings)
                
                # Save bet to database
                win_or_loss = "win" if winnings > 0 else "loss"
                self.db.save_bet(user_id, game_id, bet_amount, bet_type, win_or_loss, winnings)
                
                # Add to winners or losers list
                bet_result = {
                    "user_id": user_id,
                    "username": username,
                    "bet_amount": bet_amount,
                    "bet_type": bet_type,
                    "winnings": winnings,
                    "new_balance": new_balance
                }
                
                if winnings > 0:
                    winners.append(bet_result)
                else:
                    losers.append(bet_result)
            
            # Update pattern analyzer
            self.pattern_analyzer.append_result(result)
            
            # Send results
            embed = self._create_result_embed(session, winners, losers)
            try:
                if session["message"]:
                    await session["message"].edit(embed=embed)
            except Exception as e:
                logger.error(f"Error updating result embed: {str(e)}")
                # Try to send a new message instead if edit fails
                try:
                    channel = self.bot.get_channel(session["channel_id"])
                    if channel:
                        await channel.send(embed=embed)
                except Exception as inner_e:
                    logger.error(f"Error sending result message: {str(inner_e)}")
            
            # Remove session
            del self.active_sessions[session_id]
            
            logger.info(f"Ended session {session_id} with result {result} (total: {total})")
            
            # Start a new session automatically after a short delay
            channel = self.bot.get_channel(session["channel_id"])
            if channel:
                await asyncio.sleep(5)  # Wait a bit before starting a new session
                
                # Create a new interaction-like object for the start_session method
                class DummyInteraction:
                    def __init__(self, channel_id):
                        self.channel_id = channel_id
                    
                    async def response(self):
                        pass
                    
                    async def original_response(self):
                        pass
                
                try:
                    # Cách mới: tạo trực tiếp một channel message thay vì dùng dummy interaction
                    # Tạo message phiên mới và bắt đầu phiên
                    embed = discord.Embed(
                        title="🎲 Tài Xỉu - Phiên mới đã bắt đầu! 🎲",
                        description="Đang chuẩn bị phiên mới...",
                        color=discord.Color.gold()
                    )
                    # Gửi message trực tiếp vào channel
                    new_message = await channel.send(embed=embed)
                    
                    # Tạo phiên mới trực tiếp thay vì dùng start_session
                    session_id = f"session_{len(self.active_sessions) + 1}_{int(time.time())}"
                    end_time = datetime.now() + timedelta(seconds=BETTING_WINDOW)
                    
                    # Tạo phiên mới
                    self.active_sessions[session_id] = {
                        "channel_id": session["channel_id"],
                        "message": new_message,
                        "end_time": end_time,
                        "bets": {},
                        "seed": None,
                        "md5_hash": None
                    }
                    
                    # Update embed 
                    embed = self._create_session_embed(self.active_sessions[session_id])
                    await new_message.edit(embed=embed)
                    
                    # Đặt lịch cập nhật và kết thúc phiên
                    asyncio.create_task(self._update_session(session_id))
                    
                    logger.info(f"Started session {session_id} in channel {session['channel_id']}")
                except Exception as e:
                    logger.error(f"Error starting new session after previous one: {str(e)}")
                
                # Phiên mới đã được bắt đầu trực tiếp ở bước trước, không cần làm gì thêm
                
        except Exception as e:
            logger.error(f"Error ending session {session_id}: {e}")
            # Try to remove the session anyway
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
    
    async def place_bet(self, interaction, amount, bet_type):
        """Place a bet in the active session for the current channel."""
        channel_id = interaction.channel_id
        user_id = str(interaction.user.id)
        username = interaction.user.name
        
        # Find active session for this channel
        active_session = None
        for session_id, session in self.active_sessions.items():
            if session["channel_id"] == channel_id:
                active_session = session
                break
        
        if not active_session:
            await interaction.followup.send(
                "Không có phiên tài xỉu nào đang hoạt động trong kênh này. Hãy bắt đầu phiên mới với /tai_xiu.",
                ephemeral=True
            )
            return False
        
        # Check if betting window is still open
        now = datetime.now()
        if now >= active_session["end_time"]:
            # Tính thời gian cho phiên tiếp theo
            time_until_next = 5  # Đợi 5 giây sau khi kết thúc phiên hiện tại
            
            await interaction.followup.send(
                f"⏱️ **Quá thời gian đặt cược cho phiên này.** ⏱️\n"
                f"Kết quả đang được xác định, phiên mới sẽ bắt đầu sau đó.\n"
                f"Vui lòng đợi khoảng {time_until_next} giây để đặt cược vào phiên tiếp theo.",
                ephemeral=True
            )
            return False
        
        # Get or create player
        player = self.db.get_or_create_player(user_id, username)
        current_balance = player["balance"]
        
        # Validate bet amount
        if not is_valid_bet_amount(amount, current_balance):
            await interaction.followup.send(
                f"Số tiền cược không hợp lệ. Cược tối thiểu là {format_currency(MIN_BET)}, "
                f"tối đa là {format_currency(MAX_BET)}, và không vượt quá số dư hiện tại của bạn ({format_currency(current_balance)}).",
                ephemeral=True
            )
            return False
        
        # Validate bet type
        if bet_type not in ["Tài", "Xỉu"]:
            await interaction.followup.send(
                "Loại cược không hợp lệ. Vui lòng chọn 'Tài' hoặc 'Xỉu'.",
                ephemeral=True
            )
            return False
        
        # Update or create bet
        if user_id in active_session["bets"]:
            old_amount = active_session["bets"][user_id]["amount"]
            old_type = active_session["bets"][user_id]["type"]
            
            # If changing bet type, update the bet entirely
            if old_type != bet_type:
                active_session["bets"][user_id] = {
                    "amount": amount,
                    "type": bet_type,
                    "username": username,
                    "time": now
                }
                
                # Không sử dụng response.send_message - sẽ trả về True để bot.py xử lý thông báo
                message = f"Đã đặt cược {format_currency(amount)} vào {bet_type}."
            else:
                # Otherwise, add to the existing bet
                new_amount = old_amount + amount
                if new_amount > MAX_BET:
                    await interaction.followup.send(
                        f"Tổng cược sẽ vượt quá giới hạn tối đa ({format_currency(MAX_BET)}).",
                        ephemeral=True
                    )
                    return False
                
                if new_amount > current_balance:
                    await interaction.followup.send(
                        f"Tổng cược sẽ vượt quá số dư hiện tại của bạn ({format_currency(current_balance)}).",
                        ephemeral=True
                    )
                    return False
                
                active_session["bets"][user_id]["amount"] = new_amount
                active_session["bets"][user_id]["time"] = now
                
                # Không sử dụng response.send_message - sẽ trả về True để bot.py xử lý thông báo
                message = f"Đã đặt cược {format_currency(amount)} vào {bet_type}."
        else:
            # Create new bet
            active_session["bets"][user_id] = {
                "amount": amount,
                "type": bet_type,
                "username": username,
                "time": now
            }
            
            # Không sử dụng response.send_message - sẽ trả về True để bot.py xử lý thông báo
            message = f"Đã đặt cược {format_currency(amount)} vào {bet_type}."
        
        # Update session embed
        try:
            embed = self._create_session_embed(active_session)
            if active_session["message"]:
                await active_session["message"].edit(embed=embed)
            else:
                logger.warning(f"Session message is None for session in channel {channel_id}")
        except Exception as e:
            logger.error(f"Error updating session embed: {str(e)}")
            # Tiếp tục thực hiện dù không cập nhật được embed
        
        logger.info(f"User {username} ({user_id}) placed bet: {amount} on {bet_type}")
        
        return True
    
    async def show_history(self, interaction, user_id=None):
        """Show game history or a player's bet history."""
        if user_id:
            # Show player's bet history
            username = interaction.user.name
            bet_history = self.db.get_player_bet_history(user_id)
            
            if not bet_history:
                await interaction.followup.send(
                    "Bạn chưa có lịch sử đặt cược nào.",
                    ephemeral=True
                )
                return
            
            # Create embed with bet history
            embed = discord.Embed(
                title=f"Lịch sử cược của {username}",
                description=f"Hiển thị {len(bet_history)} kết quả gần đây nhất",
                color=discord.Color.blue()
            )
            
            # Add player balance
            balance = self.db.get_player_balance(user_id)
            embed.add_field(
                name="Số dư hiện tại",
                value=format_currency(balance),
                inline=False
            )
            
            # Add bet history
            history_text = ""
            win_count = 0
            loss_count = 0
            total_win = 0
            total_loss = 0
            
            for bet in bet_history[:10]:  # Show first 10 entries in detail
                result_emoji = "✅" if bet["result"] == "win" else "❌"
                dice_str = " ".join([self._get_dice_emoji(val) for val in bet["dice_values"]])
                
                history_text += f"{result_emoji} **{bet['bet_type']}** {format_currency(bet['bet_amount'])} → "
                
                if bet["result"] == "win":
                    history_text += f"Thắng {format_currency(bet['win_amount'])}"
                    win_count += 1
                    total_win += bet["win_amount"]
                else:
                    history_text += f"Thua {format_currency(abs(bet['win_amount']))}"
                    loss_count += 1
                    total_loss += abs(bet["win_amount"])
                
                history_text += f" | {dice_str} = {bet['total_value']} ({bet['game_result']})\n"
            
            embed.add_field(
                name="Lịch sử cược chi tiết (10 gần nhất)",
                value=history_text if history_text else "Không có dữ liệu",
                inline=False
            )
            
            # Add summary statistics
            total_bets = win_count + loss_count
            win_rate = (win_count / total_bets * 100) if total_bets > 0 else 0
            
            stats_text = (
                f"Tổng số cược: {total_bets}\n"
                f"Thắng: {win_count} ({win_rate:.1f}%)\n"
                f"Thua: {loss_count} ({100-win_rate:.1f}%)\n"
                f"Tổng thắng: {format_currency(total_win)}\n"
                f"Tổng thua: {format_currency(total_loss)}\n"
                f"Lợi nhuận: {format_currency(total_win - total_loss)}"
            )
            
            embed.add_field(
                name="Thống kê",
                value=stats_text,
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        else:
            # Show game history
            game_history = self.db.get_game_history()
            
            if not game_history:
                await interaction.followup.send(
                    "Chưa có lịch sử trò chơi nào.",
                    ephemeral=True
                )
                return
            
            # Create embed with game history
            embed = discord.Embed(
                title="Lịch sử trò chơi Tài Xỉu",
                description=f"Hiển thị {len(game_history)} kết quả gần đây nhất",
                color=discord.Color.gold()
            )
            
            # Add pattern analysis
            pattern_analysis = self.pattern_analyzer.analyze_patterns()
            patterns_detected = []
            
            if pattern_analysis["cau_bet"][0] > 0:
                streak, result = pattern_analysis["cau_bet"]
                patterns_detected.append(f"Cầu bệt: {streak} lần {result} liên tiếp")
            
            if pattern_analysis["cau_dao_1_1"] > 0:
                patterns_detected.append(f"Cầu đảo 1-1: {pattern_analysis['cau_dao_1_1']} lần luân phiên")
            
            if pattern_analysis["cau_3_2_1"]:
                patterns_detected.append("Cầu 3-2-1: Có")
            
            if pattern_analysis["cau_dao_1_2_3"]:
                patterns_detected.append("Cầu đảo 1-2-3: Có")
            
            if pattern_analysis["cau_nhip_nghieng"]:
                patterns_detected.append("Cầu nhịp nghiêng: Có")
            
            if patterns_detected:
                embed.add_field(
                    name="Phân tích mẫu",
                    value="\n".join(patterns_detected),
                    inline=False
                )
            
            # Add recent results as emojis
            result_emojis = []
            for game in game_history[:50]:  # Show last 50 results
                if game["result"] == "Tài":
                    result_emojis.append("🔴")  # Red for Tài (High)
                else:
                    result_emojis.append("⚫")  # Black for Xỉu (Low)
            
            # Split into chunks of 10 for better visibility
            emoji_chunks = [result_emojis[i:i+10] for i in range(0, len(result_emojis), 10)]
            
            for i, chunk in enumerate(emoji_chunks):
                embed.add_field(
                    name=f"Kết quả {i*10+1}-{i*10+len(chunk)}",
                    value="".join(chunk),
                    inline=False
                )
            
            # Add detailed results
            detailed_results = []
            for i, game in enumerate(game_history[:10]):  # Show details for last 10 games
                dice_str = " ".join([self._get_dice_emoji(val) for val in game["dice_values"]])
                detailed_results.append(
                    f"{i+1}. {dice_str} = {game['total_value']} ({game['result']})"
                )
            
            embed.add_field(
                name="Chi tiết 10 kết quả gần nhất",
                value="\n".join(detailed_results),
                inline=False
            )
            
            # Add statistics
            tai_count = sum(1 for game in game_history if game["result"] == "Tài")
            xiu_count = len(game_history) - tai_count
            
            stats_text = (
                f"Tài: {tai_count} ({tai_count/len(game_history)*100:.1f}%)\n"
                f"Xỉu: {xiu_count} ({xiu_count/len(game_history)*100:.1f}%)"
            )
            
            embed.add_field(
                name="Thống kê",
                value=stats_text,
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
    
    def _create_session_embed(self, session):
        """Create an embed for the current game session."""
        now = datetime.now()
        time_left = max(0, int((session["end_time"] - now).total_seconds()))
        
        # Count total bets for each type
        tai_bets = 0
        xiu_bets = 0
        tai_count = 0
        xiu_count = 0
        
        for bet_info in session["bets"].values():
            if bet_info["type"] == "Tài":
                tai_bets += bet_info["amount"]
                tai_count += 1
            else:
                xiu_bets += bet_info["amount"]
                xiu_count += 1
        
        # Tạo tiêu đề với biểu tượng thời gian phù hợp
        if time_left <= 5:
            title = "⏱️ TÀI XỈU - SẮP HẾT THỜI GIAN ĐẶT CƯỢC! ⏱️"
            color = discord.Color.red()
        elif time_left <= 10:
            title = "⏱️ Tài Xỉu - Thời gian đặt cược sắp kết thúc! ⏱️"
            color = discord.Color.orange()
        else:
            title = "🎲 Tài Xỉu - Đặt cược ngay! 🎲"
            color = discord.Color.gold()
        
        # Tạo thông báo thời gian phù hợp
        if time_left <= 5:
            time_msg = f"⚠️ **CHỈ CÒN {time_left} GIÂY!** ⚠️"
        elif time_left <= 10:
            time_msg = f"⚠️ **Chỉ còn {time_left} giây để đặt cược!** ⚠️"
        else:
            time_msg = f"Thời gian còn lại: **{time_left}s**"
        
        # Thêm cảnh báo tùy chỉnh nếu có
        warning_msg = session.get("warning_message", "")
        if warning_msg and time_left <= 10:
            time_msg = warning_msg
        
        embed = discord.Embed(
            title=title,
            description=(
                f"{time_msg}\n\n"
                f"Tài (11-18): {tai_count} người, tổng {format_currency(tai_bets)}\n"
                f"Xỉu (3-10): {xiu_count} người, tổng {format_currency(xiu_bets)}\n\n"
                f"💎 **THẮNG NHẬN GẤP ĐÔI TIỀN CƯỢC** 💎\n\n"
                f"Sử dụng lệnh `/tai_xiu dat_cuoc` để đặt cược.\n"
                f"Số tiền cược từ {format_currency(MIN_BET)} đến {format_currency(MAX_BET)}."
            ),
            color=color
        )
        
        # Add footer with explanation
        embed.set_footer(text=(
            "Tài Xỉu: 3 viên xúc xắc, tổng từ 3-10 là Xỉu, 11-18 là Tài. "
            "Thắng được GẤP ĐÔI số tiền cược, thua mất toàn bộ."
        ))
        
        # If there are bets, add them to the embed
        if session["bets"]:
            # Sort bets by time (most recent first)
            sorted_bets = sorted(
                session["bets"].items(),
                key=lambda x: x[1]["time"],
                reverse=True
            )
            
            # Show up to 10 most recent bets
            recent_bets = []
            for user_id, bet_info in sorted_bets[:10]:
                recent_bets.append(
                    f"{bet_info['username']}: {format_currency(bet_info['amount'])} ({bet_info['type']})"
                )
            
            embed.add_field(
                name="Cược gần đây",
                value="\n".join(recent_bets) if recent_bets else "Chưa có cược nào",
                inline=False
            )
        
        return embed
    
    def _create_result_embed(self, session, winners, losers):
        """Create an embed for the game result."""
        dice_str = " ".join([self._get_dice_emoji(val) for val in session["dice_values"]])
        
        # Calculate total win/loss
        total_win = sum(w["winnings"] for w in winners)
        total_loss = sum(abs(l["winnings"]) for l in losers)
        
        if session["result"] == "Tài":
            color = discord.Color.red()
            title_emoji = "🔴"
        else:
            color = discord.Color.dark_gray()
            title_emoji = "⚫"
        
        embed = discord.Embed(
            title=f"{title_emoji} Kết quả: {session['result']} {title_emoji}",
            description=(
                f"**{dice_str} = {session['total']}**\n\n"
                f"Người thắng: {len(winners)}, tổng thắng: {format_currency(total_win)}\n"
                f"Người thua: {len(losers)}, tổng thua: {format_currency(total_loss)}"
            ),
            color=color
        )
        
        # Add winners
        if winners:
            winners_text = []
            for winner in sorted(winners, key=lambda w: w["winnings"], reverse=True)[:10]:
                winners_text.append(
                    f"{winner['username']}: +{format_currency(winner['winnings'])}"
                )
            
            embed.add_field(
                name="🏆 Người thắng 🏆",
                value="\n".join(winners_text) if winners_text else "Không có người thắng",
                inline=True
            )
        
        # Add losers
        if losers:
            losers_text = []
            for loser in sorted(losers, key=lambda l: abs(l["winnings"]), reverse=True)[:10]:
                losers_text.append(
                    f"{loser['username']}: -{format_currency(abs(loser['winnings']))}"
                )
            
            embed.add_field(
                name="💸 Người thua 💸",
                value="\n".join(losers_text) if losers_text else "Không có người thua",
                inline=True
            )
        
        # Add hash verification
        seed = session.get("seed", "N/A")
        md5_hash = session.get("md5_hash", "N/A")
        
        embed.add_field(
            name="Xác thực kết quả (MD5)",
            value=f"Hash: `{md5_hash[:10]}...`",
            inline=False
        )
        
        # Add footer with explanation
        embed.set_footer(text=(
            "Phiên mới sẽ bắt đầu sau vài giây. "
            "Sử dụng lệnh /lich_su để xem lịch sử và phân tích mẫu. "
            "Thắng nhận GẤP ĐÔI tiền cược!"
        ))
        
        return embed
    
    def _get_dice_emoji(self, value):
        """Get the appropriate dice emoji for a value."""
        dice_emojis = {
            1: "1️⃣",
            2: "2️⃣",
            3: "3️⃣",
            4: "4️⃣",
            5: "5️⃣",
            6: "6️⃣"
        }
        return dice_emojis.get(value, "❓")
    
    def close(self):
        """Close the database connection."""
        self.db.close()
