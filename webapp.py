#!/usr/bin/env python3
"""
AI Trading Agent - Full Web Application
Modern web interface with real-time dashboard and trading controls
"""
import os
import json
import asyncio
import logging
import ssl
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import webbrowser
import threading
import time
from pathlib import Path

# Global SSL fix for development environment
import urllib3
import requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Disable SSL verification globally for development
ssl._create_default_https_context = ssl._create_unverified_context

# Comprehensive SSL bypass for development environment

# Monkey patch requests to disable SSL verification globally
original_request = requests.Session.request
original_get = requests.get
original_post = requests.post

def patched_request(self, method, url, **kwargs):
    kwargs['verify'] = False
    return original_request(self, method, url, **kwargs)

def patched_get(*args, **kwargs):
    kwargs['verify'] = False
    return original_get(*args, **kwargs)

def patched_post(*args, **kwargs):
    kwargs['verify'] = False
    return original_post(*args, **kwargs)

requests.Session.request = patched_request
requests.get = patched_get
requests.post = patched_post

# Also patch httpx if it's being used
try:
    import httpx
    original_httpx_get = httpx.get
    original_httpx_post = httpx.post
    
    def patched_httpx_get(*args, **kwargs):
        kwargs['verify'] = False
        return original_httpx_get(*args, **kwargs)
    
    def patched_httpx_post(*args, **kwargs):
        kwargs['verify'] = False
        return original_httpx_post(*args, **kwargs)
    
    httpx.get = patched_httpx_get
    httpx.post = patched_httpx_post
except:
    pass

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

# Try to import trading components
try:
    from kiteconnect import KiteConnect
    KITE_AVAILABLE = True
except ImportError:
    KITE_AVAILABLE = False

# Import real trading engine
try:
    from src.trading_engine import TradingEngine
    TRADING_ENGINE_AVAILABLE = True
except ImportError:
    TRADING_ENGINE_AVAILABLE = False
    TradingEngine = None

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="AI Trading Agent",
    description="Automated Intraday Trading Platform",
    version="1.0.0"
)

# Static files and templates
static_dir = Path("static")
templates_dir = Path("templates")
static_dir.mkdir(exist_ok=True)
templates_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Global state
class TradingState:
    def __init__(self):
        self.is_authenticated = False
        self.is_trading = False
        self.api_key = None
        self.api_secret = None
        self.access_token = None
        self.kite_client = None
        self.daily_budget = 10000
        self.budget_used = 0
        self.daily_pnl = 0
        self.trades = []
        self.positions = []
        self.active_connections = []
        self.trading_thread = None
        self.auto_start_enabled = False
        self.scheduler_thread = None
        # Real trading engine
        self.trading_engine = None
        self.use_real_trading = True  # Set to False for simulation mode
    
    def to_dict(self):
        return {
            'is_authenticated': self.is_authenticated,
            'is_trading': self.is_trading,
            'daily_budget': self.daily_budget,
            'budget_used': self.budget_used,
            'daily_pnl': self.daily_pnl,
            'trades_count': len(self.trades),
            'positions_count': len(self.positions),
            'market_open': self.is_market_open(),
            'auto_start_enabled': self.auto_start_enabled,
            'market_status': self.get_market_status(),
            'use_real_trading': self.use_real_trading,
            'trading_engine_available': TRADING_ENGINE_AVAILABLE
        }
    
    def is_market_open(self):
        """Check if market is currently open"""
        now = datetime.now()
        
        # Check if it's a weekend
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Market hours: 9:15 AM to 3:30 PM (IST)
        market_open_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        return market_open_time <= now <= market_close_time
    
    def get_market_status(self):
        """Get detailed market status with timing information"""
        now = datetime.now()
        
        if now.weekday() >= 5:  # Weekend
            next_monday = now + timedelta(days=(7 - now.weekday()))
            next_open = next_monday.replace(hour=9, minute=15, second=0, microsecond=0)
            return {
                'status': 'Weekend',
                'message': 'Market closed for weekend',
                'next_open': next_open.strftime('%Y-%m-%d %H:%M:%S'),
                'countdown': str(next_open - now).split('.')[0]
            }
        
        market_open_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        if now < market_open_time:
            # Before market opens
            countdown = market_open_time - now
            return {
                'status': 'Pre-Market',
                'message': f'Market opens at 9:15 AM',
                'next_open': market_open_time.strftime('%Y-%m-%d %H:%M:%S'),
                'countdown': str(countdown).split('.')[0]
            }
        elif now > market_close_time:
            # After market closes
            tomorrow = now + timedelta(days=1)
            if tomorrow.weekday() >= 5:  # If tomorrow is weekend
                days_to_monday = 7 - tomorrow.weekday()
                next_open = tomorrow + timedelta(days=days_to_monday)
            else:
                next_open = tomorrow
            next_open = next_open.replace(hour=9, minute=15, second=0, microsecond=0)
            
            return {
                'status': 'Post-Market',
                'message': 'Market closed for the day',
                'next_open': next_open.strftime('%Y-%m-%d %H:%M:%S'),
                'countdown': str(next_open - now).split('.')[0]
            }
        else:
            # Market is open
            time_to_close = market_close_time - now
            return {
                'status': 'Open',
                'message': f'Market closes at 3:30 PM',
                'next_close': market_close_time.strftime('%Y-%m-%d %H:%M:%S'),
                'countdown': str(time_to_close).split('.')[0]
            }
    
    def save_access_token(self):
        """Save access token to file for persistence"""
        try:
            if self.access_token:
                with open('.tokens', 'w') as f:
                    f.write(f"access_token={self.access_token}\n")
                    f.write(f"timestamp={int(time.time())}\n")
                logger.info("Access token saved successfully")
        except Exception as e:
            logger.warning(f"Failed to save access token: {e}")

trading_state = TradingState()

# WebSocket manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with dashboard"""
    return templates.TemplateResponse(
        "dashboard.html", 
        {
            "request": request,
            "state": trading_state.to_dict(),
            "kite_available": KITE_AVAILABLE
        }
    )

@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    """Setup and authentication page"""
    return templates.TemplateResponse(
        "setup.html",
        {
            "request": request,
            "state": trading_state.to_dict(),
            "kite_available": KITE_AVAILABLE
        }
    )

@app.get("/manual-auth", response_class=HTMLResponse)
async def manual_auth_page(request: Request):
    """Manual authentication page"""
    with open("manual_auth.html", "r", encoding='utf-8') as f:
        content = f.read()
    return HTMLResponse(content=content)

