import logging
import os
import requests
import base64
import time
import io
from PIL import Image
from telegram import Update, ForceReply
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Environment variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
BFL_API_KEY = os.environ.get("BFL_API_KEY")

if not TELEGRAM_BOT_TOKEN or not BFL_API_KEY:
    logger.error("Please set TELEGRAM_BOT_TOKEN and BFL_API_KEY environment variables.")
    exit(1)

def get_aspect_ratio(image_bytes):
    """Calculate aspect ratio from image bytes."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        width, height = image.size
        
        # Calculate GCD to get the simplest ratio
        def gcd(a, b):
            while b:
                a, b = b, a % b
            return a
        
        ratio_gcd = gcd(width, height)
        ratio_width = width // ratio_gcd
        ratio_height = height // ratio_gcd
        
        # Map to supported ratios (3:7 to 7:3 as per BFL.ai docs)
        supported_ratios = {
            "1:1": (1, 1), "4:3": (4, 3), "3:4": (3, 4),
            "16:9": (16, 9), "9:16": (9, 16), "21:9": (21, 9),
            "9:21": (9, 21), "3:2": (3, 2), "2:3": (2, 3),
            "7:3": (7, 3), "3:7": (3, 7)
        }
        
        # Find closest supported ratio
        current_ratio = ratio_width / ratio_height
        closest_ratio = "1:1"
        min_diff = float('inf')
        
        for ratio_str, (r_w, r_h) in supported_ratios.items():
            target_ratio = r_w / r_h
            diff = abs(current_ratio - target_ratio)
            if diff < min_diff:
                min_diff = diff
                closest_ratio = ratio_str
        
        logger.info(f"Original size: {width}x{height}, Calculated ratio: {ratio_width}:{ratio_height}, Using: {closest_ratio}")
        return closest_ratio
    except Exception as e:
        logger.error(f"Error calculating aspect ratio: {e}")
        return "1:1"  # Default fallback

async def process_image_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str, aspect_ratio: str) -> None:
    """Process the image editing with BFL.ai API."""
    try:
        input_image_base64 = context.user_data["photo"]

        # Send processing message
        processing_msg = await update.message.reply_text(
            f"🎨 Editing your image...\n"
            f"📝 Prompt: {prompt}\n"
            f"📐 Aspect ratio: {aspect_ratio}\n\n"
            f"⏳ This may take 10-30 seconds..."
        )

        # BFL.ai API call to create request
        url = "https://api.bfl.ai/v1/flux-kontext-pro"
        headers = {
            "accept": "application/json",
            "x-key": BFL_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "prompt": prompt,
            "input_image": input_image_base64,
            "aspect_ratio": aspect_ratio,
            "output_format": "jpeg",
            "safety_tolerance": 2
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        response_data = response.json()

        polling_url = response_data.get("polling_url")
        request_id = response_data.get("id")

        if not polling_url:
            await processing_msg.edit_text("❌ Error: Could not get polling URL from BFL.ai.")
            logger.error(f"BFL.ai API response missing polling_url: {response_data}")
            return

        logger.info(f"Started image editing request {request_id}")

        # Poll for result
        max_polls = 60  # Maximum 2 minutes of polling
        poll_count = 0
        
        while poll_count < max_polls:
            time.sleep(2)  # Poll every 2 seconds
            poll_count += 1
            
            result_response = requests.get(polling_url, headers=headers)
            result_response.raise_for_status()
            result_data = result_response.json()

            status = result_data.get("status")
            logger.info(f"Polling status for {request_id}: {status} (poll #{poll_count})")

            if status == "Ready":
                edited_image_url = result_data.get("result", {}).get("sample")
                if edited_image_url:
                    # Download and send the edited image
                    image_response = requests.get(edited_image_url)
                    image_response.raise_for_status()
                    
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=io.BytesIO(image_response.content),
                        caption=f"✨ **Edited Image**\n📝 Prompt: {prompt}"
                    )
                    await processing_msg.delete()
                    
                    # Keep the image for potential further edits
                    await update.message.reply_text(
                        "🔄 You can send another editing instruction for this image, "
                        "or send a new image to start over!"
                    )
                    return
                else:
                    await processing_msg.edit_text("❌ Error: No edited image URL received.")
                    return
                    
            elif status in ["Error", "Failed"]:
                error_msg = result_data.get("failure_reason", "Unknown error")
                await processing_msg.edit_text(f"❌ Image editing failed: {error_msg}")
                logger.error(f"BFL.ai request {request_id} failed: {result_data}")
                return
            elif status == "Pending":
                # Update progress message every 10 polls
                if poll_count % 10 == 0:
                    await processing_msg.edit_text(
                        f"🎨 Still editing your image...\n"
                        f"📝 Prompt: {prompt}\n"
                        f"⏳ Elapsed time: {poll_count * 2} seconds"
                    )

        # Timeout reached
        await processing_msg.edit_text(
            "⏰ Request timed out. The image editing is taking longer than expected. "
            "Please try again with a simpler prompt."
        )

    except requests.exceptions.RequestException as e:
        logger.error(f"API request error: {e}")
        await update.message.reply_text("❌ Network error. Please try again later.")
    except Exception as e:
        logger.error(f"Unexpected error in process_image_edit: {e}")
        await update.message.reply_text("❌ An unexpected error occurred. Please try again.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    welcome_message = f"""
