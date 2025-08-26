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
                logger.info("⏹️ Trading stopped flag detected - skipping analysis")
                return
                
            logger.info("🔍 Starting market analysis for trading opportunities...")
            
            # Get market sentiment
            try:
                logger.info("📈 Analyzing market sentiment...")
                market_sentiment = self.market_analyzer.get_market_sentiment()
                logger.info(f"📊 Market Sentiment: {market_sentiment['sentiment']} "
                           f"(Strength: {market_sentiment['strength']:.2f})")
                
                # Skip trading in highly bearish market
                if market_sentiment['sentiment'] == 'BEARISH' and market_sentiment['strength'] < 0.3:
                    logger.info("🐻 Bearish market detected. Skipping new trades for safety.")
                    return
                elif market_sentiment['sentiment'] == 'BULLISH':
                    logger.info("🚀 Bullish market sentiment - good conditions for trading!")
                else:
                    logger.info(f"📊 Neutral market sentiment - proceeding with caution")
                    
            except Exception as e:
                logger.error(f"❌ Failed to analyze market sentiment: {e}")
                logger.info("🔄 Continuing with stock screening despite sentiment analysis failure...")
            
            # Screen stocks for opportunities
            try:
                logger.info("🔍 Screening stocks for trading opportunities...")
                signals = self.market_analyzer.screen_stocks()
                
                if not signals:
                    logger.info("📊 No trading opportunities found in current market scan")
                    logger.info("⏳ Will continue monitoring for better setups...")
                    return
                else:
                    logger.info(f"✨ Found {len(signals)} potential trading opportunities!")
                    
                    # Log details about top signals
                    for i, signal in enumerate(signals[:3]):
                        logger.info(f"🎯 Signal #{i+1}: {signal.get('symbol', 'Unknown')} - "
                                   f"{signal.get('signal', 'Unknown')} (Strength: {signal.get('strength', 0):.2f})")
                
            except Exception as e:
                logger.error(f"❌ Failed to screen stocks: {e}")
                logger.info("🔄 Using fallback stock screening...")
                
                # Fallback: Use a simple stock list for basic functionality
                try:
                    fallback_stocks = ['RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK']
                    logger.info(f"📊 Fallback: Checking {len(fallback_stocks)} major stocks...")
                    
                    # Create basic signals for fallback (demo purposes)
                    signals = []
                    for stock in fallback_stocks[:2]:  # Limit to 2 for safety
                        # Use realistic prices for demo
                        demo_prices = {
                            'RELIANCE': 2450.0,
                            'TCS': 3890.0, 
                            'HDFCBANK': 1678.0,
                            'INFY': 1825.0,
                            'ICICIBANK': 975.0
                        }
                        
                        signals.append({
                            'symbol': stock,
                            'signal': 'BUY',  # Demo mode - always BUY for simplicity
                            'strength': 0.6,
                            'price': demo_prices.get(stock, 100.0),
                            'confidence': 0.7
                        })
                    
                    if signals:
                        logger.info(f"🔄 Generated {len(signals)} fallback signals for demo trading")
                        logger.info("⚠️ DEMO MODE: Using fallback signals for testing purposes")
                    else:
                        logger.info("📊 No fallback signals generated - will retry in next cycle")
                        return
                        
                except Exception as fallback_error:
                    logger.error(f"❌ Fallback stock screening also failed: {fallback_error}")
                    logger.info("⏳ Will retry complete analysis in next cycle...")
                    return
            
            # Process top signals
            trades_attempted = 0
            trades_successful = 0
            
            for i, signal in enumerate(signals[:3]):  # Top 3 signals
                if self.stop_trading:
                    logger.info("⏹️ Trading stopped during signal processing")
                    break
                
                trades_attempted += 1
                symbol = signal.get('symbol', 'Unknown')
                logger.info(f"🎯 Processing signal #{i+1}/{min(3, len(signals))}: {symbol}")
                
                success = self._execute_trade(signal)
                if success:
                    trades_successful += 1
                    logger.info(f"✅ Trade executed successfully for {symbol}")
                    time.sleep(10)  # Wait between trades
                else:
                    logger.info(f"❌ Trade execution failed for {symbol}")
            
            # Summary of this analysis cycle
            if trades_attempted > 0:
                logger.info(f"📈 Analysis cycle complete: {trades_successful}/{trades_attempted} trades successful")
            else:
                logger.info("📊 Analysis cycle complete: No suitable opportunities found")
                logger.info("🔄 Continuing to monitor markets for better setups...")
                    
        except Exception as e:
            logger.error(f"❌ Error in market analysis: {e}")
            logger.info("🔄 Will retry analysis in next cycle...")
    
    def _execute_trade(self, signal_data: Dict) -> bool:
        """Execute a trade based on signal"""
        try:
            symbol = signal_data.get('symbol', 'Unknown')
            signal_type = signal_data.get('signal', 'Unknown')
            strength = signal_data.get('strength', 0)
            
            logger.info(f"🎯 Evaluating trade signal for {symbol}")
            logger.info(f"📊 Signal: {signal_type}, Strength: {strength:.2f}")
            
            # Risk check
            logger.info(f"🛡️ Performing risk assessment for {symbol}...")
            can_trade, reason = self.risk_manager.can_take_trade(signal_data)
            if not can_trade:
                logger.warning(f"⛔ Trade rejected for {symbol}: {reason}")
                return False
            else:
                logger.info(f"✅ Risk check passed for {symbol}")
            
            # Validate signal
            logger.info(f"🔍 Validating signal quality for {symbol}...")
            if not self.market_analyzer.validate_signal(signal_data):
                logger.warning(f"⛔ Signal validation failed for {symbol}")
                return False
            else:
                logger.info(f"✅ Signal validation passed for {symbol}")
            
            # Get available margin
            logger.info(f"💰 Checking available margin...")
            available_margin = self.zerodha_client.get_available_margin()
            logger.info(f"💵 Available margin: ₹{available_margin:.2f}")
            
            if available_margin < 1000:  # Minimum margin check
                logger.warning(f"⛔ Insufficient margin for trading: ₹{available_margin:.2f}")
                return False
            
            # Calculate position size
            logger.info(f"📐 Calculating position size for {symbol}...")
            quantity, amount_needed = self.risk_manager.calculate_position_size(
                signal_data, available_margin)
            
            if quantity == 0:
                logger.warning(f"⛔ No quantity calculated for {symbol} - insufficient funds or limits reached")
                return False
            else:
                logger.info(f"📊 Position size: {quantity} shares, Amount needed: ₹{amount_needed:.2f}")
            
            # Prepare order parameters
            price = signal_data.get('price', 0)
            order_params = {
                'tradingsymbol': symbol,
                'exchange': 'NSE',
                'transaction_type': 'BUY' if signal_type == 'BUY' else 'SELL',
                'quantity': quantity,
                'order_type': 'LIMIT',
                'price': price,
                'product': 'MIS',  # Intraday
                'validity': 'DAY'
            }
            
            logger.info(f"📋 Order details: {order_params['transaction_type']} {quantity} {symbol} @ ₹{price}")
            
            # Validate order parameters
            logger.info(f"🔍 Validating order parameters...")
            valid, validation_msg = self.risk_manager.validate_order_params(order_params)
            if not valid:
                logger.warning(f"⛔ Order validation failed for {symbol}: {validation_msg}")
                return False
            else:
                logger.info(f"✅ Order parameters validated")
            
            # Place order
            logger.info(f"🚀 Placing order for {symbol}...")
            order_id = self.zerodha_client.place_order(**order_params)
            
            if order_id:
                # Record trade
                order_data = {
                    'order_id': order_id,
                    'symbol': symbol,
                    'quantity': quantity,
                    'price': price,
                    'signal_data': signal_data,
                    'timestamp': datetime.now()
                }
                
                self.active_orders[order_id] = order_data
                self.risk_manager.record_trade(order_data)
                
                # Create trade record for UI
                trade_record = {
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'symbol': symbol,
                    'action': signal_type,
                    'quantity': quantity,
                    'price': round(price, 2),
                    'value': round(quantity * price, 2)
                }
                
                # Update webapp state and broadcast to UI
                try:
                    # Import here to avoid circular import
                    import asyncio
                    from webapp import trading_state, manager
                    
                    # Add to trading state
                    trading_state.trades.append(trade_record)
                    
                    # Update budget used (for BUY orders)
                    if signal_type == 'BUY':
                        trading_state.budget_used += trade_record['value']
                    
                    # Broadcast trade to UI
                    asyncio.run(manager.broadcast({
                        "type": "new_trade",
                        "trade": trade_record,
                        "pnl": trading_state.daily_pnl
                    }))
                    
                    logger.info(f"✅ Trade broadcasted to UI: {signal_type} {quantity} {symbol}")
                    
                except Exception as e:
                    logger.warning(f"Failed to broadcast trade to UI: {e}")
                
                logger.info(f"✅ Order placed successfully for {symbol}")
                logger.info(f"📄 Order ID: {order_id}")
                logger.info(f"👀 Starting order monitoring...")
                
                # Start monitoring this position
                threading.Thread(target=self._monitor_order, args=(order_id,), daemon=True).start()
                
                return True
            else:
                logger.error(f"❌ Failed to place order for {symbol} - broker rejected")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to execute trade for {signal_data.get('symbol', 'Unknown')}: {e}")
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
            
            logger.info(f"👀 Monitoring order {order_id} for {symbol}")
            
            while time.time() - start_time < max_wait_time:
                try:
                    # Get order status
                    orders = self.zerodha_client.get_orders()
                    current_order = next((o for o in orders if o['order_id'] == order_id), None)
                    
                    if not current_order:
                        logger.warning(f"Order {order_id} not found in order book")
                        break
                    
                    status = current_order.get('status', '')
                    filled_quantity = current_order.get('filled_quantity', 0)
                    average_price = current_order.get('average_price', 0)
                    
                    if status == 'COMPLETE':
                        logger.info(f"✅ Order filled: {symbol} ({order_id})")
                        logger.info(f"📊 Filled: {filled_quantity} shares @ ₹{average_price}")
                        
                        # Update trade record with actual fill details
                        try:
                            import asyncio
                            from webapp import trading_state, manager
                            
                            # Update the trade record with actual fill price
                            for trade in reversed(trading_state.trades):
                                if (trade['symbol'] == symbol and 
                                    abs(trade['quantity'] - filled_quantity) <= 1):  # Allow small rounding differences
                                    trade['price'] = round(average_price, 2)
                                    trade['value'] = round(filled_quantity * average_price, 2)
                                    trade['status'] = 'FILLED'
                                    break
                            
                            # Broadcast fill notification
                            asyncio.run(manager.broadcast({
                                "type": "trading_status",
                                "message": f"✅ Order FILLED: {trade['action']} {filled_quantity} {symbol} @ ₹{average_price:.2f}"
                            }))
                            
                        except Exception as e:
                            logger.warning(f"Failed to update UI for order fill: {e}")
                        
                        # Add to monitoring positions
                        self.monitoring_positions[order_id] = order_data
                        
                        # Remove from active orders
                        if order_id in self.active_orders:
                            del self.active_orders[order_id]
                        
                        break
                        
                    elif status in ['CANCELLED', 'REJECTED']:
                        logger.warning(f"❌ Order {status.lower()}: {symbol} ({order_id})")
                        
                        # Remove from UI if cancelled/rejected
                        try:
                            import asyncio
                            from webapp import trading_state, manager
                            
                            # Remove from trades list if order was cancelled
                            trading_state.trades = [t for t in trading_state.trades 
                                                 if not (t['symbol'] == symbol and t.get('order_id') == order_id)]
                            
                            # Broadcast cancellation
                            asyncio.run(manager.broadcast({
                                "type": "trading_status",
                                "message": f"❌ Order {status}: {symbol} - {current_order.get('status_message', 'No reason provided')}"
                            }))
                            
                        except Exception as e:
                            logger.warning(f"Failed to update UI for order cancellation: {e}")
                        
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
                success = self.zerodha_client.cancel_order(order_id)
                
                if success:
                    logger.info(f"✅ Order cancelled due to timeout: {symbol}")
                else:
                    logger.warning(f"❌ Failed to cancel timed out order: {symbol}")
                
                if order_id in self.active_orders:
                    del self.active_orders[order_id]
                    
        except Exception as e:
            logger.error(f"Error in order monitoring: {e}")
    
    def _monitor_positions(self):
        """Monitor all open positions"""
        try:
            logger.info("👀 Checking current positions...")
            positions = self.risk_manager.get_current_positions()
            
            if not positions:
                logger.info("📊 No open positions to monitor")
                return
            
            logger.info(f"👀 Monitoring {len(positions)} open positions...")
            
            for position in positions:
                try:
                    symbol = position.get('tradingsymbol', 'Unknown')
                    quantity = position.get('quantity', 0)
                    pnl = position.get('pnl', 0)
                    
                    logger.info(f"📊 Position: {symbol} - Qty: {quantity}, P&L: ₹{pnl:.2f}")
                    
                    # Check if position should be squared off
                    should_square_off, reason = self.risk_manager.should_square_off_position(position)
                    
                    if should_square_off:
                        logger.info(f"🔄 Squaring off {symbol}: {reason}")
                        success = self._square_off_position(position)
                        if success:
                            logger.info(f"✅ Successfully squared off {symbol}")
                        else:
                            logger.warning(f"❌ Failed to square off {symbol}")
                    else:
                        logger.info(f"✅ Position {symbol} within acceptable parameters")
                        
                except Exception as e:
                    logger.error(f"❌ Error monitoring position: {e}")
                    logger.info("🔄 Continuing with next position...")
                    
        except Exception as e:
            logger.error(f"❌ Error in position monitoring: {e}")
            logger.info("🔄 Will retry position monitoring in next cycle...")
    
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
            logger.info("🛡️ Performing risk assessment...")
            risk_summary = self.risk_manager.get_risk_summary()
            
            daily_pnl = risk_summary.get('daily_pnl', 0)
            open_positions = risk_summary.get('open_positions', 0)
            budget_used = risk_summary.get('budget_used', 0)
            
            logger.info(f"📊 Risk Summary - P&L: ₹{daily_pnl:.2f}, "
                       f"Positions: {open_positions}, "
                       f"Budget Used: ₹{budget_used:.2f}")
            
            # Check if max loss reached
            max_loss_reached = risk_summary.get('max_loss_reached', False)
            if max_loss_reached:
                logger.warning("🚨 Maximum daily loss reached. Stopping new trades.")
                logger.warning("🔄 Initiating emergency square off...")
                self.stop_trading = True
                
                # Square off all positions
                try:
                    self.risk_manager.emergency_square_off_all()
                    logger.info("✅ Emergency square off completed")
                except Exception as e:
                    logger.error(f"❌ Emergency square off failed: {e}")
            else:
                logger.info("✅ Daily loss limits are within acceptable range")
            
            # Check if close to loss limit
            remaining_loss_capacity = risk_summary.get('remaining_loss_capacity', 0)
            if remaining_loss_capacity < 1000:  # Less than ₹1000 buffer
                logger.warning(f"⚠️ Close to loss limit. Remaining capacity: ₹{remaining_loss_capacity:.2f}")
                logger.info("🛡️ Consider reducing position sizes or stopping trading")
            else:
                logger.info(f"✅ Risk capacity remaining: ₹{remaining_loss_capacity:.2f}")
                
        except Exception as e:
            logger.error(f"❌ Error in risk check: {e}")
            logger.info("🔄 Will retry risk check in next cycle...")
    
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