class ManualAuthRequest(BaseModel):
    api_key: str
    api_secret: str
    request_token: str

@app.post("/api/manual_auth")
async def manual_authenticate(auth_data: ManualAuthRequest):
    """Manual authentication with request token"""
    try:
        if not KITE_AVAILABLE:
            raise HTTPException(400, "KiteConnect not available")
        
        # Initialize Kite client with SSL bypass
        kite = KiteConnect(api_key=auth_data.api_key)
        
        # SSL bypass is handled globally by the monkey patch at the top of the file
        
        # Generate access token
        data = kite.generate_session(auth_data.request_token, api_secret=auth_data.api_secret)
        access_token = data["access_token"]
        
        # Set access token and test connection
        kite.set_access_token(access_token)
        profile = kite.profile()
        
        # Update trading state
        trading_state.api_key = auth_data.api_key
        trading_state.api_secret = auth_data.api_secret
        trading_state.access_token = access_token
        trading_state.kite_client = kite
        trading_state.is_authenticated = True
        
        # Get margin info
        try:
            margins = kite.margins()
            equity_margin = margins.get('equity', {})
            available_cash = equity_margin.get('available', {}).get('cash', 0)
        except:
            available_cash = 0
        
        # Save to .env file
        env_content = f"""# Zerodha Kite API Configuration
KITE_API_KEY={auth_data.api_key}
KITE_API_SECRET={auth_data.api_secret}
KITE_ACCESS_TOKEN={access_token}

# Trading Configuration
MAX_DAILY_BUDGET=10000
RISK_PER_TRADE=0.02
MAX_POSITIONS=5

# Optional: Telegram Bot for notifications
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Market Data Configuration
USE_LIVE_DATA=true
"""
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(env_content)
        
        # Save tokens to persistent storage
        trading_state.save_access_token()
        
        logger.info(f"Manual authentication successful for {profile.get('user_name', 'Unknown')}")
        
        # Broadcast success
        await manager.broadcast({
            "type": "auth_success",
            "user": profile.get("user_name", "Trader"),
            "message": "Manual authentication successful!"
        })
        
        return JSONResponse({
            "success": True,
            "user_name": profile.get("user_name", "Trader"),
            "margin": f"{available_cash:.2f}",
            "message": "Authentication successful!"
        })
        
    except Exception as e:
        logger.error(f"Manual authentication failed: {e}")
        return JSONResponse({
            "success": False,
            "message": str(e)
        }, status_code=400)

@app.post("/api/configure")
async def configure_api(
    api_key: str = Form(...),
    api_secret: str = Form(...)
):
    """Configure API credentials"""
    try:
        # Validate inputs
        if len(api_key) < 10 or len(api_secret) < 10:
            raise HTTPException(400, "Invalid API credentials")
        
        # Save configuration
        trading_state.api_key = api_key
        trading_state.api_secret = api_secret
        # Keep existing daily_budget or use default
        if not trading_state.daily_budget:
            trading_state.daily_budget = 10000
        
        # Save to .env file
        env_content = f"""# Zerodha Kite API Configuration
KITE_API_KEY={api_key}
KITE_API_SECRET={api_secret}

# Trading Configuration
MAX_DAILY_BUDGET={trading_state.daily_budget}
RISK_PER_TRADE=0.02
MAX_POSITIONS=5

# Optional: Telegram Bot for notifications
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Market Data Configuration
USE_LIVE_DATA=true
"""
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(env_content)
        
        return JSONResponse({"success": True, "message": "Configuration saved successfully"})
    
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        raise HTTPException(500, str(e))

class BudgetRequest(BaseModel):
    daily_budget: float

@app.post("/api/update_budget")
async def update_budget(budget_data: BudgetRequest):
    """Update daily trading budget"""
    try:
        # Validate budget amount
        if budget_data.daily_budget < 5000:
            raise HTTPException(400, "Minimum daily budget is ₹5,000")
        
        if budget_data.daily_budget > 1000000:
            raise HTTPException(400, "Maximum daily budget is ₹10,00,000")
        
        # Stop trading if currently running and budget is reduced below current usage
        if trading_state.is_trading and budget_data.daily_budget < trading_state.budget_used:
            # Auto-stop trading if new budget is less than current usage
            trading_state.is_trading = False
            if trading_state.trading_thread:
                trading_state.trading_thread = None
            
            logger.warning(f"Trading stopped automatically due to budget reduction. "
                         f"New budget: ₹{budget_data.daily_budget}, Used: ₹{trading_state.budget_used}")
        
        # Update budget in both trading state and config
        old_budget = trading_state.daily_budget
        trading_state.daily_budget = budget_data.daily_budget
        
        # Update the global config so risk manager uses new budget
        from config import Config
        Config.MAX_DAILY_BUDGET = budget_data.daily_budget
        
        # Log the change
        logger.info(f"Daily budget updated from ₹{old_budget} to ₹{budget_data.daily_budget}")
        
        # Broadcast update to connected clients
        await manager.broadcast({
            "type": "budget_update",
            "daily_budget": trading_state.daily_budget,
            "budget_used": trading_state.budget_used,
            "is_trading": trading_state.is_trading
        })
        
        return JSONResponse({
            "success": True, 
            "message": f"Daily budget updated to ₹{budget_data.daily_budget:,.2f}",
            "daily_budget": trading_state.daily_budget,
            "budget_used": trading_state.budget_used
        })
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Budget update error: {e}")
        raise HTTPException(500, str(e))

@app.post("/api/authenticate")
async def authenticate():
    """Start Zerodha authentication process"""
    try:
        if not KITE_AVAILABLE:
            return JSONResponse({
                "success": False, 
                "message": "KiteConnect not available",
                "login_url": "https://developers.kite.trade"
            })
        
        if not trading_state.api_key:
            raise HTTPException(400, "API key not configured")
        
        # Initialize Kite client with SSL bypass
        trading_state.kite_client = KiteConnect(api_key=trading_state.api_key)
        
        # SSL bypass is handled globally by the monkey patch at the top of the file
        
        login_url = trading_state.kite_client.login_url()
        
        return JSONResponse({
            "success": True,
            "login_url": login_url,
            "message": "Authentication started"
        })
    
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return JSONResponse({
            "success": False,
            "message": f"Authentication failed: {str(e)}",
            "login_url": "https://developers.kite.trade"
        }, status_code=500)

