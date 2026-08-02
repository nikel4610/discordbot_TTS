import asyncio
import logging
import os
import tempfile

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from imageio_ffmpeg import get_ffmpeg_exe
from navertts import NaverTTS

load_dotenv()

logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO').upper(),
    format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
)
LOGGER = logging.getLogger('tts-bot')

BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN:
    raise RuntimeError('BOT_TOKEN is missing. Set it in the .env file.')

try:
    TARGET_CHANNEL_IDS = {
        int(channel_id.strip())
        for channel_id in os.getenv('TARGET_CHANNEL_IDS', '').split(',')
        if channel_id.strip()
    }
except ValueError as exc:
    raise RuntimeError('TARGET_CHANNEL_IDS must be comma-separated Discord channel IDs.') from exc

if not TARGET_CHANNEL_IDS:
    raise RuntimeError('TARGET_CHANNEL_IDS is missing. Set at least one text channel ID in the .env file.')

try:
    MAX_TTS_LENGTH = int(os.getenv('MAX_TTS_LENGTH', '300'))
except ValueError as exc:
    raise RuntimeError('MAX_TTS_LENGTH must be an integer.') from exc

FFMPEG_EXECUTABLE = get_ffmpeg_exe()
BOT_SMOKE_TEST = os.getenv('BOT_SMOKE_TEST') == '1'

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

voice_clients = {}
tts_queues = {}
tts_workers = set()
disconnecting_sessions = set()

def preprocess_message_content(content):
    content = content.strip()
    content = content.replace('ㅋ', '크').replace('ㅎ', '흐').replace('ㅠ', '유')
    if len(content) > MAX_TTS_LENGTH:
        content = f'{content[:MAX_TTS_LENGTH]}... 이하 생략'
    return content


def get_message_content(message):
    content = message.clean_content.strip()
    if content:
        return content
    if message.attachments:
        return '첨부 파일을 보냈어요.'
    return ''


def get_session_key(message):
    return (message.guild.id, message.channel.id)


def remove_file(filename):
    try:
        os.remove(filename)
    except FileNotFoundError:
        pass
    except OSError as exc:
        LOGGER.warning('Failed to remove temp file %s: %s', filename, exc)


def create_tts_file_sync(content, prefix):
    processed_content = preprocess_message_content(content)
    tts = NaverTTS(processed_content, speed=0)

    with tempfile.NamedTemporaryFile(prefix=prefix, suffix='.mp3', delete=False) as temp_file:
        filename = temp_file.name

    try:
        tts.save(filename)
    except Exception:
        remove_file(filename)
        raise

    return filename


async def create_tts_file(content, prefix):
    return await asyncio.to_thread(create_tts_file_sync, content, prefix)


async def play_audio_file(voice_client, filename):
    done = asyncio.Event()

    def after_play(error):
        if error:
            LOGGER.warning('Audio playback error: %s', error)
        remove_file(filename)
        bot.loop.call_soon_threadsafe(done.set)

    try:
        voice_client.play(
            discord.FFmpegPCMAudio(filename, executable=FFMPEG_EXECUTABLE),
            after=after_play,
        )
    except Exception:
        remove_file(filename)
        raise

    await done.wait()


async def speak_message(message, voice_client):
    content = get_message_content(message)
    if not content:
        return

    filename = await create_tts_file(content, f'tts_{message.guild.id}_{message.channel.id}_')
    await play_audio_file(voice_client, filename)


async def tts_worker(session_key):
    queue = tts_queues.get(session_key)
    if not queue:
        tts_workers.discard(session_key)
        return

    try:
        while True:
            if session_key in disconnecting_sessions:
                break

            message = await queue.get()
            try:
                if session_key in disconnecting_sessions:
                    continue

                voice_client = voice_clients.get(session_key)
                if not voice_client or not voice_client.is_connected():
                    voice_channel = await find_voice_channel(message.guild, message.author)
                    if not voice_channel:
                        await message.channel.send('음성 채널을 찾을 수 없어요!')
                        continue

                    try:
                        voice_client = await voice_channel.connect()
                    except discord.DiscordException as exc:
                        LOGGER.warning('Voice channel connect failed: %s', exc)
                        await message.channel.send('음성 채널에 접속하지 못했어요. 봇 권한을 확인해주세요.')
                        continue

                    voice_clients[session_key] = voice_client

                await speak_message(message, voice_client)
            except Exception as exc:
                LOGGER.exception('TTS playback failed: %s', exc)
                await message.channel.send('TTS 재생 중 문제가 생겼어요.')
            finally:
                queue.task_done()

            if session_key in disconnecting_sessions:
                break

            if queue.empty():
                break
    finally:
        tts_workers.discard(session_key)
        queue = tts_queues.get(session_key)
        if queue and not queue.empty() and session_key not in disconnecting_sessions:
            tts_workers.add(session_key)
            asyncio.create_task(tts_worker(session_key))


