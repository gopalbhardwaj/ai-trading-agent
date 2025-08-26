"""
Trading Engine - Main orchestrator for automated trading
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import threading
import schedule

from src.zerodha_client import ZerodhaClient
from src.market_analyzer import MarketAnalyzer
from src.risk_manager import RiskManager
from config import Config

logger = logging.getLogger(__name__)

class KiteClientAdapter:
    """Adapter to make KiteConnect client compatible with MarketAnalyzer and RiskManager"""
    def __init__(self, kite_client):
        self.kite = kite_client
        self.kite_client = kite_client  # For compatibility
        self.is_authenticated = True
        self.access_token = getattr(kite_client, 'access_token', None)
    
    def get_instruments(self, exchange="NSE"):
        """Get instruments for an exchange"""
        try:
            return self.kite.instruments(exchange)
        except Exception as e:
            logger.error(f"Failed to get instruments for {exchange}: {e}")
            return []
    
    def get_historical_data(self, instrument_token, from_date, to_date, interval="minute"):
        """Get historical data"""
        try:
            return self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
        except Exception as e:
            logger.error(f"Failed to get historical data: {e}")
            return []
    
    def get_quote(self, instruments):
        """Get quote for instruments"""
        try:
            return self.kite.quote(instruments)
        except Exception as e:
            logger.error(f"Failed to get quote: {e}")
            return {}
    
    def get_ltp(self, instruments):
        """Get LTP for instruments"""
        try:
            return self.kite.ltp(instruments)
        except Exception as e:
            logger.error(f"Failed to get LTP: {e}")
            return {}
    
    def get_positions(self):
        """Get positions"""
        try:
            return self.kite.positions()
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return {'net': [], 'day': []}
    
    def get_holdings(self):
        """Get holdings"""
        try:
            return self.kite.holdings()
        except Exception as e:
            logger.error(f"Failed to get holdings: {e}")
            return []
    
    def get_orders(self):
        """Get orders"""
        try:
            return self.kite.orders()
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return []
    
    def get_available_margin(self):
        """Get available margin"""
        try:
            margins = self.kite.margins()
            equity_margin = margins.get('equity', {})
            return equity_margin.get('available', {}).get('cash', 0)
        except Exception as e:
            logger.error(f"Failed to get margin: {e}")
            return 0
    
    def place_order(self, **kwargs):
        """Place an order"""
        try:
            return self.kite.place_order(**kwargs)
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return None
    
    def cancel_order(self, order_id):
        """Cancel an order"""
        try:
            self.kite.cancel_order(order_id=order_id)
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return False
    
    def modify_order(self, order_id, **kwargs):
        """Modify an order"""
        try:
            self.kite.modify_order(order_id=order_id, **kwargs)
            return True
        except Exception as e:
            logger.error(f"Failed to modify order: {e}")
            return False 

class TradingEngine:
    def __init__(self, kite_client=None):
        # Use provided kite client if available, otherwise create new one
        if kite_client:
            self.zerodha_client = KiteClientAdapter(kite_client)
            self.external_auth = True
        else:
            self.zerodha_client = ZerodhaClient()
            self.external_auth = False
            
        self.market_analyzer = None
        self.risk_manager = None
        self.is_running = False
        self.stop_trading = False
        
        # Trading state
        self.active_orders = {}
        self.monitoring_positions = {}
        
    def initialize(self) -> bool:
        """Initialize all components"""
        try:
            logger.info("🚀 Initializing Trading Engine...")
            
            # Validate configuration
            Config.validate_config()
            
            # Handle authentication
            if self.external_auth:
                logger.info("✅ Using externally authenticated Kite client")
            else:
                # Authenticate with Zerodha using internal client
                if not self.zerodha_client.authenticate():
                    logger.error("❌ Failed to authenticate with Zerodha")
                    return False
            
            # Initialize components
            self.market_analyzer = MarketAnalyzer(self.zerodha_client)
            self.risk_manager = RiskManager(self.zerodha_client)
            
            # Get account info
            try:
                if self.external_auth:
                    profile = self.zerodha_client.kite.profile()
                else:
                    profile = self.zerodha_client.get_profile()
                logger.info(f"✅ Logged in as: {profile.get('user_name', 'Unknown')}")
            except Exception as e:
                logger.warning(f"Could not fetch profile: {e}")
                profile = {}
            
            # Display risk summary
            try:
                risk_summary = self.risk_manager.get_risk_summary()
                logger.info(f"💰 Available Budget: ₹{risk_summary.get('remaining_budget', 0):.2f}")
                logger.info(f"📊 Daily PnL: ₹{risk_summary.get('daily_pnl', 0):.2f}")
            except Exception as e:
                logger.warning(f"Could not get risk summary: {e}")
            
            logger.info("✅ Trading Engine initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Trading Engine: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _analyze_and_trade(self):
        """Analyze market and execute trades"""
        try:
            if self.stop_trading:
                return
                
            logger.info("🔍 Analyzing market for trading opportunities...")
            
            # Get market sentiment
            market_sentiment = self.market_analyzer.get_market_sentiment()
            logger.info(f"📈 Market Sentiment: {market_sentiment['sentiment']} "
                       f"(Strength: {market_sentiment['strength']:.2f})")
            
            # Skip trading in highly bearish market
            if market_sentiment['sentiment'] == 'BEARISH' and market_sentiment['strength'] < 0.3:
                logger.info("🐻 Bearish market detected. Skipping new trades.")
                return
            
            # Screen stocks for opportunities
            signals = self.market_analyzer.screen_stocks()
            
            if not signals:
                logger.info("📊 No trading opportunities found")
                return
            
            # Process top signals
            for signal in signals[:3]:  # Top 3 signals
                if self.stop_trading:
                    break
                    
                success = self._execute_trade(signal)
                if success:
                    time.sleep(10)  # Wait between trades
                    
        except Exception as e:
            logger.error(f"Error in market analysis: {e}")
    
    def _execute_trade(self, signal_data: Dict) -> bool:
        """Execute a trade based on signal"""
        try:
            symbol = signal_data['symbol']
            
            logger.info(f"🎯 Processing trade signal for {symbol}: {signal_data['signal']} "
                       f"(Strength: {signal_data['strength']:.2f})")
            
            # Risk check
            can_trade, reason = self.risk_manager.can_take_trade(signal_data)
            if not can_trade:
                logger.warning(f"⛔ Trade rejected for {symbol}: {reason}")
                return False
            
            # Validate signal
            if not self.market_analyzer.validate_signal(signal_data):
                logger.warning(f"⛔ Signal validation failed for {symbol}")
                return False
            
            # Get available margin
            available_margin = self.zerodha_client.get_available_margin()
            
            # Calculate position size
            quantity, amount_needed = self.risk_manager.calculate_position_size(
                signal_data, available_margin)
            
            if quantity == 0:
                logger.warning(f"⛔ No quantity calculated for {symbol}")
                return False
            
            # Prepare order parameters
            order_params = {
                'tradingsymbol': symbol,
                'exchange': 'NSE',
                'transaction_type': 'BUY' if signal_data['signal'] == 'BUY' else 'SELL',
                'quantity': quantity,
                'order_type': 'LIMIT',
                'price': signal_data['price'],
                'product': 'MIS',  # Intraday
                'validity': 'DAY'
            }
            
            # Validate order parameters
            valid, validation_msg = self.risk_manager.validate_order_params(order_params)
            if not valid:
                logger.warning(f"⛔ Order validation failed for {symbol}: {validation_msg}")
                return False
            
            # Place order
            order_id = self.zerodha_client.place_order(**order_params)
            
            if order_id:
                # Record trade
                order_data = {
                    'order_id': order_id,
                    'symbol': symbol,
                    'quantity': quantity,
                    'price': signal_data['price'],
                    'signal_data': signal_data,
                    'timestamp': datetime.now()
                }
                
                self.active_orders[order_id] = order_data
                self.risk_manager.record_trade(order_data)
                
                logger.info(f"✅ Order placed for {symbol}: {order_id}")
                
                # Start monitoring this position
                threading.Thread(target=self._monitor_order, args=(order_id,), daemon=True).start()
                
                return True
            else:
                logger.error(f"❌ Failed to place order for {symbol}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to execute trade for {signal_data.get('symbol', 'Unknown')}: {e}")
            return False
    
    def _monitor_order(self, order_id: str):
        """Monitor a specific order until it's filled or cancelled"""
        try:
            order_data = self.active_orders.get(order_id)
            if not order_data:
                return
            
            symbol = order_data['symbol']
            max_wait_time = 300  # 5 minutes
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                try:
                    # Get order status
                    orders = self.zerodha_client.get_orders()
                    current_order = next((o for o in orders if o['order_id'] == order_id), None)
                    
                    if not current_order:
                        logger.warning(f"Order {order_id} not found")
                        break
                    
                    status = current_order.get('status', '')
                    
                    if status == 'COMPLETE':
                        logger.info(f"✅ Order filled: {symbol} ({order_id})")
                        
                        # Add to monitoring positions
                        self.monitoring_positions[order_id] = order_data
                        
                        # Remove from active orders
                        if order_id in self.active_orders:
                            del self.active_orders[order_id]
                        
                        break
                        
                    elif status in ['CANCELLED', 'REJECTED']:
                        logger.warning(f"❌ Order {status.lower()}: {symbol} ({order_id})")
                        
                        # Remove from active orders
                        if order_id in self.active_orders:
                            del self.active_orders[order_id]
                        
                        break
                    
                    time.sleep(30)  # Check every 30 seconds
                    
                except Exception as e:
                    logger.error(f"Error monitoring order {order_id}: {e}")
                    time.sleep(30)
            
            # Timeout handling
            if time.time() - start_time >= max_wait_time:
                logger.warning(f"⏰ Order timeout: {symbol} ({order_id}). Cancelling...")
                self.zerodha_client.cancel_order(order_id)
                
                if order_id in self.active_orders:
                    del self.active_orders[order_id]
                    
        except Exception as e:
            logger.error(f"Error in order monitoring: {e}")
    
    def _monitor_positions(self):
        """Monitor all open positions"""
        try:
            positions = self.risk_manager.get_current_positions()
            
            if not positions:
                return
            
            logger.info(f"👀 Monitoring {len(positions)} positions...")
            
            for position in positions:
                try:
                    symbol = position.get('tradingsymbol', '')
                    pnl = position.get('pnl', 0)
                    
                    # Check if position should be squared off
                    should_square_off, reason = self.risk_manager.should_square_off_position(position)
                    
                    if should_square_off:
                        logger.info(f"🔄 Squaring off {symbol}: {reason}")
                        self._square_off_position(position)
                        
                except Exception as e:
                    logger.error(f"Error monitoring position: {e}")
                    
        except Exception as e:
            logger.error(f"Error in position monitoring: {e}")
    
    def _square_off_position(self, position: Dict) -> bool:
        """Square off a specific position"""
        try:
            symbol = position.get('tradingsymbol', '')
            quantity = position.get('quantity', 0)
            
            if quantity == 0:
                return True
            
            # Determine transaction type (opposite of current position)
            transaction_type = 'SELL' if quantity > 0 else 'BUY'
            abs_quantity = abs(quantity)
            
            # Place market order to square off
            order_id = self.zerodha_client.place_order(
                tradingsymbol=symbol,
                exchange='NSE',
                transaction_type=transaction_type,
                quantity=abs_quantity,
                order_type='MARKET',
                product='MIS'
            )
            
            if order_id:
                logger.info(f"✅ Square off order placed for {symbol}: {order_id}")
                
                # Update PnL
                pnl = position.get('pnl', 0)
                self.risk_manager.update_pnl(pnl)
                
                return True
            else:
                logger.error(f"❌ Failed to place square off order for {symbol}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to square off position: {e}")
            return False
    
    def _risk_check(self):
        """Perform periodic risk checks"""
        try:
            risk_summary = self.risk_manager.get_risk_summary()
            
            logger.info(f"🛡️ Risk Check - PnL: ₹{risk_summary.get('daily_pnl', 0):.2f}, "
                       f"Positions: {risk_summary.get('open_positions', 0)}, "
                       f"Budget Used: ₹{risk_summary.get('budget_used', 0):.2f}")
            
            # Check if max loss reached
            if risk_summary.get('max_loss_reached', False):
                logger.warning("🚨 Maximum daily loss reached. Stopping new trades.")
                self.stop_trading = True
                
                # Square off all positions
                self.risk_manager.emergency_square_off_all()
            
            # Check if close to loss limit
            remaining_loss_capacity = risk_summary.get('remaining_loss_capacity', 0)
            if remaining_loss_capacity < 1000:  # Less than ₹1000 buffer
                logger.warning(f"⚠️ Close to loss limit. Remaining capacity: ₹{remaining_loss_capacity:.2f}")
                
        except Exception as e:
            logger.error(f"Error in risk check: {e}")
    
    def stop(self):
        """Stop the trading engine"""
        logger.info("🛑 Stopping trading engine...")
        self.is_running = False
        self.stop_trading = True
        
        # Emergency square off if needed
        try:
            positions = self.risk_manager.get_current_positions()
            if positions:
                logger.warning("⚠️ Open positions found. Initiating square off...")
                self.risk_manager.emergency_square_off_all()
        except Exception as e:
            logger.error(f"Error during emergency square off: {e}")
        
        logger.info("✅ Trading engine stopped")
    
    def get_status(self) -> Dict:
        """Get current trading engine status"""
        try:
            risk_summary = self.risk_manager.get_risk_summary() if self.risk_manager else {}
            
            return {
                'is_running': self.is_running,
                'stop_trading': self.stop_trading,
                'market_open': self._is_market_open(),
                'active_orders': len(self.active_orders),
                'monitoring_positions': len(self.monitoring_positions),
                'risk_summary': risk_summary
            }
            
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {}
    
    def force_square_off_all(self):
        """Force square off all positions (manual intervention)"""
        try:
            logger.warning("🚨 Manual square off initiated")
            return self.risk_manager.emergency_square_off_all() if self.risk_manager else False
        except Exception as e:
            logger.error(f"Manual square off failed: {e}")
            return False
    
    def _is_market_open(self):
        """Check if market is open"""
        # Use webapp's market open logic for consistency
        from datetime import datetime
        now = datetime.now()
        if now.weekday() >= 5:  # Weekend
            return False
        market_open_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
        return market_open_time <= now <= market_close_time 