@app.get("/callback")
async def auth_callback(request: Request):
    """Handle Zerodha OAuth callback"""
    try:
        # Get parameters from query string
        request_token = request.query_params.get("request_token")
        status = request.query_params.get("status", "success")
        error = request.query_params.get("error")
        
        logger.info(f"Callback received - Status: {status}, Token: {request_token}, Error: {error}")
        
        if error:
            logger.error(f"Authentication error from Zerodha: {error}")
            return RedirectResponse("/?error=auth_error")
        
        if status != "success" or not request_token:
            logger.error(f"Invalid callback - Status: {status}, Token present: {bool(request_token)}")
            return RedirectResponse("/?error=auth_failed")
        
        if not trading_state.kite_client or not trading_state.api_secret:
            logger.error("Invalid state - no kite client or API secret")
            return RedirectResponse("/?error=invalid_state")
        
        # Generate access token
        logger.info("Generating access token...")
        
        # SSL bypass is handled globally by the monkey patch at the top of the file
        
        try:
            data = trading_state.kite_client.generate_session(
                request_token, 
                api_secret=trading_state.api_secret
            )
            
            trading_state.access_token = data["access_token"]
            trading_state.kite_client.set_access_token(trading_state.access_token)
            trading_state.is_authenticated = True
            
            # Get user profile
            try:
                profile = trading_state.kite_client.profile()
                user_name = profile.get("user_name", "Trader")
                logger.info(f"Authentication successful for user: {user_name}")
            except Exception as e:
                logger.warning(f"Could not fetch profile: {e}")
                user_name = "Trader"
            
            # Broadcast authentication success
            await manager.broadcast({
                "type": "auth_success",
                "user": user_name,
                "message": "Authentication successful!"
            })
            
            return RedirectResponse("/?auth=success")
            
        except Exception as e:
            logger.error(f"Token generation failed: {e}")
            return RedirectResponse(f"/?error=token_failed")
    
    except Exception as e:
        logger.error(f"Callback error: {e}")
        return RedirectResponse(f"/?error=callback_failed")

@app.post("/api/start_trading")
async def start_trading():
    """Start automated trading with market hours validation"""
    try:
        if not trading_state.is_authenticated:
            raise HTTPException(400, "Not authenticated")
        
        if trading_state.is_trading:
            raise HTTPException(400, "Trading already active")
        
        # Check if market is open
        if not trading_state.is_market_open():
            market_status = trading_state.get_market_status()
            raise HTTPException(400, f"Cannot start trading: Market is {market_status['status']}. {market_status['message']}")
        
        trading_state.is_trading = True
        
        # Choose real trading or simulation
        if trading_state.use_real_trading and TRADING_ENGINE_AVAILABLE:
            # Initialize real trading engine
            if not trading_state.trading_engine:
                trading_state.trading_engine = TradingEngine()
            
            # Start real trading in background
            trading_state.trading_thread = threading.Thread(
                target=run_real_trading,
                daemon=True
            )
            trading_state.trading_thread.start()
            
            message = "🚀 REAL automated trading started!"
            logger.info("Real trading engine started")
        else:
            # Fallback to simulation
            trading_state.trading_thread = threading.Thread(
                target=run_trading_simulation,
                daemon=True
            )
            trading_state.trading_thread.start()
            
            message = "⚠️ Simulation mode - No real trades will be placed"
            logger.info("Trading simulation started")
        
        await manager.broadcast({
            "type": "trading_started",
            "message": message
        })
        
        return JSONResponse({"success": True, "message": message})
    
    except Exception as e:
        logger.error(f"Start trading error: {e}")
        raise HTTPException(500, str(e))

@app.post("/api/stop_trading")
async def stop_trading():
    """Stop automated trading"""
    try:
        trading_state.is_trading = False
        
        # Stop real trading engine if active
        if trading_state.trading_engine:
            trading_state.trading_engine.stop()
        
        await manager.broadcast({
            "type": "trading_stopped",
            "message": "Automated trading stopped"
        })
        
        return JSONResponse({"success": True, "message": "Trading stopped"})
    
    except Exception as e:
        logger.error(f"Stop trading error: {e}")
        raise HTTPException(500, str(e))

@app.post("/api/emergency_square_off")
async def emergency_square_off():
    """Emergency square off all positions"""
    try:
        if not trading_state.is_authenticated:
            raise HTTPException(400, "Not authenticated")
        
        success = False
        message = ""
        
        if trading_state.use_real_trading and trading_state.trading_engine:
            # Real trading engine square off
            success = trading_state.trading_engine.force_square_off_all()
            message = "🚨 Emergency square off executed for all real positions" if success else "❌ Failed to square off positions"
        else:
            # Simulation mode - just clear positions
            trading_state.positions = []
            trading_state.daily_pnl = 0
            trading_state.budget_used = 0
            success = True
            message = "🚨 All simulated positions cleared"
        
        await manager.broadcast({
            "type": "emergency_square_off",
            "message": message,
            "success": success
        })
        
        return JSONResponse({
            "success": success,
            "message": message
        })
    
    except Exception as e:
        logger.error(f"Emergency square off error: {e}")
        raise HTTPException(500, str(e))

class AutoStartRequest(BaseModel):
    enabled: bool

@app.post("/api/toggle_auto_start")
async def toggle_auto_start(auto_start_data: AutoStartRequest):
    """Toggle auto-start trading when market opens"""
    try:
        if not trading_state.is_authenticated:
            raise HTTPException(400, "Not authenticated")
        
        trading_state.auto_start_enabled = auto_start_data.enabled
        
        if auto_start_data.enabled:
            # Start the scheduler if not already running
            if not trading_state.scheduler_thread or not trading_state.scheduler_thread.is_alive():
                trading_state.scheduler_thread = threading.Thread(
                    target=market_scheduler,
                    daemon=True
                )
                trading_state.scheduler_thread.start()
            
            message = "Auto-start enabled. Trading will begin automatically when market opens."
            logger.info("Auto-start trading enabled")
        else:
            message = "Auto-start disabled. Manual trading start required."
            logger.info("Auto-start trading disabled")
        
        # Broadcast update to connected clients
        await manager.broadcast({
            "type": "auto_start_update",
            "enabled": trading_state.auto_start_enabled,
            "message": message
        })
        
        return JSONResponse({
            "success": True, 
            "message": message,
            "auto_start_enabled": trading_state.auto_start_enabled
        })
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auto-start toggle error: {e}")
        raise HTTPException(500, str(e))

class TradingModeRequest(BaseModel):
    use_real_trading: bool

