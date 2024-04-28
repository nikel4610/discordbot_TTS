import asyncio
import os
import time

from discord.ext.commands import Bot
from dotenv import load_dotenv
from navertts import NaverTTS
import discord

load_dotenv()
# https://discord.com/oauth2/authorize?client_id=1234120588877107240&permissions=2168832&scope=bot

BOT_TOKEN = os.getenv('BOT_TOKEN')
VOICE_CHANNEL_ID = os.getenv('VOICE_CHANNEL_ID')

intents = discord.Intents.default()
intents.message_content = True

bot = Bot('', intents=intents)

disconnect_timer = None


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')


@bot.event
async def on_message(message):
    global disconnect_timer

    if message.author.bot:
        return

    if bot.voice_clients == []:
        channel = bot.get_channel(int(VOICE_CHANNEL_ID))
        await channel.connect()

    voice = bot.voice_clients[0]

    tts = NaverTTS(message.content, speed=0)
    tts.save('tts.mp3')

    if voice.is_playing():
        voice.stop()

    voice.play(discord.FFmpegPCMAudio('tts.mp3'), after=lambda e: print('done', e))

    while voice.is_playing():
        await asyncio.sleep(1)

    if disconnect_timer:
        disconnect_timer.cancel()

    disconnect_timer = asyncio.create_task(voice_disconnect_after_delay(5.0))


async def voice_disconnect_after_delay(delay):
    await asyncio.sleep(delay)
    await voice_disconnect()


async def voice_disconnect():
    global disconnect_timer

    voice = bot.voice_clients[0]
    if voice.is_connected():
        tts = NaverTTS('저는 이만 들어가볼게요', speed=0)
        tts.save('tts.mp3')

        voice.play(discord.FFmpegPCMAudio('tts.mp3'))

        time.sleep(3)

        await voice.disconnect()

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
bot.run(BOT_TOKEN)