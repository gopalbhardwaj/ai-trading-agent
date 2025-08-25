"""
Zerodha Kite API Client for automated trading
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import webbrowser
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs
import threading

from kiteconnect import KiteConnect
from config import Config

logger = logging.getLogger(__name__)

class ZerodhaClient:
    def __init__(self):
        self.api_key = Config.KITE_API_KEY
        self.api_secret = Config.KITE_API_SECRET
        self.kite = KiteConnect(api_key=self.api_key)
        self.access_token = None
        self.request_token = None
        self.is_authenticated = False
        
    def authenticate(self) -> bool:
        """
        Authenticate with Zerodha Kite API
        Returns True if authentication successful
        """
        try:
            # Try to load existing access token
            if self._load_access_token():
                logger.info("✅ Loaded existing access token")
                return True
            
            # Start authentication flow
            login_url = self.kite.login_url()
            logger.info(f"🔐 Please login at: {login_url}")
            
            # Start local server to capture redirect
            self._start_auth_server()
            
            # Open browser for user to login
            webbrowser.open(login_url)
            
            # Wait for authentication
            timeout = 300  # 5 minutes
            start_time = time.time()
            
            while not self.request_token and (time.time() - start_time) < timeout:
                time.sleep(1)
            
            if not self.request_token:
                logger.error("❌ Authentication timeout")
                return False
            
            # Generate access token
            data = self.kite.generate_session(self.request_token, api_secret=self.api_secret)
            self.access_token = data["access_token"]
            self.kite.set_access_token(self.access_token)
            
            # Save access token for future use
            self._save_access_token()
            
            self.is_authenticated = True
            logger.info("✅ Successfully authenticated with Zerodha")
            return True
            
        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            return False
    
    def _start_auth_server(self):
        """Start local server to capture OAuth redirect"""
        class AuthHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(handler_self):
                if handler_self.path.startswith('/callback'):
                    # Parse request token from URL
                    parsed_url = urlparse(handler_self.path)
                    query_params = parse_qs(parsed_url.query)
                    
                    if 'request_token' in query_params:
                        self.request_token = query_params['request_token'][0]
                        
                        # Send success response
                        handler_self.send_response(200)
                        handler_self.send_header('Content-type', 'text/html')
                        handler_self.end_headers()
                        handler_self.wfile.write(b"""
                        <html>
                        <body>
                        <h2>Authentication Successful!</h2>
                        <p>You can close this window and return to the trading agent.</p>
                        </body>
                        </html>
                        """)
                    else:
                        handler_self.send_response(400)
                        handler_self.end_headers()
                        handler_self.wfile.write(b"Authentication failed")
                        
                handler_self.log_message = lambda *args: None  # Suppress logs
        
        # Start server in background thread
        def run_server():
            with socketserver.TCPServer(("", 5000), AuthHandler) as httpd:
                httpd.timeout = 300  # 5 minutes
                httpd.handle_request()
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
    
    def _save_access_token(self):
        """Save access token to file"""
        try:
            with open('.tokens', 'w') as f:
                f.write(f"access_token={self.access_token}\n")
                f.write(f"timestamp={int(time.time())}\n")
        except Exception as e:
            logger.warning(f"Failed to save access token: {e}")
    
    def _load_access_token(self) -> bool:
        """Load access token from file"""
        try:
            with open('.tokens', 'r') as f:
                lines = f.readlines()
                
            token_data = {}
            for line in lines:
                key, value = line.strip().split('=', 1)
                token_data[key] = value
            
            # Check if token is still valid (tokens expire daily)
            token_timestamp = int(token_data.get('timestamp', 0))
            current_time = int(time.time())
            
            if current_time - token_timestamp > 86400:  # 24 hours
                logger.info("Access token expired")
                return False
            
            self.access_token = token_data.get('access_token')
            if self.access_token:
                self.kite.set_access_token(self.access_token)
                self.is_authenticated = True
                return True
                
        except FileNotFoundError:
            logger.info("No saved access token found")
        except Exception as e:
            logger.warning(f"Failed to load access token: {e}")
        
        return False
    
    def get_profile(self) -> Dict[str, Any]:
        """Get user profile information"""
        try:
            return self.kite.profile()
        except Exception as e:
            logger.error(f"Failed to get profile: {e}")
            return {}
    
    def get_margins(self) -> Dict[str, Any]:
        """Get account margins"""
        try:
            return self.kite.margins()
        except Exception as e:
            logger.error(f"Failed to get margins: {e}")
            return {}
    
    def get_holdings(self) -> List[Dict[str, Any]]:
        """Get current holdings"""
        try:
            return self.kite.holdings()
        except Exception as e:
            logger.error(f"Failed to get holdings: {e}")
            return []
    
    def get_positions(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get current positions"""
        try:
            return self.kite.positions()
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return {'net': [], 'day': []}
    
    def get_orders(self) -> List[Dict[str, Any]]:
        """Get order history"""
        try:
            return self.kite.orders()
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return []
    
    def get_quote(self, instruments: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get live quotes for instruments"""
        try:
            return self.kite.quote(instruments)
        except Exception as e:
            logger.error(f"Failed to get quotes: {e}")
            return {}
    
    def get_historical_data(self, instrument_token: str, from_date: datetime, 
                          to_date: datetime, interval: str = "minute") -> List[Dict[str, Any]]:
        """Get historical data for an instrument"""
        try:
            return self.kite.historical_data(
                instrument_token=int(instrument_token),
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
        except Exception as e:
            logger.error(f"Failed to get historical data: {e}")
            return []
    
    def place_order(self, tradingsymbol: str, exchange: str, transaction_type: str,
                   quantity: int, order_type: str, price: Optional[float] = None,
                   product: str = "MIS", validity: str = "DAY",
                   disclosed_quantity: Optional[int] = None,
                   trigger_price: Optional[float] = None,
                   squareoff: Optional[float] = None,
                   stoploss: Optional[float] = None) -> Optional[str]:
        """
        Place an order
        Returns order_id if successful, None otherwise
        """
        try:
            order_id = self.kite.place_order(
                tradingsymbol=tradingsymbol,
                exchange=exchange,
                transaction_type=transaction_type,
                quantity=quantity,
                order_type=order_type,
                price=price,
                product=product,
                validity=validity,
                disclosed_quantity=disclosed_quantity,
                trigger_price=trigger_price,
                squareoff=squareoff,
                stoploss=stoploss
            )
            
            logger.info(f"✅ Order placed: {order_id}")
            return order_id
            
        except Exception as e:
            logger.error(f"❌ Failed to place order: {e}")
            return None
    
    def modify_order(self, order_id: str, **kwargs) -> bool:
        """Modify an existing order"""
        try:
            self.kite.modify_order(order_id=order_id, **kwargs)
            logger.info(f"✅ Order modified: {order_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to modify order {order_id}: {e}")
            return False
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            self.kite.cancel_order(order_id=order_id)
            logger.info(f"✅ Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to cancel order {order_id}: {e}")
            return False
    
    def get_instruments(self, exchange: str = "NSE") -> List[Dict[str, Any]]:
        """Get list of instruments"""
        try:
            return self.kite.instruments(exchange=exchange)
        except Exception as e:
            logger.error(f"Failed to get instruments: {e}")
            return []
    
    def is_market_open(self) -> bool:
        """Check if market is currently open"""
        now = datetime.now()
        weekday = now.weekday()
        
        # Check if it's a weekday (0=Monday, 6=Sunday)
        if weekday >= 5:  # Saturday or Sunday
            return False
        
        # Check time (9:15 AM to 3:30 PM)
        current_time = now.strftime("%H:%M")
        return Config.MARKET_OPEN_TIME <= current_time <= Config.MARKET_CLOSE_TIME
    
    def get_available_margin(self) -> float:
        """Get available margin for trading"""
        try:
            margins = self.get_margins()
            equity_margin = margins.get('equity', {})
            return float(equity_margin.get('available', {}).get('cash', 0))
        except Exception as e:
            logger.error(f"Failed to get available margin: {e}")
            return 0.0 