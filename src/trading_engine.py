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

class TradingEngine:
    def __init__(self):
        self.zerodha_client = ZerodhaClient()
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
            
            # Authenticate with Zerodha
            if not self.zerodha_client.authenticate():
                logger.error("❌ Failed to authenticate with Zerodha")
                return False
            
            # Initialize components
            self.market_analyzer = MarketAnalyzer(self.zerodha_client)
            self.risk_manager = RiskManager(self.zerodha_client)
            
            # Get account info
            profile = self.zerodha_client.get_profile()
            logger.info(f"✅ Logged in as: {profile.get('user_name', 'Unknown')}")
            
            # Display risk summary
            risk_summary = self.risk_manager.get_risk_summary()
            logger.info(f"💰 Available Budget: ₹{risk_summary.get('remaining_budget', 0):.2f}")
            logger.info(f"📊 Daily PnL: ₹{risk_summary.get('daily_pnl', 0):.2f}")
            
            logger.info("✅ Trading Engine initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Trading Engine: {e}")
            return False
    
    def start(self, daily_budget: float = None):
        """Start the trading engine"""
        try:
            if daily_budget:
                Config.MAX_DAILY_BUDGET = daily_budget
                logger.info(f"💵 Daily budget set to: ₹{daily_budget:.2f}")
            
            if not self.initialize():
                return False
            
            self.is_running = True
            self.stop_trading = False
            
            logger.info("🎯 Starting automated trading...")
            
            # Schedule trading tasks
            self._schedule_tasks()
            
            # Start main trading loop
            self._run_trading_loop()
            
        except KeyboardInterrupt:
            logger.info("🛑 Trading stopped by user")
            self.stop()
        except Exception as e:
            logger.error(f"❌ Trading engine error: {e}")
            self.stop()
    
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
    
    def _schedule_tasks(self):
        """Schedule various trading tasks"""
        # Market analysis every 5 minutes
        schedule.every(5).minutes.do(self._analyze_and_trade)
        
        # Position monitoring every 2 minutes
        schedule.every(2).minutes.do(self._monitor_positions)
        
        # Risk check every 10 minutes
        schedule.every(10).minutes.do(self._risk_check)
        
        # Auto square off at configured time
        schedule.every().day.at(Config.SQUARE_OFF_TIME).do(self._auto_square_off)
        
        logger.info("📅 Trading tasks scheduled")
    
    def _run_trading_loop(self):
        """Main trading loop"""
        while self.is_running:
            try:
                # Check if market is open
                if not self.zerodha_client.is_market_open():
                    logger.info("🏪 Market is closed. Waiting...")
                    time.sleep(300)  # Check every 5 minutes
                    continue
                
                # Run scheduled tasks
                schedule.run_pending()
                
                # Sleep for a short interval
                time.sleep(30)  # 30 seconds between iterations
                
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
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
                    
                    # Update PnL (only unrealized for now)
                    # self.risk_manager.update_pnl(pnl)  # Commented to avoid double counting
                    
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
    
    def _auto_square_off(self):
        """Auto square off all positions at market close"""
        try:
            logger.info("🔔 Auto square off time reached")
            
            positions = self.risk_manager.get_current_positions()
            if positions:
                logger.info(f"🔄 Squaring off {len(positions)} positions...")
                self.risk_manager.emergency_square_off_all()
            else:
                logger.info("✅ No positions to square off")
                
        except Exception as e:
            logger.error(f"Error in auto square off: {e}")
    
    def get_status(self) -> Dict:
        """Get current trading engine status"""
        try:
            risk_summary = self.risk_manager.get_risk_summary()
            
            return {
                'is_running': self.is_running,
                'stop_trading': self.stop_trading,
                'market_open': self.zerodha_client.is_market_open(),
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
            return self.risk_manager.emergency_square_off_all()
        except Exception as e:
            logger.error(f"Manual square off failed: {e}")
            return False 