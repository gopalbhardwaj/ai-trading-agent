"""
Risk Management Module for Trading Agent
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

from config import Config

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, zerodha_client):
        self.zerodha_client = zerodha_client
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.open_positions = {}
        self.daily_budget_used = 0.0
        self.max_daily_loss_reached = False
        
        # Load daily state
        self._load_daily_state()
    
    def _load_daily_state(self):
        """Load daily trading state from file"""
        try:
            with open('daily_state.json', 'r') as f:
                state = json.load(f)
                
            # Check if it's a new trading day
            today = datetime.now().strftime('%Y-%m-%d')
            if state.get('date') != today:
                # Reset for new day
                self._reset_daily_state()
            else:
                # Load existing state
                self.daily_pnl = state.get('daily_pnl', 0.0)
                self.daily_trades = state.get('daily_trades', 0)
                self.daily_budget_used = state.get('daily_budget_used', 0.0)
                self.max_daily_loss_reached = state.get('max_daily_loss_reached', False)
                
                logger.info(f"📊 Loaded daily state: PnL: ₹{self.daily_pnl:.2f}, "
                          f"Trades: {self.daily_trades}, Budget Used: ₹{self.daily_budget_used:.2f}")
                
        except FileNotFoundError:
            self._reset_daily_state()
        except Exception as e:
            logger.error(f"Failed to load daily state: {e}")
            self._reset_daily_state()
    
    def _save_daily_state(self):
        """Save daily trading state to file"""
        try:
            state = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'daily_pnl': self.daily_pnl,
                'daily_trades': self.daily_trades,
                'daily_budget_used': self.daily_budget_used,
                'max_daily_loss_reached': self.max_daily_loss_reached
            }
            
            with open('daily_state.json', 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save daily state: {e}")
    
    def _reset_daily_state(self):
        """Reset daily state for new trading day"""
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.daily_budget_used = 0.0
        self.max_daily_loss_reached = False
        self._save_daily_state()
        logger.info("🔄 Reset daily state for new trading day")
    
    def calculate_position_size(self, signal_data: Dict, available_margin: float) -> Tuple[int, float]:
        """
        Calculate position size based on risk parameters
        Returns: (quantity, amount_needed)
        """
        try:
            price = signal_data['price']
            stop_loss = signal_data['stop_loss']
            
            # Calculate risk per share
            if signal_data['signal'] == 'BUY':
                risk_per_share = abs(price - stop_loss)
            else:  # SELL
                risk_per_share = abs(stop_loss - price)
            
            if risk_per_share <= 0:
                logger.warning("Invalid risk calculation")
                return 0, 0
            
            # Calculate maximum risk amount
            remaining_budget = Config.MAX_DAILY_BUDGET - self.daily_budget_used
            max_risk_amount = min(remaining_budget * Config.RISK_PER_TRADE, 
                                available_margin * Config.RISK_PER_TRADE)
            
            # Calculate quantity based on risk
            max_quantity = int(max_risk_amount / risk_per_share)
            
            # Calculate amount needed
            amount_needed = max_quantity * price
            
            # Check constraints
            if amount_needed > available_margin:
                max_quantity = int(available_margin / price)
                amount_needed = max_quantity * price
            
            if amount_needed > remaining_budget:
                max_quantity = int(remaining_budget / price)
                amount_needed = max_quantity * price
            
            # Minimum quantity check
            if max_quantity < 1:
                return 0, 0
            
            logger.info(f"💰 Position size: {max_quantity} shares @ ₹{price:.2f} "
                       f"(Risk: ₹{risk_per_share:.2f}/share, Total: ₹{amount_needed:.2f})")
            
            return max_quantity, amount_needed
            
        except Exception as e:
            logger.error(f"Failed to calculate position size: {e}")
            return 0, 0
    
    def can_take_trade(self, signal_data: Dict) -> Tuple[bool, str]:
        """
        Check if we can take a new trade based on risk limits
        Returns: (can_trade, reason)
        """
        try:
            # Check if max daily loss reached
            if self.max_daily_loss_reached:
                return False, "Maximum daily loss limit reached"
            
            # Check daily PnL
            if self.daily_pnl <= -Config.MAX_DAILY_LOSS:
                self.max_daily_loss_reached = True
                self._save_daily_state()
                return False, f"Daily loss limit exceeded: ₹{self.daily_pnl:.2f}"
            
            # Check maximum positions
            current_positions = len(self.get_current_positions())
            if current_positions >= Config.MAX_POSITIONS:
                return False, f"Maximum positions limit reached: {current_positions}/{Config.MAX_POSITIONS}"
            
            # Check market hours
            if not self.zerodha_client.is_market_open():
                return False, "Market is closed"
            
            # Check available margin
            available_margin = self.zerodha_client.get_available_margin()
            if available_margin < 1000:  # Minimum margin required
                return False, f"Insufficient margin: ₹{available_margin:.2f}"
            
            # Check if we have enough budget left
            remaining_budget = Config.MAX_DAILY_BUDGET - self.daily_budget_used
            if remaining_budget < 1000:  # Minimum budget required
                return False, f"Daily budget exhausted: ₹{remaining_budget:.2f} remaining"
            
            # Check signal strength
            if signal_data['strength'] < 0.5:
                return False, f"Signal strength too low: {signal_data['strength']:.2f}"
            
            return True, "All risk checks passed"
            
        except Exception as e:
            logger.error(f"Risk check failed: {e}")
            return False, "Risk check failed"
    
    def record_trade(self, order_data: Dict):
        """Record a trade for risk tracking"""
        try:
            self.daily_trades += 1
            amount = order_data.get('quantity', 0) * order_data.get('price', 0)
            self.daily_budget_used += amount
            
            logger.info(f"📝 Trade recorded: #{self.daily_trades}, Amount: ₹{amount:.2f}")
            self._save_daily_state()
            
        except Exception as e:
            logger.error(f"Failed to record trade: {e}")
    
    def update_pnl(self, pnl_change: float):
        """Update daily PnL"""
        try:
            self.daily_pnl += pnl_change
            
            logger.info(f"💹 PnL Updated: {'+' if pnl_change >= 0 else ''}₹{pnl_change:.2f} "
                       f"(Total: ₹{self.daily_pnl:.2f})")
            
            # Check if daily loss limit reached
            if self.daily_pnl <= -Config.MAX_DAILY_LOSS:
                self.max_daily_loss_reached = True
                logger.warning(f"🚨 Daily loss limit reached: ₹{self.daily_pnl:.2f}")
            
            self._save_daily_state()
            
        except Exception as e:
            logger.error(f"Failed to update PnL: {e}")
    
    def get_current_positions(self) -> List[Dict]:
        """Get current open positions"""
        try:
            positions = self.zerodha_client.get_positions()
            day_positions = positions.get('day', [])
            
            # Filter only positions with non-zero quantity
            open_positions = [pos for pos in day_positions if pos.get('quantity', 0) != 0]
            
            return open_positions
            
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    def should_square_off_position(self, position: Dict) -> Tuple[bool, str]:
        """
        Check if a position should be squared off based on various criteria
        """
        try:
            symbol = position.get('tradingsymbol', '')
            quantity = position.get('quantity', 0)
            avg_price = position.get('average_price', 0)
            current_price = position.get('last_price', avg_price)
            pnl = position.get('pnl', 0)
            
            # Check time-based square off (before market close)
            now = datetime.now()
            square_off_time = datetime.strptime(Config.SQUARE_OFF_TIME, "%H:%M").time()
            current_time = now.time()
            
            if current_time >= square_off_time:
                return True, "Time-based square off (market closing soon)"
            
            # Calculate percentage PnL
            if avg_price > 0:
                pnl_percent = (pnl / (abs(quantity) * avg_price)) * 100
            else:
                pnl_percent = 0
            
            # Check stop loss
            if quantity > 0:  # Long position
                stop_loss_percent = -Config.STOP_LOSS_PERCENT * 100
                take_profit_percent = Config.TAKE_PROFIT_PERCENT * 100
            else:  # Short position
                stop_loss_percent = Config.STOP_LOSS_PERCENT * 100
                take_profit_percent = -Config.TAKE_PROFIT_PERCENT * 100
            
            if pnl_percent <= stop_loss_percent:
                return True, f"Stop loss triggered: {pnl_percent:.2f}%"
            
            if (quantity > 0 and pnl_percent >= take_profit_percent) or \
               (quantity < 0 and pnl_percent <= take_profit_percent):
                return True, f"Take profit triggered: {pnl_percent:.2f}%"
            
            return False, "Position within acceptable range"
            
        except Exception as e:
            logger.error(f"Failed to check square off for position: {e}")
            return False, "Error in position check"
    
    def get_risk_summary(self) -> Dict:
        """Get current risk summary"""
        try:
            positions = self.get_current_positions()
            total_exposure = sum(abs(pos.get('quantity', 0) * pos.get('last_price', 0)) for pos in positions)
            total_pnl = sum(pos.get('pnl', 0) for pos in positions)
            
            remaining_budget = Config.MAX_DAILY_BUDGET - self.daily_budget_used
            remaining_loss_capacity = Config.MAX_DAILY_LOSS + self.daily_pnl
            
            return {
                'daily_pnl': self.daily_pnl,
                'daily_trades': self.daily_trades,
                'open_positions': len(positions),
                'total_exposure': total_exposure,
                'unrealized_pnl': total_pnl,
                'budget_used': self.daily_budget_used,
                'remaining_budget': remaining_budget,
                'remaining_loss_capacity': remaining_loss_capacity,
                'max_loss_reached': self.max_daily_loss_reached
            }
            
        except Exception as e:
            logger.error(f"Failed to get risk summary: {e}")
            return {}
    
    def validate_order_params(self, order_params: Dict) -> Tuple[bool, str]:
        """
        Validate order parameters before placing order
        """
        try:
            # Check required parameters
            required_params = ['tradingsymbol', 'quantity', 'price', 'transaction_type']
            for param in required_params:
                if param not in order_params or order_params[param] is None:
                    return False, f"Missing required parameter: {param}"
            
            # Check quantity
            quantity = order_params.get('quantity', 0)
            if quantity <= 0:
                return False, "Invalid quantity"
            
            # Check price
            price = order_params.get('price', 0)
            if price <= 0:
                return False, "Invalid price"
            
            # Check order value
            order_value = quantity * price
            if order_value > Config.MAX_DAILY_BUDGET:
                return False, f"Order value exceeds daily budget: ₹{order_value:.2f}"
            
            # Check remaining budget
            remaining_budget = Config.MAX_DAILY_BUDGET - self.daily_budget_used
            if order_value > remaining_budget:
                return False, f"Insufficient remaining budget: ₹{remaining_budget:.2f}"
            
            return True, "Order parameters valid"
            
        except Exception as e:
            logger.error(f"Order validation failed: {e}")
            return False, "Validation failed"
    
    def emergency_square_off_all(self) -> bool:
        """
        Emergency function to square off all positions
        """
        try:
            positions = self.get_current_positions()
            
            if not positions:
                logger.info("No positions to square off")
                return True
            
            logger.warning(f"🚨 Emergency square off: {len(positions)} positions")
            
            success_count = 0
            for position in positions:
                try:
                    symbol = position.get('tradingsymbol', '')
                    quantity = position.get('quantity', 0)
                    
                    if quantity == 0:
                        continue
                    
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
                        success_count += 1
                        logger.info(f"✅ Squared off {symbol}: {abs_quantity} shares")
                    else:
                        logger.error(f"❌ Failed to square off {symbol}")
                        
                except Exception as e:
                    logger.error(f"Failed to square off position {position}: {e}")
                    continue
            
            logger.info(f"Emergency square off completed: {success_count}/{len(positions)} successful")
            return success_count == len(positions)
            
        except Exception as e:
            logger.error(f"Emergency square off failed: {e}")
            return False 