🎨 **AI Image Editor Bot**

Hi {user.mention_html()}!

**Two ways to use:**

**Method 1** (Quick): Send photo with caption
📷➕📝 Attach your edit instruction as photo caption

**Method 2** (Step-by-step):
1. Send me an image
2. Send a text description of how you want to edit it

**Examples:**
• "Change the car color to red"
• "Add sunglasses to the person"  
• "Make the sky sunset colored"
• "Add text 'SALE' to the image"

The bot maintains your image's original aspect ratio!
    """
    await update.message.reply_html(
        welcome_message,
        reply_markup=ForceReply(selective=True),
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = """
🔧 **Bot Commands & Usage**

**Commands:**
• `/start` - Start the bot
• `/help` - Show this help message
• `/clear` - Clear current image from memory

**How to edit images:**

**Method 1**: Photo with caption
📷 Send photo with editing instruction as caption

**Method 2**: Step-by-step
1. Send a photo to the bot
2. Send your editing instruction as text
3. Wait for the AI to process your request

**Tips:**
• Be specific in your descriptions
• The bot maintains original aspect ratios
• Processing may take 10-30 seconds
• You can send a new image anytime

**Supported edits:**
• Color changes
• Object modifications  
• Adding/removing elements
• Text overlay
• Style changes
    """
    await update.message.reply_text(help_text)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear the stored image."""
    if "photo" in context.user_data:
        del context.user_data["photo"]
        if "aspect_ratio" in context.user_data:
            del context.user_data["aspect_ratio"]
        await update.message.reply_text("✅ Image cleared! Send a new image to start editing.")
    else:
        await update.message.reply_text("No image to clear. Send an image first!")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stores the photo and either uses caption or asks for a text prompt."""
    try:
        if not update.message.photo:
            await update.message.reply_text("❌ Please send a photo.")
            return

        # Check if photo has a caption (attached text)
        caption = update.message.caption
        
        await update.message.reply_text("📥 Processing your image...")

        # Get the largest photo
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytes()
        
        # Calculate aspect ratio
        aspect_ratio = get_aspect_ratio(photo_bytes)
        
        # Store photo and aspect ratio
        context.user_data["photo"] = base64.b64encode(photo_bytes).decode("utf-8")
        context.user_data["aspect_ratio"] = aspect_ratio
        
        if caption and caption.strip():
            # Photo has caption - use it as editing prompt immediately
            await update.message.reply_text(
                f"✅ Image received with caption!\n"
                f"📐 Detected aspect ratio: {aspect_ratio}\n"
                f"📝 Using caption as prompt: \"{caption}\"\n\n"
                f"🎨 Starting edit..."
            )
            # Process the edit immediately using the caption
            await process_image_edit(update, context, caption.strip(), aspect_ratio)
        else:
            # No caption - ask for text prompt
            await update.message.reply_text(
                f"✅ Image received! \n"
                f"📐 Detected aspect ratio: {aspect_ratio}\n\n"
                f"💬 Now send me your editing instructions!"
            )
            
    except Exception as e:
        logger.error(f"Error handling photo: {e}")
        await update.message.reply_text("❌ Error processing the image. Please try again.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processes the text prompt and sends the image to BFL.ai for editing."""
    if "photo" not in context.user_data:
        await update.message.reply_text(
            "📷 Please send a photo first before sending editing instructions.\n"
            "Use /start to see how to use the bot."
        )
        return

    prompt = update.message.text
    aspect_ratio = context.user_data.get("aspect_ratio", "1:1")
    
    await process_image_edit(update, context, prompt, aspect_ratio)

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Run the bot
    logger.info("Starting Telegram BFL.ai Image Editor Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

