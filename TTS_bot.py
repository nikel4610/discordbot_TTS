import asyncio
import os
import time

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from imageio_ffmpeg import get_ffmpeg_exe
from navertts import NaverTTS

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN:
    raise RuntimeError('BOT_TOKEN is missing. Set it in the .env file.')

try:
    TARGET_CHANNEL_IDS = [
        int(channel_id.strip())
        for channel_id in os.getenv('TARGET_CHANNEL_IDS', '').split(',')
        if channel_id.strip()
    ]
except ValueError as exc:
    raise RuntimeError('TARGET_CHANNEL_IDS must be comma-separated Discord channel IDs.') from exc

if not TARGET_CHANNEL_IDS:
    raise RuntimeError('TARGET_CHANNEL_IDS is missing. Set at least one text channel ID in the .env file.')

FFMPEG_EXECUTABLE = get_ffmpeg_exe()
BOT_SMOKE_TEST = os.getenv('BOT_SMOKE_TEST') == '1'

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='', intents=intents)

voice_clients = {}

def preprocess_message_content(content):
    content = content.replace('ㅋ', '크').replace('ㅎ', '흐').replace('ㅠ', '유')
    return content

async def speak_message(message, voice_client):
    processed_content = preprocess_message_content(message.content)
    tts = NaverTTS(processed_content, speed=0)
    
    filename = f'tts_{message.channel.id}_{int(time.time())}.mp3'
    tts.save(filename)

    if voice_client.is_playing():
        voice_client.stop()

    voice_client.play(
        discord.FFmpegPCMAudio(filename, executable=FFMPEG_EXECUTABLE),
        after=lambda e: os.remove(filename),
    )

    while voice_client.is_playing():
        await asyncio.sleep(1)

async def voice_disconnect(voice_client, channel_id):
    if voice_client.is_connected():
        tts = NaverTTS('무식이는 이만 나가볼게요', speed=0)
        filename = f'tts_disconnect_{channel_id}_{int(time.time())}.mp3'
        tts.save(filename)

        voice_client.play(discord.FFmpegPCMAudio(filename, executable=FFMPEG_EXECUTABLE))

        await asyncio.sleep(3)
        os.remove(filename)

        await voice_client.disconnect()
        del voice_clients[channel_id]
        print(f"Disconnected from voice channel (Channel ID: {channel_id})")

async def find_voice_channel(guild, user):
    for vc in guild.voice_channels:
        if user in [member for member in vc.members if not member.bot]:
            return vc
    return None

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}', flush=True)
    if not check_voice_channel.is_running():
        check_voice_channel.start()
    if BOT_SMOKE_TEST:
        await bot.close()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id in TARGET_CHANNEL_IDS:
        if message.content == '!leave':
            voice_client = voice_clients.get(message.channel.id)
            if voice_client:
                await voice_disconnect(voice_client, message.channel.id)
                await message.channel.send('음성 채널에서 나갔어요!')
            else:
                await message.channel.send('음성 채널에 접속 중이 아니에요!')
        elif message.content == '!update':
            embed = discord.Embed(
                title="최근 업데이트 내역입니다 (2024.07.27)",
                description="업데이트 내용을 확인하세요.\n\n---",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="7월 27일 업데이트 내용",
                value="1. 무식이 수출 완료\n",
                inline=False
            )
            embed.add_field(
                name="\u200b", 
                value="\u200b",
                inline=False
            )
            embed.add_field(
                name="7월 1일 업데이트 내용",
                value="1. 혼자 남겨졌을 때 자동으로 나가는 기능 추가\n"
                    "2. 300초 뒤에 자동으로 나가는 기능 제거",
                inline=False
            )
            embed.add_field(
                name="\u200b", 
                value="\u200b",
                inline=False
            )
            embed.add_field(
                name="6월 29일 업데이트 내용",
                value="1. !update 명령어 추가 (업데이트 내용 출력)\n"
                    "2. 'ㅋ' -> '크', 'ㅎ' -> '흐', 'ㅠ' -> '유' 로 읽도록 수정",
                inline=False
            )
            embed.add_field(
                name="\u200b", 
                value="\u200b",
                inline=False
            )
            embed.add_field(
                name="4월 28일 업데이트 내용", 
                value="1. 디스코드 봇 추가\n"
                    "2. !leave 명령어 추가 (음성 채널 나가기)\n"
                    "3. 300초 후 자동 나가기 기능 추가",
                inline=False
            )
            await message.channel.send(embed=embed)
        else:
            voice_client = voice_clients.get(message.channel.id)
            if not voice_client:
                voice_channel = await find_voice_channel(message.guild, message.author)
                if voice_channel:
                    voice_client = await voice_channel.connect()
                    voice_clients[message.channel.id] = voice_client
                else:
                    await message.channel.send('음성 채널을 찾을 수 없어요!')
                    return

            await speak_message(message, voice_client)

@tasks.loop(minutes=1)
async def check_voice_channel():
    for channel_id, voice_client in list(voice_clients.items()):
        if len(voice_client.channel.members) == 1:  # Only the bot is in the channel
            await voice_disconnect(voice_client, channel_id)

if __name__ == '__main__':
    bot.run(BOT_TOKEN)
