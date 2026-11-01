import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Tải các biến môi trường từ file .env
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

BOT_TOKEN = os.getenv('FSBot_Token')
# Đảm bảo CHANNEL_ID được chuyển thành số nguyên int
CHANNEL_ID = int(os.getenv('Channel_ID')) if os.getenv('Channel_ID') else None

@bot.event
async def on_ready():
    print(f'Bot đã đăng nhập thành công với tên: {bot.user}')
    
    if CHANNEL_ID:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="📌 Bot đã kết nối thành công!",
                description="Hệ thống đã sẵn sàng nhận và tóm tắt thông báo.",
                color=discord.Color.blue()
            )
            await channel.send(embed=embed)
        else:
            print("Không tìm thấy Channel ID đã cấu hình trên Discord Server.")
    else:
        print("Chưa cấu hình Channel_ID trong file .env.")

if __name__ == '__main__':
    bot.run(BOT_TOKEN)