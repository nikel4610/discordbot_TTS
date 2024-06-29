import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv
from navertts import NaverTTS
# https://discord.com/oauth2/authorize?client_id=1234120588877107240&permissions=2168832&scope=bot
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
TARGET_CHANNEL_ID = int(os.getenv('TARGET_CHANNEL_ID'))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='', intents=intents)


async def speak_message(message, voice_client):
    tts = NaverTTS(message.content, speed=0)
    tts.save('tts.mp3')

    if voice_client.is_playing():
        voice_client.stop()

    voice_client.play(discord.FFmpegPCMAudio('tts.mp3'), after=lambda e: print('done', e))

    while voice_client.is_playing():
        await asyncio.sleep(1)


async def voice_disconnect_after_delay(voice_client, delay):
    await asyncio.sleep(delay)
    await voice_disconnect(voice_client)


async def voice_disconnect(voice_client, message_channel):
    if voice_client.is_connected():
        tts = NaverTTS('저는 이만 들어가볼게요', speed=0)
        tts.save('tts.mp3')

        voice_client.play(discord.FFmpegPCMAudio('tts.mp3'))

        await asyncio.sleep(3)

        await voice_client.disconnect()
        await message_channel.send('음성 채널에서 나갔어요!')


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
                await voice_disconnect(voice_client, message.channel)
            else:
                await message.channel.send('음성 채널에 접속 중이 아니에요!')
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

            await voice_disconnect_after_delay(voice_client, 10.0)


bot.run(BOT_TOKEN)
