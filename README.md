# Discord TTS Bot

마이크를 쓰기 어려운 사용자가 텍스트 채널에 메시지를 입력하면, 봇이 같은 사용자가 들어가 있는 음성 채널에서 TTS로 읽어주는 개인용 Discord 봇입니다.

## Setup

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Ubuntu 서버에서는 Discord 음성 송출에 Opus 라이브러리가 필요합니다.

```bash
sudo apt update
sudo apt install -y libopus0
```

`.env`에 Discord 봇 토큰과 읽을 텍스트 채널 ID를 설정합니다.

```dotenv
BOT_TOKEN=your_discord_bot_token_here
TARGET_CHANNEL_IDS=123456789012345678,234567890123456789
MAX_TTS_LENGTH=300
```

Discord Developer Portal의 Bot 설정에서 `Message Content Intent`를 켜야 일반 메시지 내용을 읽을 수 있습니다.

## Run

```powershell
python TTS_bot.py
```

접속 확인만 할 때는 다음처럼 실행합니다.

```powershell
$env:BOT_SMOKE_TEST='1'
python -u TTS_bot.py
```
