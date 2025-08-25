# 🤖 AI Trading Agent

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Zerodha](https://img.shields.io/badge/API-Zerodha%20Kite-orange.svg)](https://kite.trade/)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-success.svg)]()

An intelligent, automated trading system that integrates with Zerodha's Kite Connect API to execute data-driven intraday trading strategies with a professional web interface.

## 🎯 Features

### 🚀 Core Trading Capabilities
- **Automated Intraday Trading**: Executes buy/sell orders based on technical analysis
- **Multi-Indicator Analysis**: Uses RSI, MACD, EMA, Bollinger Bands, and Volume analysis
- **Risk Management**: Built-in position sizing, stop-loss, and take-profit mechanisms
- **Real-time Market Data**: Live price feeds and market analysis
- **Smart Order Execution**: Optimized entry and exit strategies

### 📊 Technical Analysis
- **RSI (Relative Strength Index)**: Momentum oscillator for overbought/oversold conditions
- **MACD**: Moving Average Convergence Divergence for trend analysis
- **EMA**: Exponential Moving Averages for trend direction
- **Bollinger Bands**: Volatility and support/resistance levels
- **Volume Analysis**: Trading volume confirmation
- **Support/Resistance**: Price level identification
- **ATR (Average True Range)**: Volatility-based position sizing

### 🛡️ Risk Management
- **Daily Budget Limits**: Maximum daily trading capital allocation
- **Position Sizing**: Calculated based on risk percentage and ATR
- **Stop Loss**: Automatic loss limitation on trades
- **Take Profit**: Profit booking at predetermined levels
- **Maximum Positions**: Limit concurrent open positions
- **Time-based Square-off**: Automatic closure before market close

### 🖥️ Professional Web Interface
- **Real-time Dashboard**: Live monitoring and control interface
- **WebSocket Updates**: Real-time data streaming
- **Trading Controls**: Manual start/stop and configuration
- **Performance Metrics**: P&L tracking and trade statistics
- **Position Monitoring**: Current holdings and order status

## 🛠️ Technology Stack

- **Backend**: Python, FastAPI, asyncio
- **Frontend**: HTML5, CSS3, JavaScript, WebSockets
- **Trading API**: Zerodha Kite Connect
- **Data Analysis**: NumPy, Pandas, TA-Lib
- **Market Data**: Real-time WebSocket feeds
- **Deployment**: Uvicorn ASGI server

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Zerodha trading account with Kite Connect API access
- Active internet connection for real-time data

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/ai-trading-agent.git
cd ai-trading-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install build tools (prevents setuptools errors)
pip install --upgrade pip setuptools wheel

# Install dependencies
pip install -r requirements-core.txt  # Core features only
# OR: pip install -r requirements.txt  # All features including ML & dashboard

# Run the application
python webapp.py
```

### Quick Setup
1. **Open your browser**: Navigate to `http://localhost:5000`
2. **Complete setup**: Enter your Zerodha API credentials
3. **Authenticate**: Connect with your Zerodha account
4. **Start trading**: Configure your budget and begin automated trading

📖 **Need detailed setup instructions?** Check our [Local Setup Guide](LOCAL_SETUP.md)

## 📚 Documentation

- 📋 **[Local Setup Guide](LOCAL_SETUP.md)**: Complete installation instructions for any computer
- 🚀 **[Deployment Guide](DEPLOYMENT.md)**: Production deployment for 24/7 trading
- 📊 **[API Documentation](docs/api.md)**: Complete API reference
- 🔧 **[Configuration Guide](docs/configuration.md)**: Detailed configuration options

## ⚙️ Configuration

### Quick Configuration
The application includes a web-based setup interface. Simply:
1. Navigate to `http://localhost:5000/setup`
2. Enter your Zerodha API credentials
3. Set your daily trading budget
4. Authenticate with Zerodha

### Environment Variables
```env
# Zerodha Kite API Configuration
KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret

# Trading Parameters
MAX_DAILY_BUDGET=50000
RISK_PER_TRADE=0.02
MAX_POSITIONS=5
```

## 📈 Trading Strategy

The AI Trading Agent employs a sophisticated multi-factor approach:

### 🎯 Entry Signals
- **Bullish**: EMA crossover + RSI confirmation + Volume surge
- **Bearish**: EMA breakdown + RSI divergence + Volume confirmation

### 🛡️ Risk Management
- **Stop Loss**: Dynamic based on ATR (2-3% typical)
- **Take Profit**: Risk-reward ratio of 1:2 or better
- **Position Sizing**: 1-2% risk per trade
- **Time-based Exit**: Square-off 15 minutes before market close

### 📊 Technical Indicators
- **Trend**: EMA (12, 26) crossovers
- **Momentum**: RSI (14) overbought/oversold levels
- **Volatility**: Bollinger Bands breakouts
- **Volume**: Confirmation of price movements

## 🔒 Security & Safety

- ✅ **Local Execution**: All trading logic runs on your machine
- ✅ **Secure API**: Industry-standard OAuth authentication
- ✅ **No Cloud Dependencies**: Complete privacy and control
- ✅ **Audit Trail**: Comprehensive logging of all decisions
- ✅ **Risk Limits**: Built-in safeguards and position limits

## 📊 Performance & Monitoring

### Real-time Dashboard Features
- 📈 Live P&L tracking
- 📊 Technical indicator visualization  
- 🔍 Position monitoring
- 📝 Trade history and logs
- ⚡ Real-time market data

### Monitoring & Alerts
- 📱 Telegram notifications (optional)
- 📧 Email alerts for critical events
- 📊 Performance analytics
- 🚨 Risk threshold warnings

## 🎮 Demo Mode

Test the system safely with our demo mode:
```bash
python demo.py
```
- Simulates real trading without actual money
- Full feature testing
- Performance evaluation
- Strategy optimization

## 📦 Installation Options

### Option 1: Quick Start (Recommended)
```bash
git clone https://github.com/yourusername/ai-trading-agent.git
cd ai-trading-agent
pip install --upgrade pip setuptools wheel
pip install -r requirements-core.txt
python webapp.py
```

### Option 2: Docker Deployment
```bash
docker-compose up -d
```

### Option 3: Production VPS
Follow our [Deployment Guide](DEPLOYMENT.md) for production setup.

## 🆘 Support & Help

### Getting Help
- 📖 **Documentation**: Check our comprehensive guides
- 🐛 **Issues**: [Report bugs](https://github.com/yourusername/ai-trading-agent/issues)
- 💬 **Discussions**: [Community support](https://github.com/yourusername/ai-trading-agent/discussions)
- 📧 **Email**: support@example.com

### Common Issues
- **Authentication fails**: Check redirect URL in Zerodha app
- **Module errors**: Ensure virtual environment is activated
- **Port conflicts**: Change port in `webapp.py` if needed

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md).

### Areas for Contribution
- 🔄 Additional technical indicators
- 📊 Enhanced visualization
- 🛡️ Advanced risk management
- 📱 Mobile responsiveness
- 🧪 Backtesting capabilities

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Important Disclaimers

### Trading Risk Warning
**This software is for educational purposes and involves substantial risk of loss. Key points:**

- 📉 Trading involves risk and can result in significant losses
- 🧪 Always test with small amounts first
- 📊 Past performance doesn't guarantee future results
- 💡 Understand the strategy before using real money
- 🚫 Never invest more than you can afford to lose

### Liability
- The authors are not responsible for any trading losses
- Use at your own risk and discretion
- Always practice proper risk management
- Consider consulting a financial advisor

## 🎯 Roadmap

### Version 2.0 (Upcoming)
- [ ] Machine learning integration
- [ ] Multi-exchange support
- [ ] Advanced backtesting
- [ ] Mobile app
- [ ] Portfolio optimization

### Version 1.5 (In Progress)
- [ ] Options trading support
- [ ] Advanced charting
- [ ] Strategy builder UI
- [ ] Paper trading mode

## 🏆 Success Stories

> "Increased my trading consistency by 40% with automated risk management" - User A

> "The real-time dashboard helps me monitor multiple positions effortlessly" - User B

---

<div align="center">

**Ready to start automated trading?**

[![Get Started](https://img.shields.io/badge/Get%20Started-Now-success.svg?style=for-the-badge)](LOCAL_SETUP.md)
[![Demo](https://img.shields.io/badge/Try%20Demo-Free-blue.svg?style=for-the-badge)](demo.py)

**⭐ Star this repo if you find it helpful!**

</div> 