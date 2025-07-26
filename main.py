import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import json, os, asyncio, random
from dotenv import load_dotenv

# 載入 .env 檔案
load_dotenv()

# 從 .env 讀取機器人令牌和角色ID
ROLE_ID = int(os.getenv("ROLE_ID"))  # 替換為你在 .env 檔案中定義的角色ID
TOKEN = os.getenv("DISCORD_TOKEN")  # 從 .env 檔案讀取機器人 Token

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)
lotteries = {}
SAVE_FILE = "lotteries.json"

@bot.event
async def on_ready():
    print(f"✅ Bot {bot.user.name} 已上線!")
    load_lotteries()
    bot.add_view(LotteryView())
    await bot.tree.sync()

# 儲存 & 載入抽獎資料
def save_lotteries():
    with open(SAVE_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            name: {
                'end_time': info['end_time'].strftime('%Y-%m-%d %H:%M:%S'),
                'participants': info['participants'],
                'prize': info['prize'],
                'winner_count': info['winner_count'],
                'channel_id': info['channel_id'],
                'guild_id': info['guild_id'],
                'start_e': info['start_e'],
                'message_id': info['message_id'],
                'stop': info['stop']
            } for name, info in lotteries.items()
        }, f, ensure_ascii=False, indent=4)

def load_lotteries():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
            for name, info in json_data.items():
                end_time = datetime.strptime(info['end_time'], '%Y-%m-%d %H:%M:%S')
                lotteries[name] = {
                    'end_time': end_time,
                    'participants': info['participants'],
                    'prize': info['prize'],
                    'winner_count': info['winner_count'],
                    'channel_id': info['channel_id'],
                    'guild_id': info['guild_id'],
                    'start_e': info['start_e'],
                    'message_id': info['message_id'],
                    'stop': info['stop']
                }
                if datetime.now() < end_time:
                    bot.loop.create_task(countdown_to_end(name, end_time, info['winner_count'], info['guild_id'], info['start_e'], info['stop']))
                else:
                    del lotteries[name]
                    save_lotteries()

# 抽獎 UI 按鈕
class LotteryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💎加入抽獎", style=discord.ButtonStyle.green, custom_id="persistent_view:join")
    async def join_lottery(self, interaction: discord.Interaction, button: discord.ui.Button):
        name = next((key for key, value in lotteries.items() if value['message_id'] == interaction.message.id), None)
        lottery = lotteries.get(name)
        if not lottery:
            await interaction.response.send_message("❌ 此抽獎活動不存在或已結束！", ephemeral=True)
            return

        if interaction.user.name in lottery['participants']:
            lottery['participants'].remove(interaction.user.name)
            await interaction.response.send_message(f"❌ 你已退出 `{name}` 抽獎!", ephemeral=True)
        else:
            lottery['participants'].append(interaction.user.name)
            await interaction.response.send_message(f"✅ 你已加入 `{name}` 抽獎!", ephemeral=True)

        save_lotteries()

    @discord.ui.button(label="🌐顯示參與者", style=discord.ButtonStyle.blurple, custom_id="persistent_view:show")
    async def show_participants(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 只有擁有管理員身分組的成員才能查看參與者
        if any(role.id == ROLE_ID for role in interaction.user.roles):
            name = next((key for key, value in lotteries.items() if value['message_id'] == interaction.message.id), None)
            lottery = lotteries.get(name)
            if lottery:
                participants = '\n'.join([f"`{p}`" for p in lottery['participants']]) or "目前沒有參與者"
                embed = discord.Embed(title="📜 參與者名單", description=participants, color=discord.Color.blue())
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("❌ 此抽獎活動不存在或已結束！", ephemeral=True)
        else:
            await interaction.response.send_message("🚫 你沒有權限查看參與者！", ephemeral=True)

async def countdown_to_end(name: str, end_time: datetime, winner_count: int, guild_id, start_e, stop):
    remaining_seconds = (end_time - datetime.now()).total_seconds()
    if remaining_seconds > 0:
        await asyncio.sleep(remaining_seconds)

    lottery = lotteries.get(name)
    if lottery and not lottery['stop']:
        participants = lottery['participants']
        channel = bot.get_channel(lottery['channel_id'])
        message = await channel.fetch_message(lottery['message_id'])
        if participants:
            winners = random.sample(participants, min(len(participants), winner_count))
            winners_mentions = ', '.join([f"`{w}`" for w in winners])
            embed = discord.Embed(title="🎉 抽獎結束!", description=f"🏆 得獎者: {winners_mentions}\n🎁 獎品: {lottery['prize']}", color=discord.Color.gold())
        else:
            embed = discord.Embed(title="❌ 抽獎結束!", description="⚠️ 無人參加，沒有得獎者。", color=discord.Color.red())

        await message.edit(embed=embed, view=None)
        del lotteries[name]
        save_lotteries()

# 限制特定身分組可執行
def has_admin_role():
    async def predicate(interaction: discord.Interaction) -> bool:
        return any(role.id == ROLE_ID for role in interaction.user.roles)
    return app_commands.check(predicate)

# 創建抽獎
@bot.tree.command(name="創建抽獎活動", description="創建新的抽獎活動")
@has_admin_role()
async def create_lottery(interaction: discord.Interaction, 名稱: str, 獎品: str, 抽出人數: int, 時間: int):
    if 名稱 in lotteries:
        await interaction.response.send_message(f"❌ `{名稱}` 已存在！", ephemeral=True)
        return

    end_time = datetime.now() + timedelta(minutes=時間)
    message = await interaction.response.send_message("⌛ 創建中...")
    lotteries[名稱] = {
        'end_time': end_time,
        'participants': [],
        'prize': 獎品,
        'winner_count': 抽出人數,
        'channel_id': interaction.channel.id,
        'guild_id': interaction.guild.id,
        'start_e': interaction.user.id,
        'message_id': message.id,
        'stop': False
    }
    save_lotteries()

    embed = discord.Embed(title="🎊 抽獎開始!", description=f"🏆 獎品: {獎品}\n⏳ 截止時間: {end_time.strftime('%Y-%m-%d %H:%M:%S')}", color=discord.Color.green())
    await message.edit(content=None, embed=embed, view=LotteryView())

# 刪除抽獎
@bot.tree.command(name="刪除抽獎活動", description="刪除一個抽獎活動")
@has_admin_role()
async def delete_lottery(interaction: discord.Interaction, name: str):
    if name in lotteries:
        del lotteries[name]
        save_lotteries()
        await interaction.response.send_message(f"🗑 `{name}` 已刪除!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ 此抽獎不存在！", ephemeral=True)

# 啟動 bot 使用 .env 裡的 Token
bot.run(TOKEN)