async def enqueue_tts_message(message):
    session_key = get_session_key(message)
    if session_key in disconnecting_sessions:
        await message.channel.send('음성 채널에서 나가는 중이에요. 잠시 후 다시 입력해주세요.')
        return

    queue = tts_queues.setdefault(session_key, asyncio.Queue())
    await queue.put(message)

    if session_key not in tts_workers:
        tts_workers.add(session_key)
        asyncio.create_task(tts_worker(session_key))


def clear_queue(queue):
    while not queue.empty():
        try:
            queue.get_nowait()
            queue.task_done()
        except asyncio.QueueEmpty:
            break


async def voice_disconnect(session_key, voice_client):
    disconnecting_sessions.add(session_key)
    queue = tts_queues.get(session_key)
    if queue:
        clear_queue(queue)

    try:
        if not voice_client.is_connected():
            return
        if voice_client.is_playing():
            voice_client.stop()

        try:
            filename = await create_tts_file('무식이는 이만 나가볼게요', f'tts_disconnect_{session_key[0]}_{session_key[1]}_')
            await play_audio_file(voice_client, filename)
        except Exception as exc:
            LOGGER.warning('Disconnect TTS failed: %s', exc)

        await voice_client.disconnect()
    finally:
        voice_clients.pop(session_key, None)
        tts_queues.pop(session_key, None)
        disconnecting_sessions.discard(session_key)
        LOGGER.info('Disconnected from voice channel (Guild ID: %s, Channel ID: %s)', session_key[0], session_key[1])

async def find_voice_channel(guild, user):
    if not guild:
        return None

    voice_state = getattr(user, 'voice', None)
    if voice_state and voice_state.channel:
        return voice_state.channel

    return None

@bot.event
async def on_ready():
    LOGGER.info('We have logged in as %s', bot.user)
    if not check_voice_channel.is_running():
        check_voice_channel.start()
    if BOT_SMOKE_TEST:
        await bot.close()

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if not message.guild:
        return

    if message.channel.id in TARGET_CHANNEL_IDS:
        content = message.content.strip()
        session_key = get_session_key(message)

        if content == '!leave':
            voice_client = voice_clients.get(session_key)
            if voice_client:
                await voice_disconnect(session_key, voice_client)
                await message.channel.send('음성 채널에서 나갔어요!')
            else:
                await message.channel.send('음성 채널에 접속 중이 아니에요!')
        elif content == '!help':
            embed = discord.Embed(
                title='무식봇 사용 방법',
                description='텍스트 채널에 입력한 내용을 같은 서버의 음성 채널에서 읽어줍니다.',
                color=discord.Color.blue()
            )
            embed.add_field(
                name='TTS 읽기',
                value='음성 채널에 들어간 상태에서 이 채널에 메시지를 보내면 순서대로 읽어줍니다.',
                inline=False
            )
            embed.add_field(
                name='명령어',
                value='`!help` 사용 방법 보기\n`!leave` 음성 채널에서 나가기',
                inline=False
            )
            embed.add_field(
                name='주의',
                value=f'서버별로 독립 동작하며, 등록된 텍스트 채널에서만 반응합니다.\n한 번에 읽는 글자 수는 최대 {MAX_TTS_LENGTH}자입니다.',
                inline=False
            )
            await message.channel.send(embed=embed)
        elif content.startswith('!'):
            await message.channel.send('알 수 없는 명령어예요. `!help`를 입력해 사용 방법을 확인하세요.')
        else:
            await enqueue_tts_message(message)

@tasks.loop(minutes=1)
async def check_voice_channel():
    for session_key, voice_client in list(voice_clients.items()):
        has_human_member = any(not member.bot for member in voice_client.channel.members)
        if not has_human_member:
            await voice_disconnect(session_key, voice_client)

if __name__ == '__main__':
    bot.run(BOT_TOKEN, log_handler=None)
