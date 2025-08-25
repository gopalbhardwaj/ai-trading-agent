# 🚀 Local Setup Guide - AI Trading Agent

This guide will help you set up the AI Trading Agent on any computer from scratch.

## 📋 Prerequisites

### System Requirements
- **Operating System**: Windows 10/11, macOS, or Linux
- **Python**: Version 3.8 or higher
- **RAM**: Minimum 4GB (8GB recommended)
- **Storage**: 2GB free space
- **Internet**: Stable connection required

### Required Accounts
- **Zerodha Account**: Active trading account with Kite API access
- **GitHub Account**: To download the code (optional if downloading ZIP)

## 🛠️ Step-by-Step Installation

### Step 1: Install Python

#### Windows:
1. Download Python from [python.org](https://www.python.org/downloads/)
2. **Important**: Check "Add Python to PATH" during installation
3. Verify installation:
   ```cmd
   python --version
   ```

#### macOS:
1. Install Homebrew: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
2. Install Python: `brew install python`
3. Verify: `python3 --version`

#### Linux (Ubuntu/Debian):
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

### Step 2: Download the Project

#### Option A: Using Git (Recommended)
```bash
git clone https://github.com/YOUR_USERNAME/ai-trading-agent.git
cd ai-trading-agent
```

#### Option B: Download ZIP
1. Go to the GitHub repository
2. Click "Code" → "Download ZIP"
3. Extract the ZIP file
4. Navigate to the extracted folder

### Step 3: Set Up Virtual Environment

#### Windows:
```cmd
python -m venv venv
venv\Scripts\activate
```

#### macOS/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

**Note**: You should see `(venv)` in your terminal prompt when activated.

### Step 4: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**If you encounter SSL errors during installation:**
```bash
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt
```

### Step 5: Set Up Zerodha Kite API

#### 5.1 Create Kite Connect App
1. Login to [Kite Connect Developer Console](https://developers.kite.trade/)
2. Click "Create New App"
3. Fill in the details:
   - **App Name**: "AI Trading Agent" (or your preferred name)
   - **App Type**: "Connect"
   - **Redirect URL**: `http://localhost:5000/callback` ⚠️ **IMPORTANT**
   - **Website**: Your website (or use `http://localhost:5000`)
   - **Description**: Brief description of your trading bot

#### 5.2 Get API Credentials
After creating the app, note down:
- **API Key** (Consumer Key)
- **API Secret** (Consumer Secret)

### Step 6: Configure Environment

#### 6.1 Create Environment File
Create a `.env` file in the project root:

**Windows:**
```cmd
echo. > .env
```

**macOS/Linux:**
```bash
touch .env
```

#### 6.2 Add Your Credentials
Open `.env` file in any text editor and add:

```env
# Zerodha Kite API Configuration
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here

# Trading Configuration
MAX_DAILY_BUDGET=10000
RISK_PER_TRADE=0.02
MAX_POSITIONS=5

# Optional: Telegram Bot for notifications
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Market Data Configuration
USE_LIVE_DATA=true
```

⚠️ **IMPORTANT**: 
- Replace `your_api_key_here` with your actual Kite API Key
- Replace `your_api_secret_here` with your actual Kite API Secret
- Set `MAX_DAILY_BUDGET` to your desired daily trading limit
- Never share this file or commit it to version control!

### Step 7: Test Installation

Run the setup test:
```bash
python run_tests.py
```

This will verify:
- ✅ All dependencies are installed
- ✅ Configuration files are valid
- ✅ API credentials format (doesn't test actual connection)

### Step 8: Launch the Application

```bash
python webapp.py
```

You should see:
```
🚀 Starting AI Trading Agent Web Application...
📱 Dashboard: http://localhost:5000
⚙️ Setup: http://localhost:5000/setup
📚 API Docs: http://localhost:5000/docs
```

### Step 9: Complete Web Setup

1. **Open your browser** and go to: `http://localhost:5000`

2. **Navigate to Setup**: Click "Setup" or go to `http://localhost:5000/setup`

3. **Enter your credentials**:
   - API Key: Your Zerodha API Key
   - API Secret: Your Zerodha API Secret  
   - Daily Budget: Your trading budget (minimum ₹5,000)

4. **Authenticate with Zerodha**:
   - Click "Authenticate with Zerodha"
   - You'll be redirected to Zerodha's login page
   - Enter your Zerodha credentials
   - Enter your 6-digit PIN
   - You'll be redirected back to the app

5. **Verify Authentication**: You should see a success message with your account details

## 🔧 Troubleshooting

### Common Issues

#### Issue: "Python not found"
**Solution**: Ensure Python is added to PATH during installation. On Windows, reinstall Python with "Add to PATH" checked.

#### Issue: "pip not found"
**Solution**: 
- Windows: Use `python -m pip` instead of `pip`
- macOS/Linux: Use `pip3` instead of `pip`

#### Issue: SSL Certificate Errors
**Solution**: The application includes SSL bypass for development. If issues persist:
1. Check your internet connection
2. Try using a VPN
3. Contact your network administrator

#### Issue: "Port 5000 already in use"
**Solution**: 
1. Kill existing processes: `taskkill /F /IM python.exe` (Windows) or `pkill python` (macOS/Linux)
2. Or change the port in `webapp.py` (line 1215) and update your Zerodha app redirect URL

#### Issue: "Module not found" errors
**Solution**:
```bash
# Ensure you're in the correct directory
cd path/to/ai-trading-agent

# Ensure virtual environment is activated
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

#### Issue: Authentication fails
**Solutions**:
1. **Check redirect URL**: Ensure your Kite app redirect URL is exactly `http://localhost:5000/callback`
2. **Verify credentials**: Double-check API Key and Secret in `.env` file
3. **Check Zerodha app status**: Ensure your Kite Connect app is approved and active
4. **Try different browser**: Sometimes browser cache can cause issues

### Getting Help

1. **Check the logs**: Look for error messages in the terminal where you ran `python webapp.py`
2. **Restart the application**: Stop (Ctrl+C) and restart the webapp
3. **Verify .env file**: Ensure no extra spaces or quotes around your API credentials

## 📱 Usage

Once set up successfully:

1. **Dashboard**: Monitor your trading activity at `http://localhost:5000`
2. **Real-time updates**: The dashboard shows live market data and trading decisions
3. **Manual controls**: Start/stop trading, adjust budget, view positions
4. **Logs**: Monitor all trading activities and decisions

## 🔒 Security Notes

- Keep your `.env` file secure and never share it
- Your API credentials provide access to your trading account
- The application runs locally on your machine for security
- Always test with small amounts before using larger budgets

## 🎯 Next Steps

After successful setup:
1. Test with a small budget first (₹5,000-₹10,000)
2. Monitor the trading decisions for a few days
3. Adjust risk parameters based on your comfort level
4. Consider the deployment guide for running 24/7

---

**Need help?** Check the troubleshooting section above or create an issue on GitHub. 