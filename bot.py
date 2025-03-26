import discord
import logging
import asyncio
import os
from discord import app_commands
from discord.ext import commands
from config import TOKEN, MIN_BET, MAX_BET, DEFAULT_BALANCE
from game import TaiXiuGame
from utils import format_currency

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TaiXiuBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(command_prefix="!", intents=intents)
        self.game = None
    
    async def setup_hook(self):
        """Set up the bot's game and commands."""
        self.game = TaiXiuGame(self)
        
        # Register command tree
        await self.tree.sync()
        logger.info("Command tree synced")
    
    async def on_ready(self):
        """Run when the bot is ready."""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")
        
        # Set bot presence
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name="Tài Xỉu | /tai_xiu"
            )
        )

# Create the bot instance
bot = TaiXiuBot()

@bot.tree.command(name="tai_xiu", description="Chơi trò chơi Tài Xỉu")
async def tai_xiu(interaction: discord.Interaction):
    """Main command for the Tài Xỉu game."""
    await bot.game.start_session(interaction)

@bot.tree.command(name="dat_cuoc", description="Đặt cược vào Tài hoặc Xỉu")
@app_commands.describe(
    amount="Số tiền cược (từ 10,000 đến 1,000,000)",
    bet_type="Loại cược (Tài hoặc Xỉu)"
)
@app_commands.choices(bet_type=[
    app_commands.Choice(name="Tài (11-18)", value="Tài"),
    app_commands.Choice(name="Xỉu (3-10)", value="Xỉu")
])
async def dat_cuoc(
    interaction: discord.Interaction, 
    amount: int, 
    bet_type: str
):
    """Place a bet on Tài or Xỉu."""
    try:
        # Phản hồi ngay lập tức để tránh lỗi Unknown Interaction (10062)
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.errors.NotFound:
            # Nếu tương tác đã hết hạn, ghi log và thoát
            logger.warning(f"Interaction expired before deferred: {interaction.id}")
            return
        except Exception as e:
            logger.error(f"Error on defer: {str(e)}")
            return
            
        # Sau đó mới xử lý đặt cược
        try:
            success = await bot.game.place_bet(interaction, amount, bet_type)
            # Nếu đặt cược thành công, cần phản hồi vì đã sử dụng defer
            if success:
                try:
                    await interaction.followup.send(
                        f"Đã đặt cược {format_currency(amount)} vào {bet_type}.",
                        ephemeral=True
                    )
                except Exception as e:
                    logger.error(f"Error sending confirmation: {str(e)}")
        except AttributeError as e:
            # Nếu có lỗi trong quá trình đặt cược
            logger.error(f"Error in place_bet (AttributeError): {str(e)}")
            try:
                await interaction.followup.send(
                    "Có lỗi khi đặt cược. Vui lòng thử lại sau hoặc bắt đầu phiên mới với `/tai_xiu`.",
                    ephemeral=True
                )
            except:
                pass
        except Exception as e:
            # Nếu có lỗi trong quá trình đặt cược
            logger.error(f"Error in place_bet: {str(e)}")
            try:
                await interaction.followup.send(
                    "Có lỗi khi đặt cược. Vui lòng thử lại sau.",
                    ephemeral=True
                )
            except:
                pass
    except Exception as e:
        logger.error(f"Lỗi nghiêm trọng trong lệnh dat_cuoc: {str(e)}")
        # Không làm gì thêm - đã xử lý hết các trường hợp lỗi

@bot.tree.command(name="lich_su", description="Xem kết quả ngẫu nhiên hoặc lịch sử cược cá nhân")
@app_commands.describe(
    type="Loại dữ liệu muốn xem"
)
@app_commands.choices(type=[
    app_commands.Choice(name="Kết quả ngẫu nhiên", value="game"),
    app_commands.Choice(name="Lịch sử cá nhân", value="user")
])
async def lich_su(
    interaction: discord.Interaction,
    type: str = "game"
):
    """Xem kết quả ngẫu nhiên hoặc lịch sử cá nhân."""
    # Phản hồi ngay lập tức để tránh lỗi Unknown Interaction (10062)
    await interaction.response.defer(ephemeral=False)
    
    if type == "user":
        user_id = str(interaction.user.id)
        await bot.game.show_history(interaction, user_id)
    else:
        await bot.game.show_history(interaction)

@bot.tree.command(name="so_du", description="Xem số dư của bạn")
async def so_du(interaction: discord.Interaction):
    """View your current balance."""
    # Phản hồi ngay lập tức để tránh lỗi Unknown Interaction (10062)
    await interaction.response.defer(ephemeral=True)
    
    user_id = str(interaction.user.id)
    username = interaction.user.name
    
    # Get or create player
    player = bot.game.db.get_or_create_player(user_id, username)
    balance = player["balance"]
    
    await interaction.followup.send(
        f"Số dư của bạn: {format_currency(balance)}",
        ephemeral=True
    )

@bot.tree.command(name="huong_dan", description="Xem hướng dẫn chơi Tài Xỉu")
async def huong_dan(interaction: discord.Interaction):
    """View game instructions."""
    # Phản hồi ngay lập tức để tránh lỗi Unknown Interaction (10062)
    await interaction.response.defer(ephemeral=False)
    
    embed = discord.Embed(
        title="Hướng dẫn chơi Tài Xỉu",
        description="Tài Xỉu là trò chơi đơn giản nhưng hấp dẫn, dựa trên tổng điểm của 3 viên xúc xắc.",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="Luật chơi",
        value=(
            "- 3 viên xúc xắc được gieo ngẫu nhiên\n"
            "- Tổng điểm từ 3-10: **Xỉu**\n"
            "- Tổng điểm từ 11-18: **Tài**\n"
            "- Thắng: Nhận lại số tiền cược\n"
            "- Thua: Mất số tiền cược"
        ),
        inline=False
    )
    
    embed.add_field(
        name="Cách chơi",
        value=(
            "1. Sử dụng lệnh `/tai_xiu` để bắt đầu phiên mới\n"
            "2. Đặt cược bằng lệnh `/dat_cuoc amount bet_type`\n"
            "   - amount: Số tiền từ 10,000 đến 1,000,000\n"
            "   - bet_type: Tài hoặc Xỉu\n"
            "3. Đợi kết quả sau 40 giây\n"
            "4. Xem lịch sử bằng lệnh `/lich_su`"
        ),
        inline=False
    )
    
    embed.add_field(
        name="Các lệnh khác",
        value=(
            "- `/so_du`: Xem số dư của bạn\n"
            "- `/lich_su game`: Xem lịch sử trò chơi\n"
            "- `/lich_su user`: Xem lịch sử cược cá nhân\n"
            "- `/huong_dan`: Xem hướng dẫn này"
        ),
        inline=False
    )
    
    embed.add_field(
        name="Ghi chú",
        value=(
            "- Mỗi người chơi bắt đầu với 1,000,000 tiền ảo\n"
            "- Nếu hết tiền, bạn sẽ được hoàn lại 1,000,000\n"
            "- Trò chơi chỉ để giải trí, không liên quan đến tiền thật\n"
            "- Tìm hiểu các mẫu cầu để tăng cơ hội thắng!"
        ),
        inline=False
    )
    
    await interaction.followup.send(embed=embed)

def run_bot():
    """Run the bot."""
    try:
        bot.run(TOKEN)
    except Exception as e:
        logger.error(f"Error running bot: {e}")
    finally:
        # Clean up
        if bot.game:
            bot.game.close()
