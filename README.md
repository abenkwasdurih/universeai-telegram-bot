# UniverseAI Telegram Bot

This is the implementation of the Telegram Bot for UniverseAI, integrated with the existing Supabase backend.

## Prerequisites

- Node.js installed (v18+)
- Postgres/Supabase credentials
- Telegram Bot Token (from @BotFather)

## Installation

1. Navigate to this directory:
   ```bash
   cd telegram-bot
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

## Configuration

The bot uses the `config.ts` file which reads from environment variables.
Create a `.env` file in this directory (or set them in your VPS environment manager like Coolify/PM2).

**Required Environment Variables:**
```env
BOT_TOKEN=your_telegram_bot_token
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
R2_ACCOUNT_ID=your_r2_account_id
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret
R2_BUCKET_NAME=your_bucket_name
R2_PUBLIC_URL=https://your-r2-public-url.com
```

## Running

**Development:**
```bash
npm run dev
```

**Production:**
1. Build the project:
   ```bash
   npm run build
   ```
2. Start the bot:
   ```bash
   npm start
   ```

## Daemon/VPS (PM2)

To keep the bot running in the background:
```bash
npm install -g pm2
pm2 start dist/bot.js --name universe-bot
pm2 save
pm2 startup
```

## Features

- **Login**: `/login <code_access>`
- **Logout**: `/logout`
- **Takeover**: `/takeover` (Switch session from Web to Telegram)
- **Status**: `/status` (Check credits)
- **Generate**: Send an image, then reply with a prompt.
- **Polls**: Automatically polls for video completion.
