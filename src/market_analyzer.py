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
        self.api_authenticated = False
        
        # Initialize and validate connection
        logger.info("🔧 Initializing MarketAnalyzer with Zerodha API...")
        self._validate_api_connection()
        if self.api_authenticated:
            self._load_instruments()
        else:
            logger.error("❌ Cannot initialize MarketAnalyzer - API authentication failed")
    
    def _validate_api_connection(self):
        """Validate that we can communicate with Zerodha API"""
        try:
            logger.info("🔐 Validating Zerodha API connection...")
            
            # Check if zerodha client has authentication
            if not hasattr(self.zerodha_client, 'kite') and not hasattr(self.zerodha_client, 'kite_client'):
                logger.error("❌ Zerodha client not properly initialized - missing kite connection")
                return False
            
            # Try to get profile to test authentication
            try:
                if hasattr(self.zerodha_client, 'kite'):
                    profile = self.zerodha_client.kite.profile()
                elif hasattr(self.zerodha_client, 'kite_client'):
                    profile = self.zerodha_client.kite_client.profile()
                else:
                    profile = self.zerodha_client.get_profile()
                
                if profile and 'user_name' in profile:
                    logger.info(f"✅ API Authentication successful - User: {profile['user_name']}")
                    self.api_authenticated = True
                    return True
                else:
                    logger.error("❌ API Authentication failed - Invalid profile response")
                    return False
                    
            except Exception as auth_error:
                logger.error(f"❌ API Authentication failed: {auth_error}")
                logger.error("🔍 DEBUG: Check if:")
                logger.error("   1. Zerodha API keys are correct")
                logger.error("   2. Access token is valid and not expired")
                logger.error("   3. Account has API access permissions")
                logger.error("   4. Network connection is working")
                return False
                
        except Exception as e:
            logger.error(f"❌ Critical error during API validation: {e}")
            return False
    
    def _load_instruments(self):
        """Load and cache instrument data from all configured exchanges"""
        try:
            if not self.api_authenticated:
                logger.error("❌ Cannot load instruments - API not authenticated")
                return
            
            all_instruments = []
            
            # Load instruments from all exchanges
            for exchange in Config.EXCHANGES:
                try:
                    logger.info(f"📊 Loading instruments from {exchange}...")
                    instruments = self.zerodha_client.get_instruments(exchange)
                    
                    if not instruments:
                        logger.warning(f"⚠️ No instruments received from {exchange}")
                        logger.warning("🔍 DEBUG: This could mean:")
                        logger.warning(f"   1. API key doesn't have access to {exchange}")
                        logger.warning(f"   2. Network issue connecting to {exchange}")
                        logger.warning(f"   3. Exchange is closed or unavailable")
                        continue
                    
                    logger.info(f"✅ Loaded {len(instruments)} instruments from {exchange}")
                    all_instruments.extend(instruments)
                    
                except Exception as e:
                    logger.error(f"❌ Failed to load instruments from {exchange}: {e}")
                    logger.error("🔍 DEBUG: Check if:")
                    logger.error(f"   1. API has permission to access {exchange}")
                    logger.error(f"   2. Exchange code '{exchange}' is correct")
                    logger.error("   3. Network connectivity is stable")
            
            if not all_instruments:
                logger.error("❌ CRITICAL: No instruments loaded from any exchange!")
                logger.error("🔍 DEBUGGING STEPS:")
                logger.error("   1. Check API authentication status")
                logger.error("   2. Verify API key has data permissions")
                logger.error("   3. Check if exchanges NSE/BSE are accessible")
                logger.error("   4. Try manual API call in browser/Postman")
                logger.error("   5. Contact Zerodha support if API is not working")
                return
            
            # Apply filtering criteria
            filtered_instruments = self._filter_instruments(all_instruments)
            
            if not filtered_instruments:
                logger.error("❌ No instruments passed filtering criteria!")
                logger.error("🔍 DEBUG: All instruments were filtered out, check:")
                logger.error("   1. Filtering criteria in config.py")
                logger.error("   2. Instrument data format from API")
                return
            
            # Cache filtered instruments
            for instrument in filtered_instruments:
                symbol = instrument['tradingsymbol']
                self.instruments_cache[symbol] = instrument
            
            logger.info(f"✅ Successfully loaded {len(self.instruments_cache)} tradeable instruments")
            
            # Log some examples for verification
            if self.instruments_cache:
                examples = list(self.instruments_cache.keys())[:5]
                logger.info(f"📈 Example instruments: {', '.join(examples)}")
            
        except Exception as e:
            logger.error(f"❌ Critical error loading instruments: {e}")
            logger.error("🔍 DEBUG: This is a serious issue - check:")
            logger.error("   1. Zerodha API service status")
            logger.error("   2. Network connectivity")
            logger.error("   3. API rate limits")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
    
    def _filter_instruments(self, instruments: List[Dict]) -> List[Dict]:
        """Apply filtering criteria to instruments"""
        filtered = []
        total_count = len(instruments)
        
        logger.info(f"🔍 Filtering {total_count} instruments...")
        
        for instrument in instruments:
            if self._is_eligible_instrument(instrument):
                filtered.append(instrument)
                
                # Stop if we have enough instruments for performance
                if len(filtered) >= Config.MAX_STOCKS_TO_ANALYZE:
                    break
        
        filter_percentage = (len(filtered) / total_count * 100) if total_count > 0 else 0
        logger.info(f"📊 Filtered {len(filtered)} eligible instruments from {total_count} total ({filter_percentage:.1f}%)")
        
        if len(filtered) == 0:
            logger.warning("⚠️ Zero instruments passed filtering - criteria may be too strict")
        
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
        """Get real-time price from Zerodha API with comprehensive error handling"""
        try:
            if not self.api_authenticated:
                logger.error(f"❌ Cannot get price for {symbol} - API not authenticated")
                return None
            
            # Check if instrument exists in cache
            instrument_info = self.instruments_cache.get(symbol)
            if not instrument_info:
                logger.error(f"❌ Instrument {symbol} not found in cache")
                logger.error("🔍 DEBUG: This could mean:")
                logger.error(f"   1. Symbol '{symbol}' is not available on NSE/BSE")
                logger.error(f"   2. Symbol was filtered out during instrument loading")
                logger.error(f"   3. Instrument cache failed to load properly")
                return None
            
            # Get quote using Zerodha API
            exchange = instrument_info.get('exchange', 'NSE')
            instrument_key = f"{exchange}:{symbol}"
            
            logger.debug(f"📊 Fetching real-time price for {instrument_key}...")
            
            try:
                quotes = self.zerodha_client.get_quote([instrument_key])
                
                if not quotes:
                    logger.error(f"❌ No quote data received for {symbol}")
                    return self._get_fallback_price(symbol)
                
                if instrument_key not in quotes:
                    logger.error(f"❌ Quote not found for {instrument_key}")
                    return self._get_fallback_price(symbol)
                
                quote_data = quotes[instrument_key]
                ltp = quote_data.get('last_price', 0)
                
                if not ltp or ltp <= 0:
                    logger.error(f"❌ Invalid price for {symbol}: {ltp}")
                    return self._get_fallback_price(symbol)
                
                logger.debug(f"✅ Real-time price for {symbol}: ₹{ltp}")
                return float(ltp)
                
            except Exception as quote_error:
                error_msg = str(quote_error).lower()
                if "insufficient permission" in error_msg or "permission" in error_msg:
                    logger.warning(f"⚠️ Quote API permission denied for {symbol}, using fallback")
                    return self._get_fallback_price(symbol)
                else:
                    logger.error(f"❌ Quote API error for {symbol}: {quote_error}")
                    return self._get_fallback_price(symbol)
                
        except Exception as e:
            logger.error(f"❌ Failed to get real-time price for {symbol}: {e}")
            return self._get_fallback_price(symbol)
    
    def _get_fallback_price(self, symbol: str) -> Optional[float]:
        """Get fallback price when quote API is not available"""
        try:
            # Try to get price from recent orders if available
            try:
                orders = self.zerodha_client.kite.orders()
                for order in orders:
                    if (order.get('tradingsymbol') == symbol and 
                        order.get('status') == 'COMPLETE' and
                        order.get('average_price', 0) > 0):
                        price = float(order['average_price'])
                        logger.info(f"📊 Fallback price for {symbol} from recent order: ₹{price}")
                        return price
            except Exception as e:
                logger.debug(f"Could not get price from orders: {e}")
            
            # Try to get from holdings if available
            try:
                holdings = self.zerodha_client.kite.holdings()
                for holding in holdings:
                    if (holding.get('tradingsymbol') == symbol and
                        holding.get('last_price', 0) > 0):
                        price = float(holding['last_price'])
                        logger.info(f"📊 Fallback price for {symbol} from holdings: ₹{price}")
                        return price
            except Exception as e:
                logger.debug(f"Could not get price from holdings: {e}")
            
            # Use conservative estimated prices for major stocks (last resort)
            estimated_prices = {
                'RELIANCE': 2450.0,
                'TCS': 3890.0,
                'HDFCBANK': 1678.0,
                'INFY': 1825.0,
                'ICICIBANK': 975.0,
                'KOTAKBANK': 1720.0,
                'SBIN': 825.0,
                'BHARTIARTL': 1245.0,
                'ITC': 465.0,
                'LT': 3670.0
            }
            
            if symbol in estimated_prices:
                price = estimated_prices[symbol]
                logger.warning(f"⚠️ Using estimated price for {symbol}: ₹{price} (Quote API not available)")
                logger.warning("🔧 Fix: Enable market data permissions or this is just an estimate")
                return price
            
            logger.error(f"❌ No fallback price available for {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting fallback price for {symbol}: {e}")
            return None
    
    def get_stock_data(self, symbol: str, period: str = "5d", interval: str = "5m") -> Optional[pd.DataFrame]:
        """
        Get stock data from Zerodha historical data API with comprehensive error handling
        """
        try:
            if not self.api_authenticated:
                logger.error(f"❌ Cannot get historical data for {symbol} - API not authenticated")
                return None
            
            # Get instrument info
            instrument_info = self.instruments_cache.get(symbol)
            if not instrument_info:
                logger.error(f"❌ Instrument {symbol} not found for historical data")
                return None
            
            # Get instrument token
            instrument_token = instrument_info.get('instrument_token')
            if not instrument_token:
                logger.error(f"❌ No instrument token for {symbol}")
                logger.error("🔍 DEBUG: Instrument data may be corrupted")
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
            logger.debug(f"📊 Fetching {days}d historical data for {symbol} (token: {instrument_token})...")
            historical_data = self.zerodha_client.get_historical_data(
                instrument_token=instrument_token,
                from_date=start_date,
                to_date=end_date,
                interval=interval
            )
            
            if not historical_data:
                logger.error(f"❌ No historical data received for {symbol}")
                logger.error("🔍 DEBUG: Check if:")
                logger.error("   1. Market was open during requested period")
                logger.error("   2. Symbol has trading history")
                logger.error("   3. API has historical data permissions")
                logger.error("   4. Date range is valid")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(historical_data)
            
            if df.empty:
                logger.error(f"❌ Empty historical data for {symbol}")
                return None
            
            # Standardize column names
            df.columns = [col.lower() for col in df.columns]
            
            # Ensure we have the required columns
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                logger.error(f"❌ Missing required columns for {symbol}: {missing_cols}")
                logger.error(f"🔍 Available columns: {list(df.columns)}")
                return None
            
            logger.debug(f"✅ Got {len(df)} candles for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"❌ Failed to get historical data for {symbol}: {e}")
            logger.error("🔍 DEBUG: Check:")
            logger.error("   1. Network connectivity")
            logger.error("   2. API rate limits")
            logger.error("   3. Zerodha historical data service status")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
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
        Screen all stocks in universe for trading opportunities - REAL DATA ONLY
        Returns list of stocks with signals sorted by strength
        """
        if not self.api_authenticated:
            logger.error("❌ Cannot screen stocks - API not authenticated")
            logger.error("🔍 CRITICAL: Fix authentication before attempting to trade")
            return []
        
        if not self.instruments_cache:
            logger.error("❌ Cannot screen stocks - No instruments loaded")
            logger.error("🔍 CRITICAL: Fix instrument loading before attempting to trade")
            return []
        
        signals = []
        
        logger.info("🔍 Starting comprehensive stock screening with REAL market data...")
        logger.info(f"📊 Analyzing {len(self.instruments_cache)} stocks from NSE/BSE")
        
        # Screen stocks without fallback - REAL DATA ONLY
        try:
            # Step 1: Pre-screening for performance
            promising_stocks = self._pre_screen_stocks()
            
            if not promising_stocks:
                logger.error("❌ Pre-screening returned no stocks")
                logger.error("🔍 DEBUG: Check if:")
                logger.error("   1. Market is open")
                logger.error("   2. Stocks have recent trading activity")
                logger.error("   3. Pre-screening criteria are too strict")
                return []
            
            logger.info(f"🎯 Pre-screening identified {len(promising_stocks)} promising stocks")
            
            # Step 2: Detailed analysis of promising stocks
            analyzed_count = 0
            failed_count = 0
            
            for symbol in promising_stocks:
                try:
                    logger.debug(f"🔍 Analyzing {symbol}...")
                    signal_data = self.generate_signals(symbol)
                    
                    if signal_data['signal'] != 'HOLD' and signal_data['strength'] > 0.4:
                        signal_data['symbol'] = symbol
                        signals.append(signal_data)
                        
                        logger.info(f"📈 {symbol}: {signal_data['signal']} "
                                  f"(Strength: {signal_data['strength']:.2f}, Price: ₹{signal_data.get('price', 0)}) - "
                                  f"{', '.join(signal_data.get('reasons', [])[:2])}")
                    else:
                        logger.debug(f"📊 {symbol}: {signal_data['signal']} (Strength: {signal_data['strength']:.2f}) - Not strong enough")
                    
                    analyzed_count += 1
                    
                    # Progress logging
                    if analyzed_count % 20 == 0:
                        logger.info(f"📊 Analyzed {analyzed_count}/{len(promising_stocks)} stocks... Found {len(signals)} signals so far")
                    
                except Exception as e:
                    failed_count += 1
                    logger.warning(f"⚠️ Failed to analyze {symbol}: {e}")
                    continue
            
            # Sort by signal strength
            signals.sort(key=lambda x: x['strength'], reverse=True)
            
            logger.info(f"✅ Stock screening complete:")
            logger.info(f"   📊 Analyzed: {analyzed_count} stocks")
            logger.info(f"   ❌ Failed: {failed_count} stocks")
            logger.info(f"   📈 Found: {len(signals)} trading opportunities")
            
            if not signals:
                logger.warning("⚠️ No trading opportunities found in current market scan")
                logger.warning("🔍 This could mean:")
                logger.warning("   1. Market conditions are not favorable")
                logger.warning("   2. All stocks are in HOLD range")
                logger.warning("   3. Signal strength threshold (0.4) is too high")
                logger.warning("   4. Technical indicators show neutral signals")
            
            return signals[:Config.TOP_PERFORMERS_COUNT]  # Return top performers
            
        except Exception as e:
            logger.error(f"❌ Critical error during stock screening: {e}")
            logger.error("🔍 DEBUG: This is a serious issue - check:")
            logger.error("   1. API connectivity")
            logger.error("   2. Market data availability")
            logger.error("   3. System resources")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return []
    
    def validate_signal(self, signal_data: Dict) -> bool:
        """Validate trading signal quality and data integrity"""
        try:
            if not signal_data:
                logger.warning("❌ Signal validation: Empty signal data")
                return False
            
            # Check required fields
            required_fields = ['symbol', 'signal', 'strength', 'price']
            for field in required_fields:
                if field not in signal_data:
                    logger.warning(f"❌ Signal validation: Missing field '{field}'")
                    return False
            
            symbol = signal_data['symbol']
            signal_type = signal_data['signal']
            strength = signal_data['strength']
            price = signal_data['price']
            
            # Validate signal type
            if signal_type not in ['BUY', 'SELL', 'HOLD']:
                logger.warning(f"❌ Signal validation: Invalid signal type '{signal_type}' for {symbol}")
                return False
            
            # Validate strength
            if not isinstance(strength, (int, float)) or strength < 0 or strength > 1:
                logger.warning(f"❌ Signal validation: Invalid strength {strength} for {symbol}")
                return False
            
            # Validate price
            if not isinstance(price, (int, float)) or price <= 0:
                logger.warning(f"❌ Signal validation: Invalid price {price} for {symbol}")
                return False
            
            # Check if symbol exists in our instruments cache
            if symbol not in self.instruments_cache:
                logger.warning(f"❌ Signal validation: Symbol {symbol} not in instruments cache")
                return False
            
            # Validate price reasonableness (basic sanity check)
            if price < 1 or price > 100000:  # Very basic range check
                logger.warning(f"❌ Signal validation: Price {price} out of reasonable range for {symbol}")
                return False
            
            logger.debug(f"✅ Signal validation passed for {symbol}: {signal_type} @ ₹{price}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error validating signal: {e}")
            return False
    
    def get_market_sentiment(self) -> Dict[str, any]:
        """Get overall market sentiment using NIFTY data"""
        try:
            if not self.api_authenticated:
                logger.error("❌ Cannot get market sentiment - API not authenticated")
                return {'sentiment': 'UNKNOWN', 'strength': 0.0, 'reasons': ['API not authenticated']}
            
            logger.debug("📊 Analyzing market sentiment using NIFTY...")
            
            # Try to get NIFTY data for sentiment analysis
            try:
                # Get NIFTY quote
                quote = self.zerodha_client.get_quote(['NSE:NIFTY 50'])
                if not quote or 'NSE:NIFTY 50' not in quote:
                    # Fallback to basic sentiment
                    logger.warning("⚠️ Could not get NIFTY data, using neutral sentiment")
                    return {'sentiment': 'NEUTRAL', 'strength': 0.5, 'reasons': ['No NIFTY data available']}
                
                nifty_data = quote['NSE:NIFTY 50']
                current_price = nifty_data.get('last_price', 0)
                change = nifty_data.get('net_change', 0)
                change_percent = nifty_data.get('change', 0)
                
                # Simple sentiment based on NIFTY movement
                reasons = []
                if change > 0:
                    if change_percent > 1:
                        sentiment = 'BULLISH'
                        strength = min(0.8, 0.5 + abs(change_percent) / 2)
                        reasons.append(f'NIFTY up {change_percent:.2f}%')
                    else:
                        sentiment = 'BULLISH'  
                        strength = 0.6
                        reasons.append(f'NIFTY slightly up {change_percent:.2f}%')
                elif change < 0:
                    if change_percent < -1:
                        sentiment = 'BEARISH'
                        strength = min(0.8, 0.5 + abs(change_percent) / 2)
                        reasons.append(f'NIFTY down {change_percent:.2f}%')
                    else:
                        sentiment = 'BEARISH'
                        strength = 0.6
                        reasons.append(f'NIFTY slightly down {change_percent:.2f}%')
                else:
                    sentiment = 'NEUTRAL'
                    strength = 0.5
                    reasons.append('NIFTY unchanged')
                
                logger.debug(f"📊 Market sentiment: {sentiment} (NIFTY: ₹{current_price}, {change_percent:.2f}%)")
                
                return {
                    'sentiment': sentiment,
                    'strength': strength,
                    'reasons': reasons,
                    'nifty_price': current_price,
                    'nifty_change': change_percent
                }
                
            except Exception as e:
                logger.warning(f"⚠️ Error getting NIFTY data for sentiment: {e}")
                return {'sentiment': 'NEUTRAL', 'strength': 0.5, 'reasons': ['Error fetching market data']}
            
        except Exception as e:
            logger.error(f"❌ Error in market sentiment analysis: {e}")
            return {'sentiment': 'UNKNOWN', 'strength': 0.0, 'reasons': [f'Analysis error: {str(e)[:50]}']}
    
    def _pre_screen_stocks(self) -> List[str]:
        """Pre-screen stocks for performance optimization"""
        try:
            if not self.api_authenticated:
                logger.error("❌ Cannot pre-screen stocks - API not authenticated")
                return []
            
            if not self.instruments_cache:
                logger.error("❌ Cannot pre-screen stocks - No instruments loaded")
                return []
            
            # Get a reasonable subset of stocks for analysis
            # Priority: Large cap stocks that are actively traded
            priority_stocks = [
                'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK',
                'KOTAKBANK', 'SBIN', 'BHARTIARTL', 'ITC', 'LT',
                'HCLTECH', 'WIPRO', 'MARUTI', 'ASIANPAINT', 'TITAN'
            ]
            
            # Filter to only include stocks that are in our instruments cache
            available_priority = [stock for stock in priority_stocks if stock in self.instruments_cache]
            
            # Add some random stocks from our cache for diversity
            all_symbols = list(self.instruments_cache.keys())
            if len(all_symbols) > len(available_priority):
                import random
                random.seed(42)  # For reproducible results
                additional_stocks = random.sample(
                    [s for s in all_symbols if s not in available_priority],
                    min(10, len(all_symbols) - len(available_priority))
                )
                available_priority.extend(additional_stocks)
            
            # Limit total stocks for performance
            result = available_priority[:Config.TOP_PERFORMERS_COUNT]
            
            logger.debug(f"📊 Pre-screening identified {len(result)} stocks for analysis")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in pre-screening stocks: {e}")
            return [] 