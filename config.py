"""
Configuration module for AI Trading Agent
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Zerodha API Configuration
    KITE_API_KEY = os.getenv('KITE_API_KEY')
    KITE_API_SECRET = os.getenv('KITE_API_SECRET')
    
    # Trading Configuration
    MAX_DAILY_BUDGET = float(os.getenv('MAX_DAILY_BUDGET', 10000))
    RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', 0.02))
    MAX_POSITIONS = int(os.getenv('MAX_POSITIONS', 5))
    
    # Market Configuration
    MARKET_OPEN_TIME = "09:15"
    MARKET_CLOSE_TIME = "15:30"
    SQUARE_OFF_TIME = "15:20"  # Square off 10 minutes before market close
    
    # Technical Analysis Parameters
    RSI_PERIOD = 14
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    
    EMA_FAST = 12
    EMA_SLOW = 26
    MACD_SIGNAL = 9
    
    BOLLINGER_PERIOD = 20
    BOLLINGER_STD = 2
    
    # Risk Management
    STOP_LOSS_PERCENT = 0.02  # 2% stop loss
    TAKE_PROFIT_PERCENT = 0.04  # 4% take profit
    MAX_DAILY_LOSS = MAX_DAILY_BUDGET * 0.05  # 5% of daily budget
    
    # Dynamic Stock Universe Configuration
    # Exchanges to scan for stocks
    EXCHANGES = ['NSE', 'BSE']
    
    # Stock Filtering Criteria
    MIN_MARKET_CAP = float(os.getenv('MIN_MARKET_CAP', 100))  # Minimum market cap in crores
    MIN_AVG_VOLUME = int(os.getenv('MIN_AVG_VOLUME', 100000))  # Minimum average daily volume
    MIN_PRICE = float(os.getenv('MIN_PRICE', 10))  # Minimum stock price
    MAX_PRICE = float(os.getenv('MAX_PRICE', 10000))  # Maximum stock price
    
    # Stock Categories to Include
    INCLUDE_STOCK_CATEGORIES = [
        'EQ',  # Equity shares
        'BE',  # Book closure
        'BZ',  # Z category securities
    ]
    
    # Stock Categories to Exclude (penny stocks, illiquid stocks, etc.)
    EXCLUDE_STOCK_CATEGORIES = [
        'IL',  # Illiquid stocks
        'GS',  # Government securities
        'BC',  # Book closure
        'SM',  # SME stocks (unless specifically wanted)
    ]
    
    # Screening Parameters
    MAX_STOCKS_TO_ANALYZE = int(os.getenv('MAX_STOCKS_TO_ANALYZE', 500))  # Limit for performance
    TOP_PERFORMERS_COUNT = int(os.getenv('TOP_PERFORMERS_COUNT', 50))  # Top stocks to analyze deeply
    
    # Volume-based filtering (for intraday liquidity)
    MIN_VOLUME_MULTIPLIER = 1.5  # Stock must have >1.5x avg volume today
    
    # Sectors to focus on (optional filter)
    FOCUS_SECTORS = os.getenv('FOCUS_SECTORS', '').split(',') if os.getenv('FOCUS_SECTORS') else []
    
    # Fallback stocks (if dynamic screening fails)
    FALLBACK_STOCKS = [
        'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK',
        'KOTAKBANK', 'SBIN', 'BHARTIARTL', 'ITC', 'LT'
    ]
    
    # Telegram Configuration (Optional)
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    
    # Logging Configuration
    LOG_LEVEL = "INFO"
    LOG_FILE = "trading_agent.log"
    
    @classmethod
    def validate_config(cls):
        """Validate that all required configuration is present"""
        if not cls.KITE_API_KEY:
            raise ValueError("KITE_API_KEY is required")
        if not cls.KITE_API_SECRET:
            raise ValueError("KITE_API_SECRET is required")
        
        print("✅ Configuration validated successfully")
        return True 