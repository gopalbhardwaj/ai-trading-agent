"""
Market Analysis Module for Technical Indicators and Signal Generation
"""
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import ta
from config import Config

logger = logging.getLogger(__name__)

class MarketAnalyzer:
    def __init__(self, zerodha_client):
        self.zerodha_client = zerodha_client
        self.instruments_cache = {}
        
        # Initialize instruments on creation
        logger.info("🔧 Initializing MarketAnalyzer with real Zerodha data...")
        self._load_instruments()
    
    def _load_instruments(self):
        """Load and cache instrument data from all configured exchanges"""
        try:
            all_instruments = []
            
            # Load instruments from all exchanges
            for exchange in Config.EXCHANGES:
                try:
                    logger.info(f"📊 Loading instruments from {exchange}...")
                    instruments = self.zerodha_client.get_instruments(exchange)
                    logger.info(f"✅ Loaded {len(instruments)} instruments from {exchange}")
                    all_instruments.extend(instruments)
                except Exception as e:
                    logger.error(f"Failed to load instruments from {exchange}: {e}")
            
            if not all_instruments:
                logger.warning("⚠️ No instruments loaded from exchanges, using fallback stocks")
                # Use fallback but still try to get their instrument tokens
                for symbol in Config.FALLBACK_STOCKS:
                    self.instruments_cache[symbol] = {
                        'tradingsymbol': symbol, 
                        'exchange': 'NSE',
                        'instrument_token': symbol  # Will be resolved later
                    }
                return
            
            # Apply filtering criteria
            filtered_instruments = self._filter_instruments(all_instruments)
            
            # Cache filtered instruments
            for instrument in filtered_instruments:
                symbol = instrument['tradingsymbol']
                self.instruments_cache[symbol] = instrument
            
            logger.info(f"✅ Filtered and loaded {len(self.instruments_cache)} tradeable instruments")
            
            # Log some examples
            if self.instruments_cache:
                examples = list(self.instruments_cache.keys())[:5]
                logger.info(f"📈 Example instruments: {', '.join(examples)}")
            
        except Exception as e:
            logger.error(f"Failed to load instruments: {e}")
            # Fallback to default stocks
            logger.info("📋 Using fallback stock list due to error")
            for symbol in Config.FALLBACK_STOCKS:
                self.instruments_cache[symbol] = {
                    'tradingsymbol': symbol, 
                    'exchange': 'NSE',
                    'instrument_token': symbol
                }
    
    def _filter_instruments(self, instruments: List[Dict]) -> List[Dict]:
        """Apply filtering criteria to instruments"""
        filtered = []
        
        for instrument in instruments:
            if self._is_eligible_instrument(instrument):
                filtered.append(instrument)
                
                # Stop if we have enough instruments for performance
                if len(filtered) >= Config.MAX_STOCKS_TO_ANALYZE:
                    break
        
        logger.info(f"📊 Filtered {len(filtered)} eligible instruments from {len(instruments)} total")
        return filtered
    
    def _is_eligible_instrument(self, instrument: Dict) -> bool:
        """Check if instrument meets our trading criteria"""
        try:
            # Basic checks
            if 'tradingsymbol' not in instrument:
                return False
            
            symbol = instrument['tradingsymbol']
            
            # Skip derivatives, futures, options
            if any(suffix in symbol for suffix in ['-EQ', 'FUT', 'CE', 'PE', 'BANK']):
                return False
            
            # Check segment/instrument type
            segment = instrument.get('segment', '').upper()
            if segment not in ['NSE', 'BSE', 'NSE-EQ', 'BSE-EQ']:
                return False
            
            # Check exchange
            exchange = instrument.get('exchange', '').upper()
            if exchange not in ['NSE', 'BSE']:
                return False
            
            # Additional filtering can be added here
            
            return True
            
        except Exception as e:
            logger.debug(f"Error checking instrument {instrument}: {e}")
            return False
    
    def get_real_time_price(self, symbol: str) -> Optional[float]:
        """Get real-time price from Zerodha API"""
        try:
            # Try to get instrument token
            instrument_info = self.instruments_cache.get(symbol)
            if not instrument_info:
                logger.warning(f"Instrument not found in cache: {symbol}")
                return None
            
            # Get quote using Zerodha API
            exchange = instrument_info.get('exchange', 'NSE')
            instrument_key = f"{exchange}:{symbol}"
            
            quotes = self.zerodha_client.get_quote([instrument_key])
            
            if quotes and instrument_key in quotes:
                quote_data = quotes[instrument_key]
                ltp = quote_data.get('last_price', 0)
                logger.debug(f"📊 Real-time price for {symbol}: ₹{ltp}")
                return float(ltp) if ltp else None
            else:
                logger.warning(f"No quote data for {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get real-time price for {symbol}: {e}")
            return None
    
    def get_stock_data(self, symbol: str, period: str = "5d", interval: str = "5m") -> Optional[pd.DataFrame]:
        """
        Get stock data from Zerodha historical data API
        """
        try:
            # Get instrument info
            instrument_info = self.instruments_cache.get(symbol)
            if not instrument_info:
                logger.warning(f"Instrument not found: {symbol}")
                return None
            
            # Get instrument token
            instrument_token = instrument_info.get('instrument_token')
            if not instrument_token:
                logger.warning(f"No instrument token for {symbol}")
                return None
            
            # Calculate date range
            end_date = datetime.now()
            
            # Convert period to days
            if period == "1d":
                days = 1
            elif period == "5d":
                days = 5
            elif period == "1mo":
                days = 30
            else:
                days = 5  # Default
            
            start_date = end_date - timedelta(days=days)
            
            # Get historical data from Zerodha
            logger.debug(f"📊 Fetching {days}d historical data for {symbol}...")
            historical_data = self.zerodha_client.get_historical_data(
                instrument_token=instrument_token,
                from_date=start_date,
                to_date=end_date,
                interval=interval
            )
            
            if not historical_data:
                logger.warning(f"No historical data for {symbol}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(historical_data)
            
            if df.empty:
                logger.warning(f"Empty historical data for {symbol}")
                return None
            
            # Standardize column names
            df.columns = [col.lower() for col in df.columns]
            
            # Ensure we have the required columns
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                if col not in df.columns:
                    logger.warning(f"Missing column {col} for {symbol}")
                    return None
            
            logger.debug(f"✅ Got {len(df)} candles for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Failed to get historical data for {symbol}: {e}")
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
        Generate trading signals for a specific stock using real market data
        """
        try:
            logger.debug(f"🔍 Analyzing {symbol} for trading signals...")
            
            # Get real-time price first
            current_price = self.get_real_time_price(symbol)
            if not current_price:
                logger.warning(f"❌ Could not get real-time price for {symbol}")
                return {'signal': 'HOLD', 'strength': 0, 'reasons': ['No real-time price available']}
            
            logger.debug(f"💰 Current price for {symbol}: ₹{current_price}")
            
            # Get historical data for technical analysis
            df = self.get_stock_data(symbol, period="5d", interval="5m")
            if df is None or df.empty:
                logger.warning(f"❌ No historical data for {symbol}")
                return {'signal': 'HOLD', 'strength': 0, 'reasons': ['No historical data available']}
            
            # Calculate technical indicators
            df_with_indicators = self.calculate_technical_indicators(df)
            if df_with_indicators is None or df_with_indicators.empty:
                logger.warning(f"❌ Failed to calculate indicators for {symbol}")
                return {'signal': 'HOLD', 'strength': 0, 'reasons': ['Technical indicators calculation failed']}
            
            # Get latest values
            latest = df_with_indicators.iloc[-1]
            
            # Extract indicator values
            rsi = latest.get('rsi', 50)
            macd = latest.get('macd', 0)
            macd_signal = latest.get('macd_signal', 0)
            bb_upper = latest.get('bb_upper', current_price * 1.02)
            bb_lower = latest.get('bb_lower', current_price * 0.98)
            ema_fast = latest.get('ema_fast', current_price)
            ema_slow = latest.get('ema_slow', current_price)
            volume = latest.get('volume', 0)
            
            # Calculate signals
            signals = []
            reasons = []
            signal_strength = 0
            
            # RSI signals
            if rsi < Config.RSI_OVERSOLD:
                signals.append('BUY')
                reasons.append(f'Oversold RSI ({rsi:.1f})')
                signal_strength += 0.3
            elif rsi > Config.RSI_OVERBOUGHT:
                signals.append('SELL')
                reasons.append(f'Overbought RSI ({rsi:.1f})')
                signal_strength += 0.3
            
            # MACD signals
            if macd > macd_signal and macd > 0:
                signals.append('BUY')
                reasons.append('Bullish MACD crossover')
                signal_strength += 0.25
            elif macd < macd_signal and macd < 0:
                signals.append('SELL')
                reasons.append('Bearish MACD crossover')
                signal_strength += 0.25
            
            # Bollinger Bands signals
            if current_price <= bb_lower:
                signals.append('BUY')
                reasons.append('Price at lower Bollinger Band')
                signal_strength += 0.2
            elif current_price >= bb_upper:
                signals.append('SELL')
                reasons.append('Price at upper Bollinger Band')
                signal_strength += 0.2
            
            # EMA trend signals
            if ema_fast > ema_slow and current_price > ema_fast:
                signals.append('BUY')
                reasons.append('Bullish EMA trend')
                signal_strength += 0.15
            elif ema_fast < ema_slow and current_price < ema_fast:
                signals.append('SELL')
                reasons.append('Bearish EMA trend')
                signal_strength += 0.15
            
            # Volume confirmation
            avg_volume = df['volume'].tail(20).mean() if len(df) >= 20 else volume
            if volume > avg_volume * 1.5:
                signal_strength += 0.1
                reasons.append('High volume confirmation')
            
            # Determine final signal
            buy_signals = signals.count('BUY')
            sell_signals = signals.count('SELL')
            
            if buy_signals > sell_signals and signal_strength > 0.4:
                final_signal = 'BUY'
            elif sell_signals > buy_signals and signal_strength > 0.4:
                final_signal = 'SELL'
            else:
                final_signal = 'HOLD'
                signal_strength = min(signal_strength, 0.3)  # Reduce strength for HOLD
            
            result = {
                'signal': final_signal,
                'strength': min(signal_strength, 1.0),  # Cap at 1.0
                'price': current_price,  # REAL current price
                'reasons': reasons[:3],  # Top 3 reasons
                'rsi': rsi,
                'macd': macd,
                'volume_ratio': volume / avg_volume if avg_volume > 0 else 1.0
            }
            
            logger.debug(f"📊 {symbol} Signal: {final_signal} (Strength: {signal_strength:.2f}, Price: ₹{current_price})")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error generating signals for {symbol}: {e}")
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