@app.post("/api/toggle_trading_mode")
async def toggle_trading_mode(mode_data: TradingModeRequest):
    """Toggle between real trading and simulation mode"""
    try:
        if trading_state.is_trading:
            raise HTTPException(400, "Cannot change mode while trading is active")
        
        trading_state.use_real_trading = mode_data.use_real_trading
        
        mode_text = "REAL TRADING" if mode_data.use_real_trading else "SIMULATION"
        warning = " ⚠️ REAL MONEY WILL BE USED!" if mode_data.use_real_trading else " (Safe demo mode)"
        
        message = f"Trading mode set to: {mode_text}{warning}"
        
        # Broadcast update to connected clients
        await manager.broadcast({
            "type": "trading_mode_update",
            "use_real_trading": trading_state.use_real_trading,
            "message": message
        })
        
        return JSONResponse({
            "success": True, 
            "message": message,
            "use_real_trading": trading_state.use_real_trading
        })
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trading mode toggle error: {e}")
        raise HTTPException(500, str(e))

# Market scheduler for auto-start
def market_scheduler():
    """Background scheduler to monitor market open/close and auto-start trading"""
    logger.info("Market scheduler started")
    
    while trading_state.auto_start_enabled:
        try:
            current_time = datetime.now()
            market_status = trading_state.get_market_status()
            
            # Check if market just opened and auto-start is enabled
            if (market_status['status'] == 'Open' and 
                not trading_state.is_trading and 
                trading_state.is_authenticated):
                
                # Check if we're within the first few minutes of market open
                market_open_time = current_time.replace(hour=9, minute=15, second=0, microsecond=0)
                time_since_open = current_time - market_open_time
                
                # Auto-start within first 5 minutes of market open
                if time_since_open.total_seconds() <= 300:  # 5 minutes
                    logger.info("Auto-starting trading as market has opened")
                    
                    trading_state.is_trading = True
                    trading_state.trading_thread = threading.Thread(
                        target=run_trading_simulation,
                        daemon=True
                    )
                    trading_state.trading_thread.start()
                    
                    # Broadcast auto-start notification
                    asyncio.run(manager.broadcast({
                        "type": "auto_start_triggered",
                        "message": "Trading auto-started as market opened"
                    }))
            
            # Auto-stop trading when market closes
            elif (market_status['status'] in ['Post-Market', 'Weekend'] and 
                  trading_state.is_trading):
                
                logger.info("Auto-stopping trading as market has closed")
                trading_state.is_trading = False
                
                # Broadcast auto-stop notification
                asyncio.run(manager.broadcast({
                    "type": "auto_stop_triggered",
                    "message": f"Trading auto-stopped: {market_status['message']}"
                }))
            
            # Check every 30 seconds
            time.sleep(30)
            
        except Exception as e:
            logger.error(f"Market scheduler error: {e}")
            time.sleep(60)  # Wait longer on error
    
    logger.info("Market scheduler stopped")

@app.get("/api/status")
async def get_status():
    """Get current trading status"""
    return JSONResponse({
        "success": True,
        "data": {
            **trading_state.to_dict(),
            "trades": trading_state.trades[-10:],  # Last 10 trades
            "positions": trading_state.positions
        }
    })

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    await manager.connect(websocket)
    try:
        while True:
            # Send periodic updates
            await websocket.send_json({
                "type": "status_update",
                "data": trading_state.to_dict()
            })
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Real trading function
def run_real_trading():
    """Run real automated trading using TradingEngine"""
    try:
        logger.info("🚀 Starting REAL trading engine...")
        
        # Initialize trading engine if not done
        if not trading_state.trading_engine.initialize():
            logger.error("Failed to initialize trading engine")
            trading_state.is_trading = False
            asyncio.run(manager.broadcast({
                "type": "trading_stopped",
                "message": "❌ Failed to initialize trading engine"
            }))
            return
        
        logger.info("✅ Real trading engine initialized successfully")
        
        # Broadcast successful initialization
        asyncio.run(manager.broadcast({
            "type": "trading_started",
            "message": "🚀 Real trading engine is now active and analyzing markets"
        }))
        
        # Start the real trading engine
        # Note: TradingEngine.start() is blocking, so we need to modify it slightly
        trading_state.trading_engine.daily_budget = trading_state.daily_budget
        
        # Run trading loop
        while trading_state.is_trading:
            try:
                # Check if market is still open
                if not trading_state.is_market_open():
                    logger.info("Market closed during trading session - stopping")
                    trading_state.is_trading = False
                    asyncio.run(manager.broadcast({
                        "type": "market_closed_stop",
                        "message": "Trading stopped - Market closed"
                    }))
                    break
                
                # Get current status from trading engine
                status = trading_state.trading_engine.get_status()
                
                # Update trading state with real data
                if status:
                    risk_summary = status.get('risk_summary', {})
                    trading_state.daily_pnl = risk_summary.get('daily_pnl', 0)
                    trading_state.budget_used = risk_summary.get('budget_used', 0)
                    
                    # Broadcast status update
                    asyncio.run(manager.broadcast({
                        "type": "status_update",
                        "data": {
                            "daily_pnl": trading_state.daily_pnl,
                            "budget_used": trading_state.budget_used,
                            "trades_count": len(trading_state.trades),
                            "positions_count": status.get('monitoring_positions', 0)
                        }
                    }))
                
                # Run one iteration of analysis and trading
                trading_state.trading_engine._analyze_and_trade()
                
                # Check positions
                trading_state.trading_engine._monitor_positions()
                
                # Risk check
                trading_state.trading_engine._risk_check()
                
                # Sleep between iterations
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in real trading loop: {e}")
                time.sleep(30)
        
        logger.info("🛑 Real trading engine stopped")
        
    except Exception as e:
        logger.error(f"Real trading error: {e}")
        trading_state.is_trading = False
        asyncio.run(manager.broadcast({
            "type": "trading_stopped",
            "message": f"❌ Real trading error: {str(e)}"
        }))

