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
        """Load and cache instrument data from all configured exchanges"""
        try:
            all_instruments = []
            
            # Load instruments from all exchanges
            for exchange in Config.EXCHANGES:
                try:
                    instruments = self.zerodha_client.get_instruments(exchange)
                    logger.info(f"📊 Loaded {len(instruments)} instruments from {exchange}")
                    all_instruments.extend(instruments)
                except Exception as e:
                    logger.error(f"Failed to load instruments from {exchange}: {e}")
            
            # Apply filtering criteria
            filtered_instruments = self._filter_instruments(all_instruments)
            
            # Cache filtered instruments
            for instrument in filtered_instruments:
                symbol = instrument['tradingsymbol']
                self.instruments_cache[symbol] = instrument
            
            logger.info(f"✅ Filtered and loaded {len(self.instruments_cache)} tradeable instruments")
            
        except Exception as e:
            logger.error(f"Failed to load instruments: {e}")
            # Fallback to default stocks
            logger.info("📋 Using fallback stock list")
            for symbol in Config.FALLBACK_STOCKS:
                self.instruments_cache[symbol] = {'tradingsymbol': symbol, 'exchange': 'NSE'}
    
    def _filter_instruments(self, instruments: List[Dict]) -> List[Dict]:
        """Apply filtering criteria to instruments"""
        filtered = []
        
        for instrument in instruments:
            try:
                # Basic filtering
                if not self._is_eligible_instrument(instrument):
                    continue
                
                # Price filtering (if available)
                if 'last_price' in instrument:
                    price = float(instrument['last_price'])
                    if price < Config.MIN_PRICE or price > Config.MAX_PRICE:
                        continue
                
                filtered.append(instrument)
                
            except Exception as e:
                continue
        
        # Limit the number of instruments for performance
        if len(filtered) > Config.MAX_STOCKS_TO_ANALYZE:
            # Sort by some criteria (volume, market cap, etc.)
            filtered = sorted(filtered, key=lambda x: x.get('volume', 0), reverse=True)
            filtered = filtered[:Config.MAX_STOCKS_TO_ANALYZE]
            logger.info(f"📊 Limited to top {Config.MAX_STOCKS_TO_ANALYZE} stocks by volume")
        
        return filtered
    
    def _is_eligible_instrument(self, instrument: Dict) -> bool:
        """Check if an instrument is eligible for trading"""
        try:
            # Check instrument type
            instrument_type = instrument.get('instrument_type', '')
            if instrument_type != 'EQ':  # Only equity shares
                return False
            
            # Check segment
            segment = instrument.get('segment', '')
            if segment not in ['NSE', 'BSE', 'NFO-OPT', 'NFO-FUT']:
                return False
            
            # Check if it's a valid equity symbol (no special characters that indicate derivatives)
            symbol = instrument.get('tradingsymbol', '')
            if not symbol or len(symbol) < 2:
                return False
            
            # Exclude derivatives and complex instruments
            if any(x in symbol for x in ['-', 'FUT', 'CE', 'PE', 'CALL', 'PUT']):
                return False
            
            # Check lot size (should be 1 for equity)
            lot_size = instrument.get('lot_size', 1)
            if lot_size != 1:
                return False
            
            return True
            
        except Exception:
            return False
    
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
        
        logger.info("🔍 Starting comprehensive stock screening...")
        logger.info(f"📊 Analyzing {len(self.instruments_cache)} stocks from NSE/BSE")
        
        # Step 1: Pre-screening for performance
        promising_stocks = self._pre_screen_stocks()
        logger.info(f"🎯 Pre-screening identified {len(promising_stocks)} promising stocks")
        
        # Step 2: Detailed analysis of promising stocks
        analyzed_count = 0
        for symbol in promising_stocks:
            try:
                signal_data = self.generate_signals(symbol)
                if signal_data['signal'] != 'HOLD' and signal_data['strength'] > 0.4:
                    signal_data['symbol'] = symbol
                    signals.append(signal_data)
                    
                    logger.info(f"📈 {symbol}: {signal_data['signal']} "
                              f"(Strength: {signal_data['strength']:.2f}) - "
                              f"{', '.join(signal_data['reasons'][:2])}")
                
                analyzed_count += 1
                
                # Progress logging
                if analyzed_count % 50 == 0:
                    logger.info(f"📊 Analyzed {analyzed_count}/{len(promising_stocks)} stocks...")
                
            except Exception as e:
                logger.error(f"Failed to analyze {symbol}: {e}")
                continue
        
        # Sort by signal strength
        signals.sort(key=lambda x: x['strength'], reverse=True)
        
        logger.info(f"✅ Found {len(signals)} trading opportunities from {analyzed_count} analyzed stocks")
        return signals[:Config.TOP_PERFORMERS_COUNT]  # Return top performers
    
    def _pre_screen_stocks(self) -> List[str]:
        """
        Pre-screen stocks based on basic criteria for performance
        Returns list of promising symbols for detailed analysis
        """
        promising = []
        
        logger.info("🔍 Pre-screening stocks for volume and momentum...")
        
        for symbol, instrument in self.instruments_cache.items():
            try:
                # Get basic stock data for pre-screening
                df = self.get_stock_data(symbol, period="2d", interval="5m")
                if df is None or len(df) < 20:
                    continue
                
                # Volume analysis
                if not self._has_sufficient_volume(df):
                    continue
                
                # Price movement analysis
                if not self._has_significant_movement(df):
                    continue
                
                # Volatility check (not too volatile, not too stable)
                if not self._has_appropriate_volatility(df):
                    continue
                
                promising.append(symbol)
                
            except Exception as e:
                continue
        
        # Limit to top stocks if too many
        if len(promising) > Config.TOP_PERFORMERS_COUNT * 2:
            # Get additional data for ranking
            ranked_stocks = self._rank_stocks_by_potential(promising)
            promising = ranked_stocks[:Config.TOP_PERFORMERS_COUNT * 2]
        
        return promising
    
    def _has_sufficient_volume(self, df: pd.DataFrame) -> bool:
        """Check if stock has sufficient volume for intraday trading"""
        try:
            recent_volume = df['volume'].tail(10).mean()
            avg_volume = df['volume'].mean()
            
            # Must have minimum volume and recent volume spike
            return (recent_volume > Config.MIN_AVG_VOLUME and 
                   recent_volume >= avg_volume * Config.MIN_VOLUME_MULTIPLIER)
        except:
            return False
    
    def _has_significant_movement(self, df: pd.DataFrame) -> bool:
        """Check if stock has significant price movement for intraday potential"""
        try:
            latest_price = df['close'].iloc[-1]
            prev_price = df['close'].iloc[-10] if len(df) > 10 else df['close'].iloc[0]
            
            price_change = abs((latest_price - prev_price) / prev_price)
            
            # Look for 0.5% to 8% movement (not too little, not too much)
            return 0.005 <= price_change <= 0.08
        except:
            return False
    
    def _has_appropriate_volatility(self, df: pd.DataFrame) -> bool:
        """Check if stock has appropriate volatility for intraday trading"""
        try:
            # Calculate recent volatility
            df['returns'] = df['close'].pct_change()
            volatility = df['returns'].tail(20).std()
            
            # Look for moderate volatility (0.1% to 5% standard deviation)
            return 0.001 <= volatility <= 0.05
        except:
            return False
    
    def _rank_stocks_by_potential(self, symbols: List[str]) -> List[str]:
        """Rank stocks by their intraday potential"""
        ranked = []
        
        for symbol in symbols:
            try:
                df = self.get_stock_data(symbol, period="1d", interval="5m")
                if df is None or len(df) < 10:
                    continue
                
                # Calculate potential score
                score = self._calculate_potential_score(df)
                ranked.append((symbol, score))
                
            except:
                continue
        
        # Sort by score and return symbols
        ranked.sort(key=lambda x: x[1], reverse=True)
        return [symbol for symbol, score in ranked]
    
    def _calculate_potential_score(self, df: pd.DataFrame) -> float:
        """Calculate a potential score for intraday trading"""
        try:
            score = 0.0
            
            # Volume score (30%)
            volume_ratio = df['volume'].tail(5).mean() / df['volume'].mean()
            score += min(volume_ratio / 2, 1.0) * 0.3
            
            # Volatility score (25%)
            df['returns'] = df['close'].pct_change()
            volatility = df['returns'].tail(10).std()
            volatility_score = min(volatility * 50, 1.0)  # Normalize
            score += volatility_score * 0.25
            
            # Trend strength score (25%)
            price_momentum = (df['close'].iloc[-1] - df['close'].iloc[-10]) / df['close'].iloc[-10]
            momentum_score = min(abs(price_momentum) * 10, 1.0)
            score += momentum_score * 0.25
            
            # Range score (20%)
            high_low_range = (df['high'].max() - df['low'].min()) / df['close'].mean()
            range_score = min(high_low_range * 20, 1.0)
            score += range_score * 0.20
            
            return score
            
        except:
            return 0.0
    
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