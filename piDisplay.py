# Built by Danny Blue-Eyes
from matplotlib.offsetbox import AnchoredOffsetbox, TextArea, VPacker, HPacker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from bitcoinrpc.authproxy import AuthServiceProxy
from matplotlib.offsetbox import AnchoredText
from datetime import datetime, timedelta
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from datetime import datetime
from tkinter import ttk
import tkinter as tk
import subprocess
import platform
import requests
import argparse
import logging
import pathlib
import json
import time
import pytz
import os

IS_PI = platform.machine().startswith("arm") or platform.machine().startswith("aarch")
# Parse command line args FIRST
parser = argparse.ArgumentParser(description="Bitcoin Pi Display")
parser.add_argument('--testing', action='store_true', help='Enable testing mode')
parser.add_argument('--static', action='store_true', help='Force static viewing mode')
parser.add_argument('--config', type=str, help='Path to config file')
args = parser.parse_args()

# Use CLI --config first, then find config.json, then set defaults
config_path = args.config or os.environ.get('PIDISPLAY_CONFIG')
if not config_path:
    BASE_DIR = pathlib.Path(__file__).resolve().parent
    config_path = str(BASE_DIR / "config.json")

with open(config_path, 'r') as config_file:
    config = json.load(config_file)

# CLI --testing OVERRIDES config.json
# CLI args OVERRIDE config.json
if args.testing:
    config['testing'] = True
if args.static:
    viewing_mode = 'static'  # CLI flag overrides config

# Use configuration values
time_series = config['time_series'].lower()
viewing_mode = config.get('viewing_mode', 'rolling').lower()
testing = config['testing']

connect_to = config['connect_to']
rpc_settings = config['rpc_settings'][connect_to]
rpc_user = rpc_settings['rpc_user']
rpc_host = rpc_settings['rpc_host']
rpc_password = rpc_settings['rpc_password']
rpc_port = rpc_settings['rpc_port']
CACHE_FILE = config['cache_file']

# Set up logging
log_file = config['testing_log_file'] if testing else config['log_file']
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
    # flush=True # Not working
)

# RPC connection
rpc_connection = AuthServiceProxy(f"http://{rpc_user}:{rpc_password}@{rpc_host}:{rpc_port}", timeout=30)

# Global Variables (Globals)
last_price_update = 0 # Variable for tracking when to update price
last_blockchain_update = 0 # Variable for tracking when to update blockchain info
fig = None # Creating global fig
canvas = None # Creating global canvas
previous_chain, previous_network , previous_fees = "", "", "" # Initiate global shit
blockchain_chain = ""
blockchain_blocks = ""
blockchain_verification_progress = ""
node_connections = ""
cpu_temp = ""
ax = None
saved_timestamp = ""
global root
root = None
app_running = True
press_start_time = [None]
long_press_duration = 2
price_timer_id = None
blockchain_timer_id = None
display_timer_id = None
current_screen = "main"  # "main" or "more"
chart_frame = None
more_fig = None
more_canvas = None
more_ax = None

def update_display():
    global app_running
    if not app_running:
        return  # Don't do anything if the app is not running   
    update_price_chart()      # Checks its own schedule internally
    update_blockchain_info()  # Checks its own schedule internally
    if app_running:
        display_timer_id = root.after(300000, update_display)

