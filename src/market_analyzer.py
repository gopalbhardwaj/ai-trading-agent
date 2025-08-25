"""
Market Analysis Module for Technical Indicators and Signal Generation
"""
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import ta
import yfinance as yf

from config import Config

logger = logging.getLogger(__name__)

class MarketAnalyzer:
    def __init__(self, zerodha_client):
        self.zerodha_client = zerodha_client
        self.instruments_cache = {}
        self._load_instruments()
    
    def _load_instruments(self):
        """Load and cache instrument data"""
        try:
            instruments = self.zerodha_client.get_instruments("NSE")
            for instrument in instruments:
                symbol = instrument['tradingsymbol']
                if symbol in Config.STOCK_UNIVERSE:
                    self.instruments_cache[symbol] = instrument
            logger.info(f"✅ Loaded {len(self.instruments_cache)} instruments")
        except Exception as e:
            logger.error(f"Failed to load instruments: {e}")
    
    def get_stock_data(self, symbol: str, period: str = "5d", interval: str = "5m") -> Optional[pd.DataFrame]:
        """
        Get stock data from Yahoo Finance (fallback) or Zerodha
        """
        try:
            # Try Yahoo Finance first for historical data
            yf_symbol = f"{symbol}.NS"  # NSE suffix for Yahoo Finance
            stock = yf.Ticker(yf_symbol)
            data = stock.history(period=period, interval=interval)
            
            if data.empty:
                logger.warning(f"No data found for {symbol}")
                return None
            
            # Rename columns to standard format
            data.columns = [col.lower() for col in data.columns]
            data.reset_index(inplace=True)
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to get data for {symbol}: {e}")
            return None
    
    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate various technical indicators
        """
        try:
            # RSI
            df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=Config.RSI_PERIOD).rsi()
            
            # Moving Averages
            df['ema_fast'] = ta.trend.EMAIndicator(df['close'], window=Config.EMA_FAST).ema_indicator()
            df['ema_slow'] = ta.trend.EMAIndicator(df['close'], window=Config.EMA_SLOW).ema_indicator()
            df['sma_20'] = ta.trend.SMAIndicator(df['close'], window=20).sma_indicator()
            
            # MACD
            macd = ta.trend.MACD(df['close'], window_fast=Config.EMA_FAST, 
                               window_slow=Config.EMA_SLOW, window_sign=Config.MACD_SIGNAL)
            df['macd'] = macd.macd()
            df['macd_signal'] = macd.macd_signal()
            df['macd_histogram'] = macd.macd_diff()
            
            # Bollinger Bands
            bollinger = ta.volatility.BollingerBands(df['close'], window=Config.BOLLINGER_PERIOD, 
                                                   window_dev=Config.BOLLINGER_STD)
            df['bb_upper'] = bollinger.bollinger_hband()
            df['bb_middle'] = bollinger.bollinger_mavg()
            df['bb_lower'] = bollinger.bollinger_lband()
            
            # Volume indicators
            df['volume_sma'] = ta.volume.VolumeSMAIndicator(df['close'], df['volume'], window=20).volume_sma()
            
            # Support and Resistance
            df['support'] = df['low'].rolling(window=20).min()
            df['resistance'] = df['high'].rolling(window=20).max()
            
            # Average True Range (ATR) for volatility
            df['atr'] = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'], window=14).average_true_range()
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to calculate technical indicators: {e}")
            return df
    
    def generate_signals(self, symbol: str) -> Dict[str, any]:
        """
        Generate buy/sell signals for a stock
        Returns: {
            'signal': 'BUY'/'SELL'/'HOLD',
            'strength': 0-1,
            'reasons': [],
            'price': float,
            'stop_loss': float,
            'take_profit': float
        }
        """
        try:
            # Get stock data
            df = self.get_stock_data(symbol)
            if df is None or len(df) < 50:
                return {'signal': 'HOLD', 'strength': 0, 'reasons': ['Insufficient data']}
            
            # Calculate technical indicators
            df = self.calculate_technical_indicators(df)
            
            # Get latest values
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest
            
            signal_score = 0
            reasons = []
            current_price = latest['close']
            
            # RSI Analysis
            if latest['rsi'] < Config.RSI_OVERSOLD:
                signal_score += 0.2
                reasons.append(f"RSI oversold ({latest['rsi']:.2f})")
            elif latest['rsi'] > Config.RSI_OVERBOUGHT:
                signal_score -= 0.2
                reasons.append(f"RSI overbought ({latest['rsi']:.2f})")
            
            # EMA Crossover
            if latest['ema_fast'] > latest['ema_slow'] and prev['ema_fast'] <= prev['ema_slow']:
                signal_score += 0.3
                reasons.append("EMA bullish crossover")
            elif latest['ema_fast'] < latest['ema_slow'] and prev['ema_fast'] >= prev['ema_slow']:
                signal_score -= 0.3
                reasons.append("EMA bearish crossover")
            
            # MACD Analysis
            if latest['macd'] > latest['macd_signal'] and prev['macd'] <= prev['macd_signal']:
                signal_score += 0.2
                reasons.append("MACD bullish crossover")
            elif latest['macd'] < latest['macd_signal'] and prev['macd'] >= prev['macd_signal']:
                signal_score -= 0.2
                reasons.append("MACD bearish crossover")
            
            # Bollinger Bands
            if latest['close'] < latest['bb_lower']:
                signal_score += 0.15
                reasons.append("Price below lower Bollinger Band")
            elif latest['close'] > latest['bb_upper']:
                signal_score -= 0.15
                reasons.append("Price above upper Bollinger Band")
            
            # Volume Analysis
            if latest['volume'] > latest['volume_sma'] * 1.5:
                signal_score += 0.1 if signal_score > 0 else -0.1
                reasons.append("High volume confirmation")
            
            # Price momentum
            price_change = (latest['close'] - prev['close']) / prev['close']
            if price_change > 0.01:  # 1% positive momentum
                signal_score += 0.1
                reasons.append("Positive price momentum")
            elif price_change < -0.01:  # 1% negative momentum
                signal_score -= 0.1
                reasons.append("Negative price momentum")
            
            # Support/Resistance levels
            if latest['close'] > latest['resistance'] * 0.99:  # Near resistance
                signal_score -= 0.1
                reasons.append("Near resistance level")
            elif latest['close'] < latest['support'] * 1.01:  # Near support
                signal_score += 0.1
                reasons.append("Near support level")
            
            # Determine signal
            if signal_score >= 0.4:
                signal = 'BUY'
            elif signal_score <= -0.4:
                signal = 'SELL'
            else:
                signal = 'HOLD'
            
            # Calculate stop loss and take profit
            atr = latest['atr']
            if signal == 'BUY':
                stop_loss = current_price - (atr * 2)
                take_profit = current_price + (atr * 3)
            elif signal == 'SELL':
                stop_loss = current_price + (atr * 2)
                take_profit = current_price - (atr * 3)
            else:
                stop_loss = current_price
                take_profit = current_price
            
            return {
                'signal': signal,
                'strength': abs(signal_score),
                'reasons': reasons,
                'price': current_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'rsi': latest['rsi'],
                'volume_ratio': latest['volume'] / latest['volume_sma'] if latest['volume_sma'] > 0 else 1
            }
            
        except Exception as e:
            logger.error(f"Failed to generate signals for {symbol}: {e}")
            return {'signal': 'HOLD', 'strength': 0, 'reasons': ['Analysis failed']}
    
    def screen_stocks(self) -> List[Dict[str, any]]:
        """
        Screen all stocks in universe for trading opportunities
        Returns list of stocks with signals sorted by strength
        """
        signals = []
        
        logger.info("🔍 Screening stocks for opportunities...")
        
        for symbol in Config.STOCK_UNIVERSE:
            try:
                signal_data = self.generate_signals(symbol)
                if signal_data['signal'] != 'HOLD' and signal_data['strength'] > 0.4:
                    signal_data['symbol'] = symbol
                    signals.append(signal_data)
                    
                    logger.info(f"📊 {symbol}: {signal_data['signal']} "
                              f"(Strength: {signal_data['strength']:.2f}) - "
                              f"{', '.join(signal_data['reasons'][:2])}")
                
            except Exception as e:
                logger.error(f"Failed to analyze {symbol}: {e}")
                continue
        
        # Sort by signal strength
        signals.sort(key=lambda x: x['strength'], reverse=True)
        
        logger.info(f"✅ Found {len(signals)} trading opportunities")
        return signals
    
    def get_market_sentiment(self) -> Dict[str, any]:
        """
        Analyze overall market sentiment using index data
        """
        try:
            # Get Nifty 50 data
            nifty_data = self.get_stock_data("^NSEI", period="5d", interval="5m")
            
            if nifty_data is None or len(nifty_data) < 20:
                return {'sentiment': 'NEUTRAL', 'strength': 0.5}
            
            # Calculate indicators for Nifty
            nifty_data = self.calculate_technical_indicators(nifty_data)
            latest = nifty_data.iloc[-1]
            
            sentiment_score = 0.5  # Start neutral
            
            # RSI analysis
            if latest['rsi'] > 60:
                sentiment_score += 0.1
            elif latest['rsi'] < 40:
                sentiment_score -= 0.1
            
            # EMA trend
            if latest['ema_fast'] > latest['ema_slow']:
                sentiment_score += 0.2
            else:
                sentiment_score -= 0.2
            
            # MACD
            if latest['macd'] > latest['macd_signal']:
                sentiment_score += 0.1
            else:
                sentiment_score -= 0.1
            
            # Price momentum
            price_change = (latest['close'] - nifty_data.iloc[-5]['close']) / nifty_data.iloc[-5]['close']
            if price_change > 0.01:
                sentiment_score += 0.1
            elif price_change < -0.01:
                sentiment_score -= 0.1
            
            # Determine sentiment
            if sentiment_score > 0.6:
                sentiment = 'BULLISH'
            elif sentiment_score < 0.4:
                sentiment = 'BEARISH'
            else:
                sentiment = 'NEUTRAL'
            
            return {
                'sentiment': sentiment,
                'strength': sentiment_score,
                'nifty_price': latest['close'],
                'nifty_change': price_change * 100
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze market sentiment: {e}")
            return {'sentiment': 'NEUTRAL', 'strength': 0.5}
    
    def validate_signal(self, signal_data: Dict[str, any]) -> bool:
        """
        Additional validation for trading signals
        """
        try:
            # Check minimum signal strength
            if signal_data['strength'] < 0.4:
                return False
            
            # Check RSI extremes
            if signal_data.get('rsi', 50) > 80 or signal_data.get('rsi', 50) < 20:
                logger.warning(f"Extreme RSI level: {signal_data.get('rsi')}")
                return False
            
            # Check volume confirmation
            if signal_data.get('volume_ratio', 1) < 0.8:
                logger.warning("Low volume - signal may be weak")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Signal validation failed: {e}")
            return False 