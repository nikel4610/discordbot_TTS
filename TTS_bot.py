import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv
from navertts import NaverTTS

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
TARGET_CHANNEL_ID = int(os.getenv('TARGET_CHANNEL_ID'))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='', intents=intents)

def preprocess_message_content(content):
    content = content.replace('ㅋ', '크').replace('ㅎ', '흐').replace('ㅠ', '유')
    return content


async def speak_message(message, voice_client):
    processed_content = preprocess_message_content(message.content)
    tts = NaverTTS(processed_content, speed=0)
    # tts = NaverTTS(message.content, speed=0)
    tts.save('tts.mp3')

    if voice_client.is_playing():
        voice_client.stop()

    voice_client.play(discord.FFmpegPCMAudio('tts.mp3'), after=lambda e: print('done', e))

    while voice_client.is_playing():
        await asyncio.sleep(1)


async def voice_disconnect_after_delay(voice_client, delay):
    print(f"Starting delay of {delay} seconds")
    await asyncio.sleep(delay)
    print("Delay finished, attempting to disconnect")
    await voice_disconnect(voice_client)


async def voice_disconnect(voice_client):
    if voice_client.is_connected():
        tts = NaverTTS('무식이는 이만 나가볼게요', speed=0)
        tts.save('tts.mp3')

        voice_client.play(discord.FFmpegPCMAudio('tts.mp3'))

        await asyncio.sleep(3)

        await voice_client.disconnect()
        print("Disconnected from voice channel")


async def find_voice_channel(guild, user):
    for vc in guild.voice_channels:
        if user in [member for member in vc.members if not member.bot]:
            return vc
    return None


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id == TARGET_CHANNEL_ID:
        if message.content == '!leave':
            voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if voice_client:
                await voice_disconnect(voice_client)
                await message.channel.send('음성 채널에서 나갔어요!')
            else:
                await message.channel.send('음성 채널에 접속 중이 아니에요!')
        elif message.content == '!update':
            embed = discord.Embed(
                title="최근 업데이트 내역입니다 (2024.06.29)",
                description="업데이트 내용을 확인하세요.\n\n---",
                color=discord.Color.blue()
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
            if not bot.voice_clients:
                voice_channel = await find_voice_channel(message.guild, message.author)
                if voice_channel:
                    await voice_channel.connect()
                else:
                    await message.channel.send('음성 채널을 찾을 수 없어요!')
                    return

            voice_client = bot.voice_clients[0]

            await speak_message(message, voice_client)

            await voice_disconnect_after_delay(voice_client, 300.0)


bot.run(BOT_TOKEN)