# Background trading simulation
def run_trading_simulation():
    """Simulate trading activity"""
    import random
    
    stocks = ['RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK']
    
    while trading_state.is_trading:
        try:
            # Check if market is still open (stop trading if market closes)
            if not trading_state.is_market_open():
                logger.info("Market closed during trading session - stopping automatically")
                trading_state.is_trading = False
                asyncio.run(manager.broadcast({
                    "type": "market_closed_stop",
                    "message": "Trading stopped automatically - Market closed"
                }))
                break
            
            # Simulate market analysis and trade execution
            if random.random() > 0.7:  # 30% chance of trade
                stock = random.choice(stocks)
                action = random.choice(['BUY', 'SELL'])
                quantity = random.randint(1, 10)
                price = random.uniform(100, 3000)
                
                trade = {
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'symbol': stock,
                    'action': action,
                    'quantity': quantity,
                    'price': round(price, 2),
                    'value': round(quantity * price, 2)
                }
                
                trading_state.trades.append(trade)
                
                # Update budget used (for BUY orders)
                if action == 'BUY':
                    trade_value = quantity * price
                    trading_state.budget_used += trade_value
                    
                    # Check if budget exceeded (safety check)
                    if trading_state.budget_used > trading_state.daily_budget:
                        logger.warning(f"Budget exceeded! Used: ₹{trading_state.budget_used:.2f}, Budget: ₹{trading_state.daily_budget:.2f}")
                        trading_state.is_trading = False
                        break
                
                # Update P&L
                pnl_change = random.uniform(-50, 100)
                trading_state.daily_pnl += pnl_change
                
                # Broadcast trade update
                asyncio.run(manager.broadcast({
                    "type": "new_trade",
                    "trade": trade,
                    "pnl": trading_state.daily_pnl
                }))
            
            time.sleep(5)  # Wait 5 seconds between checks
            
        except Exception as e:
            logger.error(f"Trading simulation error: {e}")
            time.sleep(10)

