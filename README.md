# Telegram BFL.ai Image Editor Bot

A Telegram bot that uses BFL.ai's FLUX.1 Kontext [pro] model to edit images based on text prompts while maintaining original aspect ratios.

## Features

- ✅ **Dual Input Methods**: Photo with caption OR photo then text
- ✅ **Aspect Ratio Preservation**: Automatically maintains original image ratios
- ✅ **Advanced AI Editing**: Uses BFL.ai's state-of-the-art FLUX.1 Kontext [pro] model
- ✅ **User-Friendly Interface**: Clear instructions and status updates
- ✅ **Error Handling**: Robust error handling and user feedback
- ✅ **Render.com Ready**: Configured for easy deployment

## Setup

### 1. Get API Keys

- **Telegram Bot Token**: Message [@BotFather](https://t.me/botfather) on Telegram
- **BFL.ai API Key**: Sign up at [BFL.ai](https://api.bfl.ai/)

### 2. Deploy on Render.com

1. Fork this repository
2. Connect to Render.com
3. Create a new **Background Worker** service
4. Set environment variables:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
   - `BFL_API_KEY`: Your BFL.ai API key

### 3. Local Development

```bash
# Clone and install
git clone <your-repo>
cd telegram-bfl-bot
pip install -r requirements.txt

# Set environment variables
export TELEGRAM_BOT_TOKEN="your_token"
export BFL_API_KEY="your_key"

# Run
python bot.py
```

## Usage

### Method 1: Photo with Caption (Quick)
Send a photo with your editing instruction as the caption:
📷 + "Change the car color to blue"

### Method 2: Step-by-Step
1. Send a photo
2. Send text: "Change the car color to blue"

## Commands

- `/start` - Show welcome message
- `/help` - Show help and usage instructions  
- `/clear` - Clear current image from memory

## Supported Edits

- Color changes
- Object modifications
- Adding/removing elements
- Text overlays
- Style transformations
- Background changes

## Technical Details

- **Model**: BFL.ai FLUX.1 Kontext [pro]
- **Supported Ratios**: 3:7 to 7:3 (automatically detected)
- **Max Image Size**: 20MB or 20 megapixels
- **Processing Time**: 10-30 seconds typically
- **Output Format**: JPEG

