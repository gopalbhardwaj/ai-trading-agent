"""
AI Trading Agent - Main Application
"""
import logging
import sys
import os
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress
from rich.prompt import FloatPrompt, Confirm
from rich.live import Live
import time
import threading

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.trading_engine import TradingEngine
from config import Config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)
console = Console()

class TradingAgentApp:
    def __init__(self):
        self.trading_engine = TradingEngine()
        self.is_running = False
        
    def display_banner(self):
        """Display application banner"""
        banner = """
╔═══════════════════════════════════════════════════════════════╗
║                    🤖 AI Trading Agent                       ║
║                 Automated Intraday Trading                   ║
║                    Powered by Zerodha                        ║
╚═══════════════════════════════════════════════════════════════╝
        """
        console.print(banner, style="bold blue")
        console.print("🚀 Intelligent automated trading with risk management\n", style="cyan")
    
    def get_user_budget(self) -> float:
        """Get daily budget from user"""
        console.print("💰 [bold]Budget Configuration[/bold]\n")
        
        # Show current configuration
        config_table = Table(title="Current Configuration")
        config_table.add_column("Parameter", style="cyan")
        config_table.add_column("Value", style="green")
        
        config_table.add_row("Default Daily Budget", f"₹{Config.MAX_DAILY_BUDGET:,.2f}")
        config_table.add_row("Risk Per Trade", f"{Config.RISK_PER_TRADE:.1%}")
        config_table.add_row("Max Positions", str(Config.MAX_POSITIONS))
        config_table.add_row("Stop Loss", f"{Config.STOP_LOSS_PERCENT:.1%}")
        config_table.add_row("Take Profit", f"{Config.TAKE_PROFIT_PERCENT:.1%}")
        
        console.print(config_table)
        console.print()
        
        while True:
            try:
                budget = FloatPrompt.ask(
                    f"💵 Enter your daily trading budget (minimum ₹5,000)",
                    default=Config.MAX_DAILY_BUDGET
                )
                
                if budget < 5000:
                    console.print("❌ Minimum budget is ₹5,000", style="red")
                    continue
                
                if budget > 100000:
                    if not Confirm.ask(f"⚠️  Large budget: ₹{budget:,.2f}. Are you sure?"):
                        continue
                
                return budget
                
            except KeyboardInterrupt:
                console.print("\n👋 Goodbye!")
                sys.exit(0)
            except Exception as e:
                console.print(f"❌ Invalid input: {e}", style="red")
    
    def display_risk_warning(self):
        """Display risk warning and get user confirmation"""
        warning_panel = Panel.fit(
            """⚠️  [bold red]IMPORTANT RISK DISCLAIMER[/bold red] ⚠️

🔸 This is an automated trading system that will trade real money
🔸 Trading involves significant risk and you may lose money
🔸 Past performance does not guarantee future results
🔸 The system uses technical indicators which may not always be accurate
🔸 Ensure you understand the risks before proceeding

[bold]Safety Features:[/bold]
✅ Daily loss limits
✅ Position size limits  
✅ Automatic stop losses
✅ Real-time monitoring
✅ Emergency stop functionality""",
            title="⚠️  Risk Warning ⚠️",
            border_style="red"
        )
        
        console.print(warning_panel)
        console.print()
        
        if not Confirm.ask("📋 Do you understand and accept these risks?"):
            console.print("👋 Exiting for your safety. Please read about trading risks before proceeding.")
            sys.exit(0)
    
    def display_checklist(self):
        """Display pre-trading checklist"""
        checklist_panel = Panel.fit(
            """📋 [bold]Pre-Trading Checklist[/bold]

Please ensure you have:
✅ Created a Kite Connect app at developers.kite.trade
✅ Added your API credentials to .env file
✅ Set redirect URL to: http://localhost:5000/callback
✅ Sufficient margin in your trading account
✅ Good internet connection for stable operation
✅ Understanding of intraday trading rules

[bold yellow]Note:[/bold yellow] The system will automatically square off all positions before market close (3:20 PM)""",
            title="📋 Checklist",
            border_style="yellow"
        )
        
        console.print(checklist_panel)
        console.print()
        
        if not Confirm.ask("✅ Have you completed all the above steps?"):
            console.print("❌ Please complete the checklist before starting the trading agent.")
            sys.exit(0)
    
    def display_live_status(self):
        """Display live trading status"""
        def generate_status_table():
            try:
                status = self.trading_engine.get_status()
                risk_summary = status.get('risk_summary', {})
                
                # Main status table
                status_table = Table(title=f"🤖 AI Trading Agent Status - {datetime.now().strftime('%H:%M:%S')}")
                status_table.add_column("Metric", style="cyan")
                status_table.add_column("Value", style="green")
                
                # Engine status
                status_table.add_row("🔄 Engine Status", "🟢 Running" if status.get('is_running') else "🔴 Stopped")
                status_table.add_row("📈 Market Status", "🟢 Open" if status.get('market_open') else "🔴 Closed")
                status_table.add_row("🛑 Trading Status", "🔴 Stopped" if status.get('stop_trading') else "🟢 Active")
                
                # Trading metrics
                daily_pnl = risk_summary.get('daily_pnl', 0)
                pnl_color = "green" if daily_pnl >= 0 else "red"
                pnl_symbol = "+" if daily_pnl >= 0 else ""
                
                status_table.add_row("💹 Daily P&L", f"[{pnl_color}]{pnl_symbol}₹{daily_pnl:.2f}[/{pnl_color}]")
                status_table.add_row("📊 Total Trades", str(risk_summary.get('daily_trades', 0)))
                status_table.add_row("🎯 Open Positions", str(risk_summary.get('open_positions', 0)))
                status_table.add_row("⏳ Active Orders", str(status.get('active_orders', 0)))
                
                # Budget information
                budget_used = risk_summary.get('budget_used', 0)
                remaining_budget = risk_summary.get('remaining_budget', 0)
                total_budget = budget_used + remaining_budget
                
                if total_budget > 0:
                    budget_usage = (budget_used / total_budget) * 100
                    status_table.add_row("💰 Budget Used", f"₹{budget_used:.2f} ({budget_usage:.1f}%)")
                    status_table.add_row("💵 Remaining", f"₹{remaining_budget:.2f}")
                
                return status_table
                
            except Exception as e:
                error_table = Table(title="❌ Status Error")
                error_table.add_column("Error", style="red")
                error_table.add_row(str(e))
                return error_table
        
        return generate_status_table()
    
    def start_live_monitoring(self):
        """Start live status monitoring in a separate thread"""
        def monitor():
            with Live(self.display_live_status(), refresh_per_second=1) as live:
                while self.is_running:
                    time.sleep(2)
                    live.update(self.display_live_status())
        
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
    
    def run(self):
        """Main application loop"""
        try:
            # Display banner
            self.display_banner()
            
            # Show risk warning
            self.display_risk_warning()
            
            # Show checklist
            self.display_checklist()
            
            # Get user budget
            daily_budget = self.get_user_budget()
            
            # Final confirmation
            console.print(f"\n🎯 [bold]Ready to start trading with ₹{daily_budget:,.2f} daily budget[/bold]")
            if not Confirm.ask("🚀 Start the AI Trading Agent?"):
                console.print("👋 Trading cancelled by user")
                return
            
            # Start trading
            console.print("\n🚀 [bold green]Starting AI Trading Agent...[/bold green]\n")
            
            # Set running flag
            self.is_running = True
            
            # Start live monitoring
            self.start_live_monitoring()
            
            # Start trading engine
            self.trading_engine.start(daily_budget)
            
        except KeyboardInterrupt:
            console.print("\n\n🛑 [bold red]Emergency Stop Initiated[/bold red]")
            self.shutdown()
        except Exception as e:
            console.print(f"\n❌ [bold red]Application Error:[/bold red] {e}")
            logger.error(f"Application error: {e}")
            self.shutdown()
    
    def shutdown(self):
        """Shutdown the application safely"""
        console.print("🛑 Shutting down trading agent...")
        
        self.is_running = False
        
        # Stop trading engine
        if hasattr(self, 'trading_engine'):
            self.trading_engine.stop()
        
        # Final status
        try:
            final_status = self.trading_engine.get_status()
            risk_summary = final_status.get('risk_summary', {})
            
            console.print("\n📊 [bold]Final Trading Summary:[/bold]")
            summary_table = Table()
            summary_table.add_column("Metric", style="cyan")
            summary_table.add_column("Value", style="white")
            
            daily_pnl = risk_summary.get('daily_pnl', 0)
            pnl_color = "green" if daily_pnl >= 0 else "red"
            pnl_symbol = "+" if daily_pnl >= 0 else ""
            
            summary_table.add_row("Total Trades", str(risk_summary.get('daily_trades', 0)))
            summary_table.add_row("Final P&L", f"[{pnl_color}]{pnl_symbol}₹{daily_pnl:.2f}[/{pnl_color}]")
            summary_table.add_row("Budget Used", f"₹{risk_summary.get('budget_used', 0):.2f}")
            summary_table.add_row("Open Positions", str(risk_summary.get('open_positions', 0)))
            
            console.print(summary_table)
            
        except Exception as e:
            logger.error(f"Error getting final status: {e}")
        
        console.print("\n✅ [bold green]Trading agent stopped safely[/bold green]")
        console.print("📝 Check trading_agent.log for detailed logs")
        console.print("👋 Thank you for using AI Trading Agent!")

def main():
    """Main entry point"""
    try:
        # Check if .env file exists
        if not os.path.exists('.env'):
            console.print("❌ [bold red].env file not found![/bold red]")
            console.print("Please create a .env file with your Zerodha API credentials.")
            console.print("Use the .env.example file as a template.")
            return
        
        # Create and run app
        app = TradingAgentApp()
        app.run()
        
    except Exception as e:
        console.print(f"❌ [bold red]Fatal Error:[/bold red] {e}")
        logger.error(f"Fatal error: {e}")

if __name__ == "__main__":
    main() 