def create_display():
    global root, fig, canvas, chart_frame
    root = tk.Tk()
    root.title("Bitcoin Node Information")

    if IS_PI:
        # Fullscreen for Pi display
        root.overrideredirect(True)
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        root.geometry(f"{screen_w}x{screen_h}+0+0")
        root.config(cursor="none")
        
        # Figure matches screen exactly
        fig_w = screen_w / 100  # DPI-adjusted
        fig_h = screen_h / 100
        fig = plt.Figure(figsize=(fig_w, fig_h), dpi=100)
    else:
        root.geometry("1280x720")
        fig = plt.Figure(figsize=(12, 5))   

    root.focus_set()
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(1, weight=1)

    root.bind('<Escape>', on_escape)
    root.bind('<ButtonPress-1>', on_press)
    root.bind('<ButtonRelease-1>', on_release)

    exit_button = tk.Button(
        root, text="Exit", command=proper_exit,
        bg='#202222', fg='white',
        bd=0, highlightthickness=0,
        activebackground='#202222', activeforeground='red'
    )
    exit_button.place(relx=1.0, rely=0.01, anchor='ne')
    # MORE button (next to Exit)
    more_button = tk.Button(
        root, text="More", command=show_more_screen,
        bg='#202222', fg='cyan', bd=0, highlightthickness=0,
        activebackground='#303333', activeforeground='cyan'
    )
    more_button.place(relx=0.95, rely=0.01, anchor='ne')  # Slightly left of Exit

    chart_frame = ttk.Frame(root)
    chart_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    if IS_PI:
        screen_width = root.winfo_screenwidth() / root.winfo_screenheight() * 10
        screen_height = 4.0  # Fixed height ratio
        fig = plt.Figure(figsize=(screen_width, screen_height))
    else:
        fig = plt.Figure(figsize=(10, 4))
    canvas = FigureCanvasTkAgg(fig, master=chart_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    exit_button.lift()
    more_button.lift()
    return root


def show_more_screen():
    global current_screen, more_fig, more_canvas, more_ax, canvas, fig, ax    

    if current_screen == "more":
        # ALWAYS RECREATE MAIN SCREEN FRESH - identical to initial state
        more_canvas.get_tk_widget().destroy()
        
        # Completely rebuild main chart from scratch
        fig.clear()
        ax = fig.add_subplot(111)
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        
        # Force full refresh of BOTH price chart AND node data
        update_price_chart(force_update=True)
        update_blockchain_info(force_update=True)
        
        current_screen = "main"
        return
    
    # Switch to more screen
    current_screen = "more"
    canvas.get_tk_widget().pack_forget()  # Hide main chart
    
    # Create more chart directly in chart_frame
    more_fig = plt.Figure(figsize=(14, 6))
    more_ax = more_fig.add_subplot(111)
    more_fig.patch.set_facecolor('#191A1A')
    more_ax.set_facecolor('#202222')
    
    more_canvas = FigureCanvasTkAgg(more_fig, master=chart_frame)
    more_canvas.draw()
    more_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
    
    update_more_metrics()

def update_more_metrics():
    global more_fig, more_ax, more_canvas
    if current_screen != "more" or more_ax is None:
        return
    
    more_ax.clear()
    more_ax.set_facecolor('#202222')
    
    # Fetch data
    if testing:
        print("Using dummy data for testing")
        # Dummy data for testing
        blockchain_info = {'blocks': 800000}
        network_info = {'connections': 10}
        fees = [10, 20, 30]
        current_price = 50000
        high_24h = 51000
        low_24h = 49000
        address_balance = 1.0
        last_update = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    else:
        try:
            blockchain_info, network_info, fees = get_node_info(rpc_connection)
            current_price, _, prices = get_bitcoin_price()
            if prices:
                high_24h = max(p[1] for p in prices)
                low_24h = min(p[1] for p in prices)
            else:
                high_24h = low_24h = current_price
            address_balance = get_address_balance('1FpaYV2cTk1W7WtHhsRP2kuNtKynNbeGoH')
            last_update = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            logging.error(f"Error fetching data for more metrics: {e}")
            blockchain_info = network_info = fees = None
            current_price = high_24h = low_24h = address_balance = 0
            last_update = "Error"
    
    # Display metrics
    more_ax.text(0.1, 0.95, "NODE METRICS", transform=more_ax.transAxes,
                color='white', fontsize=16, weight='bold')
    
    chain_name = blockchain_info.get('chain', 'unknown') if blockchain_info else 'unknown'
    sync_progress = blockchain_info.get('verificationprogress', 0) * 100 if blockchain_info else 0
    difficulty = blockchain_info.get('difficulty', 0) if blockchain_info else 0
    difficulty_text = format_difficulty(difficulty)
    connections_in = network_info.get('connections_in', 0) if network_info else 0
    connections_out = network_info.get('connections_out', 0) if network_info else 0
    total_connections = network_info.get('connections', 0) if network_info else 0
    latest_block = blockchain_info.get('blocks', 0) if blockchain_info else 0
    fee_rates_usd = [0, 0, 0]
    if fees:
        fee_rates_usd = [fee * 0.00000001 * current_price for fee in fees]
    usd_value = address_balance * current_price

    left_x = 0.1
    right_x = 0.55
    y_step = 0.08

    labels = [
        (left_x, 0.85, f"Last Update: {last_update}", 'cyan'),
        (left_x, 0.85 - y_step, f"Peers: {total_connections}", 'cyan'),
        (left_x, 0.85 - 2 * y_step, f"Latest Block: {latest_block:,}", 'cyan'),
        (left_x, 0.85 - 3 * y_step, f"Fee Rates (sat/vB): L:{fees[0]} M:{fees[1]} H:{fees[2]}" if fees else "Fee Rates: N/A", 'cyan'),
        (left_x, 0.85 - 4 * y_step, f"Fee Rates (USD): L:${fee_rates_usd[0]:,.2f} M:${fee_rates_usd[1]:,.2f} H:${fee_rates_usd[2]:,.2f}" if fees else "", 'cyan'),
        (left_x, 0.85 - 5 * y_step, f"24h High: ${high_24h:,.0f}", 'green'),
        (left_x, 0.85 - 6 * y_step, f"24h Low: ${low_24h:,.0f}", 'red'),
        (left_x, 0.85 - 7 * y_step, f"Address Balance: {address_balance:.3f} BTC (${usd_value:,.0f})", 'yellow'),
    ]

    for x, y, text, color in labels:
        if text:
            more_ax.text(x, y, text, transform=more_ax.transAxes, color=color, fontsize=12)

    more_ax.axis('off')
    more_fig.tight_layout()
    more_canvas.draw()

rpc_connection = AuthServiceProxy(f"http://{rpc_user}:{rpc_password}@{rpc_host}:{rpc_port}", timeout=30)

logging.basicConfig(
    filename='bitcoin_display.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def proper_exit():
    global app_running, root, price_timer_id, blockchain_timer_id, display_timer_id
    app_running = False
    
    # Cancel known timer IDs safely
    for timer_id in [price_timer_id, blockchain_timer_id, display_timer_id]:
        if timer_id and timer_id != 'None':
            try:
                root.after_cancel(timer_id)
            except:
                pass
    
    try:
        plt.close('all')
        root.quit()
        root.destroy()
    except:
        pass
    
    import sys
    sys.exit(0)

def on_press(event):
    press_start_time[0] = time.time()

def on_release(event):
    if press_start_time[0] is not None:
        press_duration = time.time() - press_start_time[0]
        if press_duration >= long_press_duration:
            update_price_chart(force_update=True)
            update_blockchain_info(force_update=True)
        press_start_time[0] = None
def get_cpu_temp():
    try:
        # This works on Raspberry Pi
        out = subprocess.check_output(
            ["vcgencmd", "measure_temp"],
            stderr=subprocess.DEVNULL,
            text=True
        )
        return float(out.replace("temp=", "").replace("'C", ""))
    except Exception:
        # Non-Pi or vcgencmd unavailable
        return None
def on_escape(event):
    proper_exit()
def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def time_until_next_even_hour(): # Used for price data when updating hourly (3600 seconds)
    now = datetime.now()
    # If past :00 of even hour, go to next even hour
    next_hour = now.replace(minute=0, second=0, microsecond=0)
    if now.hour % 2 == 1:  # Odd hour (1pm, 3pm, etc.)
        next_hour += timedelta(hours=1)
    # Always target :00 of even hour
    return (next_hour - now).total_seconds()
def time_until_next_10min(): # Used for blockchain data when updating every 10 minutes (600 seconds)
    now = datetime.now()
    minutes = now.minute
    next_10min = (minutes // 10 + 1) * 10
    if next_10min >= 60:
        next_10min = 0
        now += timedelta(hours=1)
    target_time = now.replace(minute=next_10min, second=0, microsecond=0)
    return (target_time - now).total_seconds()
def get_fee_estimates(rpc_connection):
    try:
        # Get fee estimates for 1, 6, and 144 blocks (high, medium, low priority)
        high_priority = rpc_connection.estimatesmartfee(1)
        medium_priority = rpc_connection.estimatesmartfee(6)
        low_priority = rpc_connection.estimatesmartfee(144)

        # Extract the fee rates and convert to sats/vB
        high_fee = int(high_priority['feerate'] * 100000000)  # Convert BTC/kB to sat/vB
        medium_fee = int(medium_priority['feerate'] * 100000000)
        low_fee = int(low_priority['feerate'] * 100000000)

        return [low_fee, medium_fee, high_fee]
    except Exception as e:
        logging.error(f"Error getting fee estimates: {e}")
        return None, None, None

def get_address_balance(address):
    try:
        url = f"https://api.blockcypher.com/v1/btc/main/addrs/{address}/balance"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        balance_sat = data['balance']
        balance_btc = balance_sat / 100000000
        return balance_btc
    except Exception as e:
        logging.error(f"Error getting address balance: {e}")
        return 0

def get_bitcoin_price():
    try:
        if testing:
            if os.path.exists(CACHE_FILE): # Check if cache file exists
                with open(CACHE_FILE, 'r') as cache_file:
                    cached_data = json.load(cache_file)
                    current_price = cached_data["current_price"]
                    daily_change = cached_data["daily_change"]
                    prices = cached_data["prices"]
                    print("Loaded price data from cache.")
                    return current_price, daily_change, prices
        # Current price
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        response = requests.get(url)
        response.raise_for_status()
        current_data = response.json()
        current_price = current_data["bitcoin"]["usd"]

        # Previous close price (24 hours ago)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)

        # Convert to timestamps
        start_timestamp = int(start_date.timestamp())
        end_timestamp = int(end_date.timestamp())

        historical_url = f"https://api.coingecko.com/api/v3/coins/bitcoin/market_chart/range?vs_currency=usd&from={start_timestamp}&to={end_timestamp}"
        historical_response = requests.get(historical_url)
        historical_response.raise_for_status()
        historical_data = historical_response.json()
        prices = historical_data['prices']
        
        if prices:
            previous_close_price = prices[0][1]
            daily_change = (current_price - previous_close_price) / previous_close_price * 100
            daily_change = round(daily_change, 2)
            if testing:
                with open(CACHE_FILE, 'w') as cache_file: # Save the fetched data to cache
                    json.dump({
                        "current_price": current_price,
                        "daily_change": daily_change,
                        "prices": prices
                    }, cache_file)

                print("Fetched and cached new price data.")
            return current_price, daily_change, prices
        else:
            return current_price, None, None
    except requests.RequestException as e:
        logging.error(f"Error fetching price data: {e}")
        return None, None, None
    
def update_price_chart(force_update=False):
    global last_price_update, app_running, fig, canvas, ax
    if not app_running:
        return  # Don't do anything if the app is not running
    
    current_time = time.time()
    if force_update or last_price_update == 0 or (current_time - last_price_update >= config['update_intervals']['price']): # If it's a force update, hasn't been updated, or the interval time has been met.
        try: 
            current_price, daily_change, prices = get_bitcoin_price()
            if prices and len(prices) > 0: # If we have price data and it's not empty
                fig.clear()
                ax = fig.add_subplot(111)
                ax.set_facecolor('#202222') # Set the background color # Light gray background
                fig.subplots_adjust(left=0.08, right=0.98, top=0.92, bottom=0.15) # Fix left margin for y-axis labels
                
                dates = [datetime.fromtimestamp(price[0]/1000) for price in prices]
                values = [price[1] for price in prices]

                if viewing_mode == "static":
                    # Full midnight-to-midnight EST (00:00-23:59)
                    est = pytz.timezone('US/Eastern')
                    now_est = datetime.now(est)
                    today_midnight = now_est.replace(hour=0, minute=0, second=0, microsecond=0)
                    today_midnight_naive = today_midnight.replace(tzinfo=None)
                    today_end = today_midnight.replace(hour=23, minute=59, second=59, microsecond=999999)
                    today_end_naive = today_end.replace(tzinfo=None)
                    
                    # Filter to today only (plot data we have)
                    plot_dates = [d for d in dates if today_midnight_naive <= d <= today_end_naive]
                    plot_values = [v for d, v in zip(dates, values) if today_midnight_naive <= d <= today_end_naive]
                    
                else:  # rolling - use full data
                    plot_dates = dates
                    plot_values = values

                ax.plot(plot_dates, plot_values, color='orange')
                fig.patch.set_facecolor('#191A1A')  # Slightly darker gray for figure background
                # title_color = ''
                if daily_change >= 0:
                    ax.set_title(f"฿itcoin Price: ${current_price:,.0f} - 24h Change: +{daily_change}%", color='green', loc='left', fontsize=16)
                    title_color = 'green'
                else:
                    ax.set_title(f"฿itcoin Price: ${current_price:,.0f} - 24h Change: -{abs(daily_change)}%", color='red', loc='left', fontsize=16)
                    title_color = 'red'
                # ax.set_xlabel("Time", color='white') # Do we really need this?
                # ax.set_ylabel("Price (USD)", color='white') # Leaving incase someone does!

                # Change axis colors to white
                #TODO: Chang these to change with the title color based on positive or negative change.
                ax.spines['top'].set_color(title_color)
                ax.spines['bottom'].set_color(title_color)
                ax.spines['left'].set_color(title_color)
                ax.spines['right'].set_color(title_color)
                
                # Change tick parameters
                ax.tick_params(axis='x', colors='white')  # X-axis ticks
                ax.tick_params(axis='y', colors='white')  # Y-axis ticks
                if time_series.lower() == "standard": # if time_series is set to standard
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%-I:%M %p'))
                else: # Otherwise, any other string returns military/Zulu.
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                
                # Define the currency formatter
                currency_formatter = mticker.FuncFormatter(lambda x, _: f'${x:,.0f}')
                ax.yaxis.set_major_formatter(currency_formatter) # Set the y-axis major formatter
                
                fig.tight_layout(pad=0.5, h_pad=0.8, w_pad=0.5)  # Minimal padding, max chart space                # FINAL STATIC X-AXIS LOCK - after all styling
                # Static full-day x-axis (LAST - overrides everything)
                if viewing_mode == "static":
                    est = pytz.timezone('US/Eastern')
                    now_est = datetime.now(est)
                    today_midnight = now_est.replace(hour=0, minute=0, second=0, microsecond=0)
                    today_midnight_naive = today_midnight.replace(tzinfo=None)
                    today_end = today_midnight.replace(hour=23, minute=59, second=59)
                    today_end_naive = today_end.replace(tzinfo=None)
                    ax.set_xlim(today_midnight_naive, today_end_naive)
                    ax.margins(x=0, y=0.05)  # Zero x-padding, 5% y-margin
                canvas.draw()
                
                # Redraw node info if available
                if previous_chain is not None:
                    update_node_table(previous_chain, previous_network, previous_fees)
                
                # This is overwriting the interval setting for updates. Need to update every hour or on the interval, whichever is smallest.
                last_price_update = current_time
                if app_running:
                    if price_timer_id is not None:
                        root.after_cancel(price_timer_id)
                    next_update_time = time_until_next_even_hour() * 1000
                    price_timer_id = root.after(int(next_update_time), update_price_chart)  # Capture ID

            else:
                # If we couldn't get prices, try again in 5 minutes
                root.after(300000, update_price_chart)
        except Exception as e:
            logging.error(f"Error updating price chart: {e}")
             # If there's an error, try again in 5 minutes
            root.after(300000, update_price_chart)
def get_node_info(rpc_connection):
    try:
        blockchain_info = rpc_connection.getblockchaininfo()
        network_info = rpc_connection.getnetworkinfo()
        fees = get_fee_estimates(rpc_connection)
        return blockchain_info, network_info, fees
    except Exception as e:
        logging.error(f"Error fetching node info: {e}")
        return None, None, None
def update_node_table(blockchain_data, network_data, fees):
    # Store blockchain info in global variables
    blockchain_chain = blockchain_data['chain']
    blockchain_blocks = f"{blockchain_data['blocks']}/{blockchain_data['headers']}"
    blockchain_verification_progress = f"{blockchain_data['verificationprogress'] * 100:.2f}%"
    #TODO: 
    # node_connections = f"{network_data['connections']}"
    #TODO: 
    # node_subversion = f"{network_data['subversion']}"
    #TODO: 
    # node_connections_in, node_connections_out = f"{network_data['connections_in']}", f"{network_data['connections_out']}"
                
    # Difficulty formatting
    difficulty = blockchain_data['difficulty']
    formatted_difficulty = format_difficulty(difficulty)
    
    if connect_to == 'raspiblitz': # This does nothing, can be changed when running on desktop as you can't fetch the cpu temp with this...
        # Do nothing
        # print("Changed this cuz I'm on Pi.")
        cpu_temp = get_cpu_temp()
    else:
        cpu_temp = get_cpu_temp()
    # Get fee estimates
    
    # Create or update the legend here
    if ax is not None:  # Ensure ax is defined
        if str(blockchain_verification_progress) == '100.00%':
            sync_text = 'OK'
            sync_color = 'green'
        else:
            sync_text = 'Sync In Progress'
            sync_color = 'orange'
        
        # Create text areas for each piece of information
        deviceName = TextArea(f"{connect_to}: ", textprops=dict(color='white', fontsize=12))
        chainName  = TextArea(f"{blockchain_chain}net", textprops=dict(color='cyan', fontsize=12))
        cpuTempName= TextArea(f"CPU Temp: ", textprops=dict(color='white', fontsize=12))
      
        if cpu_temp is None:
            cpuTempNumber = TextArea("N/A", textprops=dict(color='yellow', fontsize=12))
        else:
            degree_symbol = "\u00B0"
            if cpu_temp >= 85:
                color = 'red'
            elif cpu_temp >= 65:
                color = 'yellow'
            else:
                color = 'green'
            cpuTempNumber = TextArea(f"{cpu_temp}{degree_symbol}C", textprops=dict(color=color, fontsize=12))
    
        blocksName = TextArea("Blocks: ", textprops=dict(color='white', fontsize=12))
        blocksNumber = TextArea(f"{blockchain_blocks}", textprops=dict(color='yellow', fontsize=12))
        syncStatus = TextArea(f"{sync_text}", textprops=dict(color=sync_color, fontsize=12))
        verificationProgress = TextArea(f"{blockchain_verification_progress}", textprops=dict(color=sync_color, fontsize=12))
        difficultyName = TextArea(f"Difficulty: ", textprops=dict(color='white', fontsize=12))
        difficultyNumber = TextArea(f"{formatted_difficulty}", textprops=dict(color='yellow', fontsize=12))
        low_fee, medium_fee, high_fee = fees
        if low_fee and medium_fee and high_fee:
            feeText = TextArea("Fees (sat/vB): ", textprops=dict(color='white', fontsize=12))
            feeNumbers = TextArea(f"L:{low_fee:,} M:{medium_fee:,} H:{high_fee:,}", textprops=dict(color='yellow', fontsize=12))
        else:
            feeText = TextArea("Blockchain sync in progress", textprops=dict(color='orange', fontsize=12))
            feeNumbers = TextArea("", textprops=dict(color='yellow', fontsize=12))
        # TODO: Add connections in and out!
        
        # Arrange text areas horizontally and vertically
        row1 = HPacker(children=[deviceName, chainName], align="left", pad=0, sep=5)
        row2 = HPacker(children=[blocksName, blocksNumber, syncStatus, verificationProgress], align="left", pad=0, sep=5)
        row3 = HPacker(children=[feeText, feeNumbers], align="left", pad=0, sep=5)
        row4 = HPacker(children=[difficultyName, difficultyNumber, cpuTempName, cpuTempNumber], align="left", pad=0, sep=5)
        box = VPacker(children=[row1, row2, row3, row4], align="left", pad=0, sep=5)

        # Lower left of the chart
        fig.subplots_adjust(bottom=0.12)  # Increase bottom margin # Adjust the plot layout to make room for the box
        anchored_box = AnchoredOffsetbox(loc=3, child=box, pad=0.5, frameon=True, # Create the anchored box
                                            bbox_to_anchor=(0.01, 0.02),
                                            bbox_transform=ax.transAxes,
                                            borderpad=0) 
        
        anchored_box.patch.set_boxstyle("round,pad=0.5")
        anchored_box.patch.set_facecolor('black')
        anchored_box.patch.set_alpha(0.5)
        for artist in ax.texts: # Clear previous text
            artist.remove()
        # Remove old boxes
        for child in ax.get_children():
            if isinstance(child, AnchoredOffsetbox):
                child.remove()
        ax.add_artist(anchored_box) # Add the new anchored box
        # Testing
        # Optimal margins for big figure
        fig.subplots_adjust(
            left=0.09,      # Y-axis labels
            right=0.98,     # Edge-to-edge right
            top=0.92,       # Title fits
            bottom=0.08,    # Minimal bottom for node info
            wspace=0.2,     # Horizontal subplot spacing
            hspace=0.2      # Vertical subplot spacing
        )
        canvas.draw_idle() # Update the canvas to reflect the changes
    return  

def update_blockchain_info(force_update=False):
    global app_running, root, last_blockchain_update, blockchain_chain, blockchain_blocks, blockchain_verification_progress, node_connections, cpu_temp, previous_chain, previous_network, previous_fees, saved_timestamp
    if not app_running:
        return  # Don't do anything if the app is not running
    # Trying to pass in blockchain and network info to this update function.
    current_time = time.time()
    if force_update or (current_time - last_blockchain_update >= config['update_intervals']['blockchain']): # 600 seconds = 10 minutes
        if saved_timestamp == get_timestamp():
            print("Node not available - Check node connection!")
            logging.error(f"Error connecting to RPC Node. {saved_timestamp}")
        else:
            try: # Let's update info
                new_chain_info, new_network_info, fees = get_node_info(rpc_connection)
                saved_timestamp = get_timestamp()
                # If successful go to bottom to call update_node_table function
                update_node_table(new_chain_info, new_network_info, fees) # Call the update function if we're able to connect
                # Store previous values
                previous_chain = new_chain_info         # Update variable with newest data
                previous_network = new_network_info     # Update variable with newest data
                previous_fees = fees
                last_blockchain_update = current_time   # Update the last update time before exiting udpate function                
                # next_update_time = time_until_next_10min() * 1000  # Next 10-min mark
                # root.after(next_update_time, update_blockchain_info)
                if app_running:
                    if blockchain_timer_id is not None:
                        root.after_cancel(blockchain_timer_id)
                    next_update_time = time_until_next_10min() * 1000
                    blockchain_timer_id = root.after(int(next_update_time), update_blockchain_info)
                return  # Exit early after scheduling
            except Exception as e: # Failure of RPC connection here
                    logging.error(f"{get_timestamp()} - Error updating blockchain info: Expected on first try. {e}")
                    try: # Attempt to reconnect
                        update_blockchain_info() # Retry the blockchain pull
                    except Exception as e:
                        logging.error(f"{get_timestamp()} - UNEXPECTED - Failed to reconnect. Will try again in the next update. {e}")

def format_difficulty(difficulty):
    if difficulty >= 1_000_000_000_000:  # If it's in trillions
        return f"{difficulty / 1_000_000_000_000:.2f}T"
    elif difficulty >= 1_000_000_000:  # If it's in billions
        return f"{difficulty / 1_000_000_000:.2f}B"
    elif difficulty >= 1_000_000:  # If it's in millions
        return f"{difficulty / 1_000_000:.2f}M"
    else:
        return f"{difficulty:,.2f}"

# Create and run the display
try:
    root = create_display() # Initial call
    # root.config(cursor="none") # Get rid of that blasted cursor!
    update_price_chart()
    update_blockchain_info()
    root.mainloop()
except tk.TclError as e: # Catch when DISPLAY is not setup correctly.
    logging.error(f"An error occured while creating the display. {e} \n Normally this can be fixed by adding 'DISPLAY=:0.0' to bitcoin_env/bin/activate line 38. ")
except KeyboardInterrupt as e: # Catch when user interupts program.
    logging.error(f"User interupted program. {e}. Are you trying to start remotely? Use 'nohup' before running. 'nohup python3 piDisplay.py'")
except Exception as e: # Catch all other errors here.
    logging.error(f"An error occurred when initializing the app. {e}")

def main():
    global root
    try:
        root = create_display()
        update_display() # Start the scheduling loop
        root.mainloop()
    except tk.TclError as e:
        logging.error(
            f"An error occurred while creating the display. {e} "
            "If running headless, ensure DISPLAY is set correctly."
        )
    except KeyboardInterrupt as e:
        logging.error(f"User interrupted program. {e}")
    except Exception as e:
        logging.error(f"An error occurred when initializing the app. {e}")

if __name__ == "__main__":
    main()

# TODO: Move functions into a library file and import them here to clean up the main display code.