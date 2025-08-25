# 🎯 Dynamic Stock Screening

The AI Trading Agent now features **dynamic stock screening** that analyzes **ALL stocks listed on NSE/BSE** instead of being limited to a predefined list.

## 🔍 How It Works

### 1. **Comprehensive Stock Universe**
- **NSE**: ~1,800+ equity stocks
- **BSE**: ~5,000+ equity stocks  
- **Total**: Analyzes up to **6,800+ stocks** daily

### 2. **Multi-Stage Filtering Process**

#### **Stage 1: Basic Eligibility**
- ✅ **Equity shares only** (excludes derivatives, futures, options)
- ✅ **Minimum price**: ₹10 (configurable)
- ✅ **Maximum price**: ₹10,000 (configurable)
- ✅ **Lot size = 1** (standard equity trading)

#### **Stage 2: Liquidity Filtering**
- ✅ **Minimum volume**: 100,000 shares/day
- ✅ **Volume spike**: 1.5x above average
- ✅ **Recent activity**: High trading interest

#### **Stage 3: Movement Analysis**
- ✅ **Price movement**: 0.5% to 8% range
- ✅ **Volatility**: Moderate (not too calm, not too wild)
- ✅ **Momentum**: Significant directional movement

#### **Stage 4: Potential Scoring**
Each stock gets a **potential score** based on:
- **Volume surge** (30% weightage)
- **Volatility level** (25% weightage)  
- **Price momentum** (25% weightage)
- **Trading range** (20% weightage)

### 3. **Intelligent Selection**
- 📊 **Pre-screening**: Filters ~6,800 stocks → ~100-200 promising stocks
- 🎯 **Deep analysis**: Applies full technical analysis to top candidates
- 🏆 **Final selection**: Returns top 50 best opportunities

---

## ⚙️ Configuration Options

### **Environment Variables (.env file)**

```bash
# Stock Filtering
MIN_MARKET_CAP=100              # Minimum market cap (crores)
MIN_AVG_VOLUME=100000          # Minimum daily volume
MIN_PRICE=10                   # Minimum stock price
MAX_PRICE=10000               # Maximum stock price

# Performance Limits
MAX_STOCKS_TO_ANALYZE=500      # Max stocks for full analysis
TOP_PERFORMERS_COUNT=50        # Final selection size

# Sector Focus (optional)
FOCUS_SECTORS=Technology,Banking,Pharma
```

### **Filtering Criteria Explained**

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `MIN_MARKET_CAP` | 100 cr | Avoid penny stocks |
| `MIN_AVG_VOLUME` | 100K | Ensure liquidity |
| `MIN_PRICE` | ₹10 | Filter out micro-caps |
| `MAX_PRICE` | ₹10K | Focus on tradeable range |
| `MAX_STOCKS_TO_ANALYZE` | 500 | Performance optimization |
| `TOP_PERFORMERS_COUNT` | 50 | Final opportunities |

---

## 📊 Selection Process

### **Daily Workflow**
```
6,800+ Stocks (NSE + BSE)
        ↓
📋 Basic Eligibility Filter
        ↓
~3,000 Eligible Stocks
        ↓
💹 Liquidity & Volume Filter  
        ↓
~500 Liquid Stocks
        ↓
📈 Movement & Volatility Filter
        ↓
~200 Active Stocks
        ↓
🎯 Potential Score Ranking
        ↓
~100 Top Candidates
        ↓
🔬 Full Technical Analysis
        ↓
📈 50 Best Opportunities
```

### **Technical Analysis Applied**
For the final candidates, full analysis includes:
- **RSI** (14-period)
- **EMA Crossovers** (12/26)
- **MACD** signals
- **Bollinger Bands**
- **Volume confirmation**
- **Support/Resistance levels**
- **Price momentum**

---

## 🎯 Benefits

### **1. Maximum Opportunity Coverage**
- **Before**: Limited to 30 pre-selected stocks
- **After**: Scans **ALL 6,800+ NSE/BSE stocks**

### **2. Dynamic Adaptation**
- **Daily fresh screening** based on current market conditions
- **Identifies emerging opportunities** in any sector
- **Adapts to market volatility** and trends

### **3. Smart Performance Optimization**
- **Multi-stage filtering** reduces computational load
- **Intelligent pre-screening** focuses on promising stocks
- **Configurable limits** for different system capabilities

### **4. Risk Management**
- **Liquidity filtering** ensures easy entry/exit
- **Volatility limits** avoid extreme price swings
- **Volume requirements** prevent illiquid trades

---

## 🔧 Customization Examples

### **Conservative Trading (Lower Risk)**
```bash
MIN_MARKET_CAP=500          # Larger companies only
MIN_AVG_VOLUME=500000      # Higher liquidity
MIN_PRICE=50               # Avoid small caps
MAX_PRICE=5000             # Conservative range
TOP_PERFORMERS_COUNT=20    # Fewer, high-quality picks
```

### **Aggressive Trading (Higher Returns)**
```bash
MIN_MARKET_CAP=50          # Include smaller caps
MIN_AVG_VOLUME=50000       # Lower liquidity threshold
MIN_PRICE=5                # Include more volatile stocks
MAX_PRICE=15000            # Wider price range
TOP_PERFORMERS_COUNT=100   # More opportunities
```

### **Sector-Specific Trading**
```bash
FOCUS_SECTORS=Technology,Banking,Pharma,Auto
# Only analyze stocks from specified sectors
```

---

## 📈 Performance Impact

### **Analysis Speed**
- **Pre-screening**: ~30 seconds for 6,800 stocks
- **Deep analysis**: ~2-5 minutes for top 100 stocks
- **Total time**: ~3-6 minutes for complete screening

### **Resource Usage**
- **Memory**: ~200-500 MB during screening
- **CPU**: Moderate during analysis, minimal during trading
- **Network**: API calls optimized with caching

---

## 🚀 Getting Started

1. **Update Configuration**:
   ```bash
   cp env.example .env
   # Edit .env with your parameters
   ```

2. **Run the Agent**:
   ```bash
   python webapp.py
   # Or use the web interface
   ```

3. **Monitor Screening**:
   ```
   🔍 Starting comprehensive stock screening...
   📊 Analyzing 6847 stocks from NSE/BSE
   🎯 Pre-screening identified 234 promising stocks
   📈 TCS: BUY (Strength: 0.87) - EMA bullish crossover, High volume
   📈 RELIANCE: BUY (Strength: 0.82) - RSI oversold, MACD bullish
   ✅ Found 47 trading opportunities from 234 analyzed stocks
   ```

---

## ⚠️ Important Notes

### **Fallback Mechanism**
If dynamic screening fails, the system automatically falls back to analyzing these reliable stocks:
- RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK
- KOTAKBANK, SBIN, BHARTIARTL, ITC, LT

### **Data Dependencies**
- Requires **active internet** for real-time data
- **Yahoo Finance** used as primary data source
- **Zerodha API** for instrument metadata

### **Performance Considerations**
- First run may take longer (instrument caching)
- Subsequent runs are faster (cached data)
- Adjust `MAX_STOCKS_TO_ANALYZE` based on your system

---

**🎉 Now your AI Trading Agent can discover opportunities across the entire Indian stock market!** 