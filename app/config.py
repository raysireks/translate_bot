import os

# telegram bot credentials
BOT_TOKEN = os.getenv('BOT_TOKEN')
ALLOWED_GROUP_ID = int(os.getenv('ALLOWED_GROUP_ID', 0))
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', 0))
WEBHOOK_PATH = os.getenv('WEBHOOK_PATH', '/webhook')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
RUN_MODE = os.getenv('RUN_MODE', 'webhook')  # Options: "webhook", "polling", "rest"

# poe API credentials
POE_API_KEY = os.getenv('POE_API_KEY')

# huggingface API credentials
HF_TOKEN = os.getenv('HF_TOKEN')

# Play.ht API credentials
PLAY_HT_USER_ID = os.getenv('PLAY_HT_USER_ID')
PLAY_HT_API_KEY = os.getenv('PLAY_HT_API_KEY')

# anthropic API credentials
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
