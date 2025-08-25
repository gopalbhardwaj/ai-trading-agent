"""
Streamlit Dashboard for AI Trading Agent
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
import time
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.trading_engine import TradingEngine
from config import Config

# Page config
st.set_page_config(
    page_title="AI Trading Agent Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

def load_daily_state():
    """Load daily trading state"""
    try:
        with open('daily_state.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def get_trading_status():
    """Get current trading status"""
    try:
        # This is a simplified version - in a real implementation,
        # you'd connect to the running trading engine
        daily_state = load_daily_state()
        return {
            'is_running': False,  # Would check if engine is running
            'daily_pnl': daily_state.get('daily_pnl', 0),
            'daily_trades': daily_state.get('daily_trades', 0),
            'budget_used': daily_state.get('daily_budget_used', 0),
            'max_loss_reached': daily_state.get('max_daily_loss_reached', False)
        }
    except Exception:
        return {}

def main():
    """Main dashboard function"""
    
    # Title and header
    st.title("🤖 AI Trading Agent Dashboard")
    st.markdown("Real-time monitoring and control panel for automated trading")
    
    # Sidebar for controls
    with st.sidebar:
        st.header("⚙️ Controls")
        
        # Trading status
        status = get_trading_status()
        
        if status.get('is_running', False):
            st.success("🟢 Trading Engine: Running")
            if st.button("🛑 Stop Trading", type="secondary"):
                st.warning("Stop functionality would be implemented here")
        else:
            st.error("🔴 Trading Engine: Stopped")
            
            # Budget input
            daily_budget = st.number_input(
                "Daily Budget (₹)",
                min_value=5000.0,
                max_value=1000000.0,
                value=Config.MAX_DAILY_BUDGET,
                step=1000.0
            )
            
            if st.button("🚀 Start Trading", type="primary"):
                st.info("Start functionality would be implemented here")
                st.info(f"Budget set to: ₹{daily_budget:,.2f}")
        
        st.divider()
        
        # Emergency controls
        st.header("🚨 Emergency")
        if st.button("⛔ Square Off All Positions", type="secondary"):
            st.warning("Emergency square off would be executed")
        
        # Settings
        st.header("📊 Settings")
        auto_refresh = st.checkbox("Auto-refresh dashboard", value=True)
        refresh_interval = st.slider("Refresh interval (seconds)", 5, 60, 10)
    
    # Main dashboard area
    col1, col2, col3, col4 = st.columns(4)
    
    # Status metrics
    with col1:
        daily_pnl = status.get('daily_pnl', 0)
        pnl_color = "normal" if daily_pnl >= 0 else "inverse"
        st.metric(
            "Daily P&L",
            f"₹{daily_pnl:.2f}",
            delta=None,
            delta_color=pnl_color
        )
    
    with col2:
        st.metric(
            "Total Trades",
            status.get('daily_trades', 0)
        )
    
    with col3:
        budget_used = status.get('budget_used', 0)
        st.metric(
            "Budget Used",
            f"₹{budget_used:.2f}"
        )
    
    with col4:
        remaining_budget = Config.MAX_DAILY_BUDGET - budget_used
        st.metric(
            "Remaining Budget",
            f"₹{remaining_budget:.2f}"
        )
    
    # Charts section
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 P&L Chart")
        
        # Sample P&L data (in real implementation, this would come from logs)
        sample_times = pd.date_range(
            start=datetime.now().replace(hour=9, minute=15, second=0, microsecond=0),
            end=datetime.now(),
            freq='5T'
        )
        
        # Generate sample P&L progression
        import numpy as np
        np.random.seed(42)
        cumulative_pnl = np.cumsum(np.random.randn(len(sample_times)) * 50)
        
        pnl_df = pd.DataFrame({
            'Time': sample_times,
            'P&L': cumulative_pnl
        })
        
        fig_pnl = px.line(
            pnl_df, 
            x='Time', 
            y='P&L',
            title="Cumulative P&L Throughout the Day"
        )
        fig_pnl.add_hline(y=0, line_dash="dash", line_color="gray")
        fig_pnl.update_layout(
            xaxis_title="Time",
            yaxis_title="P&L (₹)",
            height=400
        )
        st.plotly_chart(fig_pnl, use_container_width=True)
    
    with col2:
        st.subheader("🎯 Trade Distribution")
        
        # Sample trade data
        trade_data = {
            'Type': ['Profitable', 'Loss', 'Breakeven'],
            'Count': [7, 3, 1],
            'Color': ['green', 'red', 'gray']
        }
        
        fig_pie = px.pie(
            values=trade_data['Count'],
            names=trade_data['Type'],
            title="Trade Outcome Distribution",
            color_discrete_map={
                'Profitable': 'green',
                'Loss': 'red',
                'Breakeven': 'gray'
            }
        )
        fig_pie.update_layout(height=400)
        st.plotly_chart(fig_pie, use_container_width=True)
    
    # Portfolio section
    st.divider()
    st.subheader("📊 Current Positions")
    
    # Sample positions data
    positions_data = {
        'Symbol': ['RELIANCE', 'TCS', 'HDFCBANK'],
        'Quantity': [10, -5, 15],
        'Avg Price': [2450.50, 3890.25, 1678.80],
        'Current Price': [2465.75, 3875.60, 1685.20],
        'P&L': [152.50, -73.25, 96.00],
        'P&L %': [0.62, -0.38, 0.38]
    }
    
    positions_df = pd.DataFrame(positions_data)
    
    # Style the dataframe
    def color_pnl(val):
        color = 'green' if val > 0 else 'red' if val < 0 else 'black'
        return f'color: {color}'
    
    styled_positions = positions_df.style.applymap(
        color_pnl, subset=['P&L', 'P&L %']
    ).format({
        'Avg Price': '₹{:.2f}',
        'Current Price': '₹{:.2f}',
        'P&L': '₹{:.2f}',
        'P&L %': '{:.2f}%'
    })
    
    st.dataframe(styled_positions, use_container_width=True)
    
    # Risk metrics
    st.divider()
    st.subheader("🛡️ Risk Metrics")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info(f"**Max Daily Loss Limit:** ₹{Config.MAX_DAILY_LOSS:.2f}")
        current_loss = abs(min(daily_pnl, 0))
        loss_percentage = (current_loss / Config.MAX_DAILY_LOSS) * 100
        st.progress(min(loss_percentage / 100, 1.0))
        st.caption(f"Current: ₹{current_loss:.2f} ({loss_percentage:.1f}%)")
    
    with col2:
        st.info(f"**Max Positions:** {Config.MAX_POSITIONS}")
        current_positions = len(positions_data['Symbol'])
        position_usage = (current_positions / Config.MAX_POSITIONS) * 100
        st.progress(position_usage / 100)
        st.caption(f"Current: {current_positions} ({position_usage:.1f}%)")
    
    with col3:
        st.info(f"**Budget Usage**")
        budget_usage = (budget_used / Config.MAX_DAILY_BUDGET) * 100
        st.progress(budget_usage / 100)
        st.caption(f"Used: ₹{budget_used:.2f} ({budget_usage:.1f}%)")
    
    # Recent trades
    st.divider()
    st.subheader("📋 Recent Trades")
    
    # Sample recent trades
    recent_trades = {
        'Time': ['14:35:22', '14:28:15', '14:15:43', '14:02:11', '13:55:28'],
        'Symbol': ['RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK'],
        'Action': ['BUY', 'SELL', 'BUY', 'SELL', 'BUY'],
        'Quantity': [10, 5, 15, 8, 20],
        'Price': [2450.50, 3890.25, 1678.80, 1825.60, 975.40],
        'Status': ['COMPLETE', 'COMPLETE', 'COMPLETE', 'COMPLETE', 'COMPLETE'],
        'P&L': [152.50, 73.25, 96.00, -45.60, 125.80]
    }
    
    trades_df = pd.DataFrame(recent_trades)
    
    styled_trades = trades_df.style.applymap(
        color_pnl, subset=['P&L']
    ).format({
        'Price': '₹{:.2f}',
        'P&L': '₹{:.2f}'
    })
    
    st.dataframe(styled_trades, use_container_width=True)
    
    # Footer
    st.divider()
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
               f"Market Status: {'🟢 Open' if datetime.now().hour < 15.5 else '🔴 Closed'}")
    
    # Auto-refresh
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()

if __name__ == "__main__":
    main() 