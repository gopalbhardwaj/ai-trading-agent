"""
Setup script for AI Trading Agent
"""
import os
import shutil
from pathlib import Path

def create_env_file():
    """Create .env file from template"""
    env_content = """# Zerodha Kite API Configuration
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here

# Trading Configuration
MAX_DAILY_BUDGET=10000
RISK_PER_TRADE=0.02
MAX_POSITIONS=5

# Optional: Telegram Bot for notifications
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Market Data Configuration
USE_LIVE_DATA=true
"""
    
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write(env_content)
        print("✅ Created .env file")
        print("⚠️  Please update .env file with your actual API credentials")
    else:
        print("ℹ️  .env file already exists")

def create_directories():
    """Create necessary directories"""
    directories = ['logs', 'data', 'backups']
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✅ Created {directory}/ directory")

def setup_logging():
    """Setup logging configuration"""
    log_config = """[loggers]
keys=root,trading

[handlers]
keys=fileHandler,consoleHandler

[formatters]
keys=defaultFormatter

[logger_root]
level=INFO
handlers=fileHandler,consoleHandler

[logger_trading]
level=INFO
handlers=fileHandler,consoleHandler
qualname=trading
propagate=0

[handler_fileHandler]
class=FileHandler
level=INFO
formatter=defaultFormatter
args=('logs/trading_agent.log', 'a')

[handler_consoleHandler]
class=StreamHandler
level=INFO
formatter=defaultFormatter
args=(sys.stdout,)

[formatter_defaultFormatter]
format=%(asctime)s - %(name)s - %(levelname)s - %(message)s
datefmt=%Y-%m-%d %H:%M:%S
"""
    
    if not os.path.exists('logging.conf'):
        with open('logging.conf', 'w') as f:
            f.write(log_config)
        print("✅ Created logging configuration")

def print_instructions():
    """Print setup instructions"""
    instructions = """
🤖 AI Trading Agent Setup Complete!

📋 Next Steps:

1. 🔑 Get Zerodha API Credentials:
   • Visit: https://developers.kite.trade/
   • Create a new app
   • Set redirect URL: http://localhost:5000/callback
   • Note down your API Key and Secret

2. ⚙️ Configure Environment:
   • Edit .env file with your API credentials
   • Adjust trading parameters as needed

3. 🚀 Run the Trading Agent:
   • CLI Version: python main.py
   • Dashboard: streamlit run dashboard.py

4. 📊 Monitor Performance:
   • Check logs in logs/trading_agent.log
   • Use the Streamlit dashboard for real-time monitoring

⚠️  IMPORTANT REMINDERS:
• This system trades real money - use at your own risk
• Start with small amounts to test the system
• Ensure you have sufficient margin in your account
• The system will auto square-off positions before market close

🛡️ Safety Features:
• Daily loss limits
• Position size limits
• Automatic stop losses
• Emergency square-off functionality

📚 Documentation:
• Read README.md for detailed instructions
• Check config.py for all configurable parameters

Good luck with your automated trading! 🎯
"""
    print(instructions)

def main():
    """Main setup function"""
    print("🚀 Setting up AI Trading Agent...\n")
    
    try:
        create_directories()
        create_env_file()
        setup_logging()
        
        print("\n✅ Setup completed successfully!")
        print_instructions()
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")

if __name__ == "__main__":
    main() 