# Create templates and static files
def create_web_files():
    """Create HTML templates and CSS files"""
    
    # Dashboard template
    dashboard_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Trading Agent - Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <link href="/static/style.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="fas fa-robot"></i> AI Trading Agent
            </a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/setup">
                    <i class="fas fa-cog"></i> Setup
                </a>
            </div>
        </div>
    </nav>

    <div class="container-fluid mt-4">
        <!-- Status Cards -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card bg-primary text-white">
                    <div class="card-body">
                        <div class="d-flex justify-content-between">
                            <div>
                                <h6>Trading Status</h6>
                                <h4 id="trading-status">
                                    {% if state.is_trading %}
                                        <i class="fas fa-play-circle text-success"></i> Running
                                    {% else %}
                                        <i class="fas fa-stop-circle text-danger"></i> Stopped
                                    {% endif %}
                                </h4>
                            </div>
                            <i class="fas fa-chart-line fa-2x"></i>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-3">
                <div class="card bg-success text-white">
                    <div class="card-body">
                        <div class="d-flex justify-content-between">
                            <div>
                                <h6>Daily P&L</h6>
                                <h4 id="daily-pnl">₹{{ "%.2f"|format(state.daily_pnl) }}</h4>
                            </div>
                            <i class="fas fa-rupee-sign fa-2x"></i>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-3">
                <div class="card bg-info text-white">
                    <div class="card-body">
                        <div class="d-flex justify-content-between">
                            <div>
                                <h6>Total Trades</h6>
                                <h4 id="total-trades">{{ state.trades_count }}</h4>
                            </div>
                            <i class="fas fa-exchange-alt fa-2x"></i>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-3">
                <div class="card bg-warning text-white">
                    <div class="card-body">
                        <div class="d-flex justify-content-between">
                            <div>
                                <h6>Open Positions</h6>
                                <h4 id="open-positions">{{ state.positions_count }}</h4>
                            </div>
                            <i class="fas fa-briefcase fa-2x"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="row">
            <!-- Trading Controls -->
            <div class="col-md-4">
                <!-- Daily Budget Control -->
                <div class="card mb-3">
                    <div class="card-header bg-warning text-dark">
                        <h5><i class="fas fa-rupee-sign"></i> Daily Trading Budget</h5>
                    </div>
                    <div class="card-body">
                        <form id="budget-form">
                            <div class="mb-3">
                                <label class="form-label">Set Daily Budget (₹)</label>
                                <div class="input-group">
                                    <span class="input-group-text">₹</span>
                                    <input type="number" class="form-control" id="daily-budget-input" 
                                           name="daily_budget" value="{{ state.daily_budget or 10000 }}" 
                                           min="5000" max="1000000" required>
                                </div>
                                <div class="form-text">
                                    Minimum: ₹5,000 | Current Used: <span data-budget-used>₹{{ "%.2f"|format(state.budget_used or 0) }}</span>
                                </div>
                            </div>
                            
                            <button type="submit" class="btn btn-warning w-100">
                                <i class="fas fa-save"></i> Update Budget
                            </button>
                        </form>
                        
                        <!-- Budget Progress -->
                        <div class="mt-3">
                            <div class="d-flex justify-content-between">
                                <small>Budget Used</small>
                                <small data-budget-percentage>{{ "%.1f"|format(((state.budget_used or 0) / (state.daily_budget or 10000)) * 100) }}%</small>
                            </div>
                            <div class="progress">
                                <div class="progress-bar {% if ((state.budget_used or 0) / (state.daily_budget or 10000)) > 0.8 %}bg-danger{% elif ((state.budget_used or 0) / (state.daily_budget or 10000)) > 0.6 %}bg-warning{% else %}bg-success{% endif %}" 
                                     style="width: {{ "%.1f"|format(((state.budget_used or 0) / (state.daily_budget or 10000)) * 100) }}%">
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Trading Controls -->
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-controls"></i> Trading Controls</h5>
                    </div>
                    <div class="card-body">
                        {% if not state.is_authenticated %}
                            <div class="alert alert-warning">
                                <i class="fas fa-exclamation-triangle"></i>
                                Please complete setup and authentication first.
                            </div>
                            <a href="/setup" class="btn btn-primary">
                                <i class="fas fa-cog"></i> Go to Setup
                            </a>
                        {% else %}
                            <div class="d-grid gap-2">
                                {% if not state.is_trading %}
                                    {% if state.use_real_trading %}
                                        <button class="btn btn-danger btn-lg" onclick="startTrading()">
                                            <i class="fas fa-play"></i> Start REAL Trading ⚠️
                                        </button>
                                    {% else %}
                                        <button class="btn btn-success btn-lg" onclick="startTrading()">
                                            <i class="fas fa-play"></i> Start Simulation
                                        </button>
                                    {% endif %}
                                {% else %}
                                    <button class="btn btn-danger btn-lg" onclick="stopTrading()">
                                        <i class="fas fa-stop"></i> Stop Trading
                                    </button>
                                {% endif %}
                                
                                <button class="btn btn-warning" onclick="squareOffAll()">
                                    <i class="fas fa-times-circle"></i> Emergency Square Off
                                </button>
                            </div>
                        {% endif %}
                        
                        <hr>
                        
                        <!-- Market Status -->
                        <div class="alert {% if state.market_open %}alert-success{% else %}alert-warning{% endif %} p-2 mb-3">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <strong><i class="fas fa-clock"></i> Market: {{ state.market_status.status }}</strong>
                                    <br><small>{{ state.market_status.message }}</small>
                                </div>
                                <div class="text-end">
                                    <small class="text-muted">
                                        {% if state.market_status.countdown %}
                                            {{ state.market_status.countdown }}
                                        {% endif %}
                                    </small>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Trading Mode Control -->
                        {% if state.trading_engine_available %}
                        <div class="mb-3">
                            <div class="form-check form-switch">
                                <input class="form-check-input" type="checkbox" id="tradingModeToggle" 
                                       {% if state.use_real_trading %}checked{% endif %}
                                       {% if state.is_trading %}disabled{% endif %}>
                                <label class="form-check-label" for="tradingModeToggle">
                                    <strong>Real Trading Mode</strong>
                                </label>
                            </div>
                            <small class="text-muted">
                                {% if state.use_real_trading %}
                                    <i class="fas fa-exclamation-triangle text-warning"></i> <strong>REAL MONEY WILL BE USED!</strong>
                                {% else %}
                                    <i class="fas fa-info-circle text-info"></i> Simulation mode - safe for testing
                                {% endif %}
                            </small>
                        </div>
                        {% endif %}
                        
                        <!-- Auto-Start Control -->
                        {% if state.is_authenticated %}
                        <div class="mb-3">
                            <div class="form-check form-switch">
                                <input class="form-check-input" type="checkbox" id="autoStartToggle" 
                                       {% if state.auto_start_enabled %}checked{% endif %}>
                                <label class="form-check-label" for="autoStartToggle">
                                    <strong>Auto-Start at Market Open</strong>
                                </label>
                            </div>
                            <small class="text-muted">
                                {% if state.auto_start_enabled %}
                                    <i class="fas fa-check-circle text-success"></i> Trading will start automatically when market opens
                                {% else %}
                                    <i class="fas fa-times-circle text-secondary"></i> Manual start required
                                {% endif %}
                            </small>
                        </div>
                        {% endif %}
                    </div>
                </div>
            </div>

            <!-- Recent Trades -->
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-history"></i> Recent Trades</h5>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-striped" id="trades-table">
                                <thead>
                                    <tr>
                                        <th>Time</th>
                                        <th>Symbol</th>
                                        <th>Action</th>
                                        <th>Qty</th>
                                        <th>Price</th>
                                        <th>Value</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td colspan="6" class="text-center text-muted">
                                            No trades yet. Start trading to see activity.
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Live Updates -->
        <div class="row mt-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-broadcast-tower"></i> Live Updates</h5>
                    </div>
                    <div class="card-body">
                        <div id="live-updates" class="alert alert-info">
                            <i class="fas fa-info-circle"></i> Waiting for updates...
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="/static/dashboard.js"></script>
</body>
</html>
"""

    # Setup template
    setup_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Trading Agent - Setup</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <link href="/static/style.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="fas fa-robot"></i> AI Trading Agent
            </a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/">
                    <i class="fas fa-dashboard"></i> Dashboard
                </a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header">
                        <h4><i class="fas fa-cog"></i> Setup & Configuration</h4>
                    </div>
                    <div class="card-body">
                        <!-- API Configuration -->
                        <div class="mb-4">
                            <h5><i class="fas fa-key"></i> Zerodha API Configuration</h5>
                            <div class="alert alert-info">
                                <i class="fas fa-info-circle"></i>
                                Get your API credentials from 
                                <a href="https://developers.kite.trade/" target="_blank">
                                    developers.kite.trade <i class="fas fa-external-link-alt"></i>
                                </a>
                            </div>
                            
                            <form id="config-form">
                                <div class="mb-3">
                                    <label class="form-label">API Key (Consumer Key)</label>
                                    <input type="text" class="form-control" name="api_key" required>
                                </div>
                                
                                <div class="mb-3">
                                    <label class="form-label">API Secret (Consumer Secret)</label>
                                    <input type="password" class="form-control" name="api_secret" required>
                                </div>
                                
                                <button type="submit" class="btn btn-primary">
                                    <i class="fas fa-save"></i> Save Configuration
                                </button>
                            </form>
                        </div>

                        <hr>

                        <!-- Authentication -->
                        <div class="mb-4">
                            <h5><i class="fas fa-shield-alt"></i> Authentication</h5>
                            {% if state.is_authenticated %}
                                <div class="alert alert-success">
                                    <i class="fas fa-check-circle"></i>
                                    Successfully authenticated with Zerodha!
                                </div>
                            {% else %}
                                <div class="alert alert-warning">
                                    <i class="fas fa-exclamation-triangle"></i>
                                    Authentication required to start trading.
                                </div>
                                <button class="btn btn-success" onclick="authenticate()">
                                    <i class="fas fa-sign-in-alt"></i> Authenticate with Zerodha
                                </button>
                            {% endif %}
                        </div>

                        <hr>

                        <!-- Risk Disclaimer -->
                        <div class="alert alert-danger">
                            <h6><i class="fas fa-exclamation-triangle"></i> Risk Warning</h6>
                            <p class="mb-0">
                                This system trades real money. Trading involves significant risk of loss.
                                Only use funds you can afford to lose. Start with small amounts to test the system.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="/static/setup.js"></script>
</body>
</html>
"""

    # CSS styles
    css_content = """
body {
    background-color: #f8f9fa;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.navbar-brand {
    font-weight: bold;
    font-size: 1.5rem;
}

.card {
    border: none;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    border-radius: 10px;
}

.card-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-radius: 10px 10px 0 0 !important;
    border: none;
}

.btn {
    border-radius: 8px;
    font-weight: 500;
}

.alert {
    border-radius: 8px;
    border: none;
}

.table {
    border-radius: 8px;
    overflow: hidden;
}

.bg-primary {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
}

.bg-success {
    background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%) !important;
}

.bg-info {
    background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%) !important;
}

.bg-warning {
    background: linear-gradient(135deg, #fa709a 0%, #fee140 100%) !important;
}

.bg-danger {
    background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%) !important;
}

.trading-card {
    transition: transform 0.2s;
}

.trading-card:hover {
    transform: translateY(-2px);
}

#live-updates {
    max-height: 200px;
    overflow-y: auto;
}

.status-indicator {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 5px;
}

.status-online {
    background-color: #28a745;
}

.status-offline {
    background-color: #dc3545;
}
"""

    # Dashboard JavaScript
    dashboard_js = """
// WebSocket connection for real-time updates
let ws = null;

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = function() {
        console.log('WebSocket connected');
        updateLiveStatus('Connected to live updates', 'success');
    };
    
    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
    
    ws.onclose = function() {
        console.log('WebSocket disconnected');
        updateLiveStatus('Disconnected from live updates', 'danger');
        // Attempt to reconnect after 5 seconds
        setTimeout(connectWebSocket, 5000);
    };
    
    ws.onerror = function(error) {
        console.error('WebSocket error:', error);
        updateLiveStatus('Connection error', 'warning');
    };
}

function handleWebSocketMessage(data) {
    switch(data.type) {
        case 'status_update':
            updateDashboard(data.data);
            break;
        case 'new_trade':
            addTradeToTable(data.trade);
            updatePnL(data.pnl);
            updateLiveStatus(`New trade: ${data.trade.action} ${data.trade.symbol}`, 'info');
            break;
        case 'trading_started':
            updateTradingStatus(true);
            updateLiveStatus(data.message, 'success');
            break;
        case 'trading_stopped':
            updateTradingStatus(false);
            updateLiveStatus(data.message, 'warning');
            break;
        case 'auth_success':
            updateLiveStatus(`Welcome ${data.user}! ${data.message}`, 'success');
            setTimeout(() => location.reload(), 2000);
            break;
        case 'auto_start_triggered':
            updateLiveStatus(data.message, 'success');
            updateTradingStatus(true);
            break;
        case 'auto_stop_triggered':
        case 'market_closed_stop':
            updateLiveStatus(data.message, 'warning');
            updateTradingStatus(false);
            break;
        case 'auto_start_update':
            updateLiveStatus(data.message, 'info');
            const autoStartToggle = document.getElementById('autoStartToggle');
            if (autoStartToggle) {
                autoStartToggle.checked = data.enabled;
            }
            break;
        case 'budget_update':
            updateBudgetDisplay(data.daily_budget, data.budget_used);
            if (!data.is_trading) {
                updateTradingStatus(false);
            }
            break;
        case 'trading_mode_update':
            updateLiveStatus(data.message, 'info');
            const tradingModeToggle = document.getElementById('tradingModeToggle');
            if (tradingModeToggle) {
                tradingModeToggle.checked = data.use_real_trading;
            }
            break;
        case 'emergency_square_off':
            updateLiveStatus(data.message, data.success ? 'success' : 'warning');
            if (data.success) {
                updateTradingStatus(false);
                updatePnL(0); // Reset P&L on emergency square off
                updateBudgetDisplay(trading_state.daily_budget, 0); // Reset budget used
                trading_state.positions = []; // Clear positions
                addTradeToTable({time: 'N/A', symbol: 'N/A', action: 'N/A', quantity: 0, price: 0, value: 0});
            }
            break;
    }
}

function updateDashboard(data) {
    document.getElementById('daily-pnl').textContent = `₹${data.daily_pnl.toFixed(2)}`;
    document.getElementById('total-trades').textContent = data.trades_count;
    document.getElementById('open-positions').textContent = data.positions_count;
}

function updateTradingStatus(isTrading) {
    const statusElement = document.getElementById('trading-status');
    if (isTrading) {
        statusElement.innerHTML = '<i class="fas fa-play-circle text-success"></i> Running';
    } else {
        statusElement.innerHTML = '<i class="fas fa-stop-circle text-danger"></i> Stopped';
    }
}

function updatePnL(pnl) {
    const pnlElement = document.getElementById('daily-pnl');
    pnlElement.textContent = `₹${pnl.toFixed(2)}`;
    
    // Add color based on positive/negative
    const card = pnlElement.closest('.card');
    if (pnl >= 0) {
        card.className = 'card bg-success text-white';
    } else {
        card.className = 'card bg-danger text-white';
    }
}

function addTradeToTable(trade) {
    const tbody = document.querySelector('#trades-table tbody');
    
    // Remove "no trades" message if present
    if (tbody.children.length === 1 && tbody.children[0].textContent.includes('No trades yet')) {
        tbody.innerHTML = '';
    }
    
    const row = document.createElement('tr');
    const actionClass = trade.action === 'BUY' ? 'text-success' : 'text-danger';
    
    row.innerHTML = `
        <td>${trade.time}</td>
        <td><strong>${trade.symbol}</strong></td>
        <td><span class="badge bg-${trade.action === 'BUY' ? 'success' : 'danger'}">${trade.action}</span></td>
        <td>${trade.quantity}</td>
        <td>₹${trade.price}</td>
        <td>₹${trade.value}</td>
    `;
    
    // Add to top of table
    tbody.insertBefore(row, tbody.firstChild);
    
    // Keep only last 10 trades
    while (tbody.children.length > 10) {
        tbody.removeChild(tbody.lastChild);
    }
}

function updateLiveStatus(message, type) {
    const timestamp = new Date().toLocaleTimeString();
    const alertClass = `alert-${type}`;
    const icon = type === 'success' ? 'check-circle' : 
                 type === 'danger' ? 'exclamation-circle' : 
                 type === 'warning' ? 'exclamation-triangle' : 'info-circle';
    
    document.getElementById('live-updates').innerHTML = `
        <i class="fas fa-${icon}"></i> 
        <strong>${timestamp}:</strong> ${message}
    `;
    document.getElementById('live-updates').className = `alert ${alertClass}`;
}

async function startTrading() {
    try {
        const response = await fetch('/api/start_trading', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        
        const result = await response.json();
        
        if (result.success) {
            updateLiveStatus('Starting automated trading...', 'info');
        } else {
            alert('Failed to start trading: ' + result.message);
        }
    } catch (error) {
        alert('Error starting trading: ' + error.message);
    }
}

async function stopTrading() {
    try {
        const response = await fetch('/api/stop_trading', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        
        const result = await response.json();
        
        if (result.success) {
            updateLiveStatus('Stopping automated trading...', 'warning');
        } else {
            alert('Failed to stop trading: ' + result.message);
        }
    } catch (error) {
        alert('Error stopping trading: ' + error.message);
    }
}

async function toggleAutoStart() {
    const toggle = document.getElementById('autoStartToggle');
    const enabled = toggle.checked;
    
    try {
        const response = await fetch('/api/toggle_auto_start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                enabled: enabled
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            updateLiveStatus(result.message, enabled ? 'success' : 'info');
        } else {
            alert('Failed to toggle auto-start: ' + result.message);
            // Revert toggle state on failure
            toggle.checked = !enabled;
        }
    } catch (error) {
        alert('Error toggling auto-start: ' + error.message);
        // Revert toggle state on error
        toggle.checked = !enabled;
    }
}

async function updateBudget() {
    const budgetForm = document.getElementById('budget-form');
    const formData = new FormData(budgetForm);
    const dailyBudget = parseFloat(formData.get('daily_budget'));
    
    try {
        const response = await fetch('/api/update_budget', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                daily_budget: dailyBudget
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            updateLiveStatus(result.message, 'success');
            // Update the progress bar and budget display
            updateBudgetDisplay(result.daily_budget, result.budget_used);
        } else {
            alert('Failed to update budget: ' + result.message);
        }
    } catch (error) {
        alert('Error updating budget: ' + error.message);
    }
}

function updateBudgetDisplay(dailyBudget, budgetUsed) {
    // Update the budget used text
    const budgetUsedElements = document.querySelectorAll('[data-budget-used]');
    budgetUsedElements.forEach(el => {
        el.textContent = `₹${budgetUsed.toFixed(2)}`;
    });
    
    // Update the progress bar
    const progressPercentage = (budgetUsed / dailyBudget) * 100;
    const progressBar = document.querySelector('.progress-bar');
    if (progressBar) {
        progressBar.style.width = `${progressPercentage.toFixed(1)}%`;
        
        // Update progress bar color based on usage
        progressBar.className = 'progress-bar';
        if (progressPercentage > 80) {
            progressBar.classList.add('bg-danger');
        } else if (progressPercentage > 60) {
            progressBar.classList.add('bg-warning');
        } else {
            progressBar.classList.add('bg-success');
        }
    }
    
    // Update percentage text
    const percentageElements = document.querySelectorAll('[data-budget-percentage]');
    percentageElements.forEach(el => {
        el.textContent = `${progressPercentage.toFixed(1)}%`;
    });
}

async function squareOffAll() {
    const warningText = trading_state && trading_state.use_real_trading ? 
        'Are you sure you want to square off ALL REAL POSITIONS? This cannot be undone!' :
        'Are you sure you want to clear all simulated positions?';
    
    if (confirm(warningText)) {
        try {
            updateLiveStatus('Emergency square off initiated...', 'warning');
            
            const response = await fetch('/api/emergency_square_off', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            });
            
            const result = await response.json();
            
            if (result.success) {
                updateLiveStatus(result.message, 'success');
            } else {
                updateLiveStatus(result.message, 'danger');
            }
        } catch (error) {
            updateLiveStatus('Error in emergency square off: ' + error.message, 'danger');
        }
    }
}

async function toggleTradingMode() {
    const toggle = document.getElementById('tradingModeToggle');
    const useRealTrading = toggle.checked;
    
    try {
        const response = await fetch('/api/toggle_trading_mode', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                use_real_trading: useRealTrading
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            updateLiveStatus(result.message, 'info');
            // No need to reload, the message will be broadcasted
        } else {
            alert('Failed to toggle trading mode: ' + result.message);
            // Revert toggle state on failure
            toggle.checked = !useRealTrading;
        }
    } catch (error) {
        alert('Error toggling trading mode: ' + error.message);
        // Revert toggle state on error
        toggle.checked = !useRealTrading;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    connectWebSocket();
    
    // Budget form submission
    const budgetForm = document.getElementById('budget-form');
    if (budgetForm) {
        budgetForm.addEventListener('submit', function(e) {
            e.preventDefault();
            updateBudget();
        });
    }
    
    // Auto-start toggle
    const autoStartToggle = document.getElementById('autoStartToggle');
    if (autoStartToggle) {
        autoStartToggle.addEventListener('change', toggleAutoStart);
    }

    // Trading mode toggle
    const tradingModeToggle = document.getElementById('tradingModeToggle');
    if (tradingModeToggle) {
        tradingModeToggle.addEventListener('change', toggleTradingMode);
    }
    
    // Check for URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('auth') === 'success') {
        updateLiveStatus('Authentication successful!', 'success');
    } else if (urlParams.get('error')) {
        const error = urlParams.get('error');
        updateLiveStatus(`Authentication error: ${error}`, 'danger');
    }
});
"""

    # Setup JavaScript
    setup_js = """
document.getElementById('config-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const formData = new FormData(this);
    
    try {
        const response = await fetch('/api/configure', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert('Configuration saved successfully!');
            location.reload();
        } else {
            alert('Error: ' + result.message);
        }
    } catch (error) {
        alert('Error saving configuration: ' + error.message);
    }
});

async function authenticate() {
    try {
        const response = await fetch('/api/authenticate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        
        const result = await response.json();
        
        if (result.success && result.login_url) {
            window.open(result.login_url, '_blank');
            alert('Please complete authentication in the new window and return here.');
        } else {
            alert('Error: ' + result.message);
        }
    } catch (error) {
        alert('Error starting authentication: ' + error.message);
    }
}
"""

    # Write all files
    with open("templates/dashboard.html", "w", encoding='utf-8') as f:
        f.write(dashboard_html)
    
    with open("templates/setup.html", "w", encoding='utf-8') as f:
        f.write(setup_html)
    
    with open("static/style.css", "w", encoding='utf-8') as f:
        f.write(css_content)
    
    with open("static/dashboard.js", "w", encoding='utf-8') as f:
        f.write(dashboard_js)
    
    with open("static/setup.js", "w", encoding='utf-8') as f:
        f.write(setup_js)

# Startup
@app.on_event("startup")
async def startup_event():
    """Create web files on startup"""
    create_web_files()
    logger.info("AI Trading Agent Web Application started")

if __name__ == "__main__":
    # Create web files
    create_web_files()
    
    # Run the web application
    print("🚀 Starting AI Trading Agent Web Application...")
    print("📱 Dashboard: http://localhost:5000")
    print("⚙️ Setup: http://localhost:5000/setup")
    print("📚 API Docs: http://localhost:5000/docs")
    
    uvicorn.run(
        "webapp:app",
        host="0.0.0.0",
        port=5000,
        reload=True,
        log_level="info"
    ) 