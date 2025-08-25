"""
Test script to validate AI Trading Agent setup
"""
import sys
import os
import importlib.util
from datetime import datetime

def test_imports():
    """Test if all required modules can be imported"""
    print("🔍 Testing imports...")
    
    required_modules = [
        'pandas', 'numpy', 'yfinance', 'ta', 'kiteconnect',
        'streamlit', 'plotly', 'rich', 'schedule'
    ]
    
    failed_imports = []
    
    for module in required_modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except ImportError:
            print(f"  ❌ {module}")
            failed_imports.append(module)
    
    if failed_imports:
        print(f"\n❌ Missing modules: {', '.join(failed_imports)}")
        print("Run: pip install -r requirements.txt")
        return False
    
    print("✅ All required modules imported successfully")
    return True

def test_config():
    """Test configuration"""
    print("\n🔍 Testing configuration...")
    
    try:
        # Test if config file exists and can be imported
        sys.path.append('.')
        from config import Config
        
        # Check if API keys are set
        if not Config.KITE_API_KEY or Config.KITE_API_KEY == 'your_api_key_here':
            print("  ⚠️  API Key not configured")
            return False
        
        if not Config.KITE_API_SECRET or Config.KITE_API_SECRET == 'your_api_secret_here':
            print("  ⚠️  API Secret not configured")
            return False
        
        print("  ✅ Configuration loaded")
        print(f"  ✅ Daily Budget: ₹{Config.MAX_DAILY_BUDGET:,.2f}")
        print(f"  ✅ Risk per Trade: {Config.RISK_PER_TRADE:.1%}")
        print(f"  ✅ Max Positions: {Config.MAX_POSITIONS}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Configuration error: {e}")
        return False

def test_components():
    """Test if all components can be imported"""
    print("\n🔍 Testing components...")
    
    try:
        sys.path.append('src')
        
        # Test Zerodha client
        from src.zerodha_client import ZerodhaClient
        print("  ✅ ZerodhaClient")
        
        # Test Market analyzer
        from src.market_analyzer import MarketAnalyzer
        print("  ✅ MarketAnalyzer")
        
        # Test Risk manager
        from src.risk_manager import RiskManager
        print("  ✅ RiskManager")
        
        # Test Trading engine
        from src.trading_engine import TradingEngine
        print("  ✅ TradingEngine")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Component error: {e}")
        return False

def test_file_structure():
    """Test if all required files exist"""
    print("\n🔍 Testing file structure...")
    
    required_files = [
        'main.py',
        'dashboard.py',
        'config.py',
        'requirements.txt',
        'README.md',
        '.env',
        'src/zerodha_client.py',
        'src/market_analyzer.py',
        'src/risk_manager.py',
        'src/trading_engine.py'
    ]
    
    missing_files = []
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path}")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n❌ Missing files: {', '.join(missing_files)}")
        return False
    
    return True

def test_market_data():
    """Test market data access"""
    print("\n🔍 Testing market data access...")
    
    try:
        import yfinance as yf
        
        # Test Yahoo Finance connection
        symbol = "RELIANCE.NS"
        stock = yf.Ticker(symbol)
        data = stock.history(period="1d", interval="5m")
        
        if not data.empty:
            print(f"  ✅ Market data access working (got {len(data)} data points for {symbol})")
            return True
        else:
            print(f"  ⚠️  No data received for {symbol}")
            return False
            
    except Exception as e:
        print(f"  ❌ Market data error: {e}")
        return False

def test_zerodha_connection():
    """Test Zerodha API connection (without authentication)"""
    print("\n🔍 Testing Zerodha API setup...")
    
    try:
        from kiteconnect import KiteConnect
        from config import Config
        
        # Test if API client can be created
        kite = KiteConnect(api_key=Config.KITE_API_KEY)
        login_url = kite.login_url()
        
        if login_url and 'kite.zerodha.com' in login_url:
            print("  ✅ Zerodha API client created successfully")
            print(f"  ✅ Login URL generated: {login_url[:50]}...")
            return True
        else:
            print("  ❌ Invalid login URL generated")
            return False
            
    except Exception as e:
        print(f"  ❌ Zerodha API error: {e}")
        return False

def run_full_test():
    """Run all tests"""
    print("🧪 Running AI Trading Agent Tests")
    print("=" * 50)
    
    tests = [
        ("File Structure", test_file_structure),
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Components", test_components),
        ("Market Data", test_market_data),
        ("Zerodha API", test_zerodha_connection)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"  ❌ {test_name} test failed: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<20} {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Your AI Trading Agent is ready to run.")
        print("\nNext steps:")
        print("1. Run: python main.py (for CLI interface)")
        print("2. Run: streamlit run dashboard.py (for web dashboard)")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please fix the issues before running the agent.")
        
        if not results.get("Configuration", True):
            print("\n💡 Tip: Make sure to update your .env file with valid Zerodha API credentials")
        
        if not results.get("Imports", True):
            print("\n💡 Tip: Run 'pip install -r requirements.txt' to install missing dependencies")

def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == '--quick':
        # Quick test - only essential components
        print("🧪 Running Quick Tests...")
        test_file_structure()
        test_imports()
        test_config()
    else:
        # Full test suite
        run_full_test()

if __name__ == "__main__":
    main() 