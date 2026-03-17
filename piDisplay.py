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
if args.testing:
    config['testing'] = True

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

# Global Variables
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

def update_display():
    global app_running
    if not app_running:
        return  # Don't do anything if the app is not running   
    update_price_chart()      # Checks its own schedule internally
    update_blockchain_info()  # Checks its own schedule internally
    if app_running:
        root.after(300000, update_display) # Check every 5 minutes if we need to update either

def create_display():
    global root, fig, canvas
    root = tk.Tk()
    root.title("Bitcoin Node Information")

    if IS_PI:
        # Fullscreen for Pi display
        root.overrideredirect(True)
        root.geometry("{0}x{1}+0+0".format(
            root.winfo_screenwidth(), root.winfo_screenheight()
        ))
        root.config(cursor="none")
    else:
        # Desktop: normal window, optionally set a reasonable size
        root.geometry("1024x600")  # or whatever matches your Pi resolution
    
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

    chart_frame = ttk.Frame(root)
    chart_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    fig = plt.Figure(figsize=(8, 3))
    canvas = FigureCanvasTkAgg(fig, master=chart_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    exit_button.lift()
    return root

rpc_connection = AuthServiceProxy(f"http://{rpc_user}:{rpc_password}@{rpc_host}:{rpc_port}", timeout=30)

logging.basicConfig(
    filename='bitcoin_display.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Functions
def proper_exit():
    global root, app_running
    app_running = False
    root.destroy()  # This cancels ALL pending after() calls automatically
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
        
        if prices and app_running: # If we have price data and the app is still running
            fig.clear() # Clear the figure before plotting new data
            previous_close_price = prices[0][1]  # The first entry is the oldest price (previous close)
            daily_change = (current_price - previous_close_price) / previous_close_price * 100 # Daily Change as percentage
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
            if prices: # If we have price data
                fig.clear()
                ax = fig.add_subplot(111)
                ax.set_facecolor('#202222') # Set the background color # Light gray background
                # dates = [datetime.fromtimestamp(price[0]/1000) for price in prices] # Convert timestamps to datetime objects
                # values = [price[1] for price in prices]

                # # if viewing_mode == "rolling":
                # ax.plot(dates, values, color='orange') # Color of plt line (price)
                # # else: # static
                
                dates = [datetime.fromtimestamp(price[0]/1000) for price in prices]
                values = [price[1] for price in prices]

                if viewing_mode == "static":
                    # Midnight to now EST
                    est = pytz.timezone('US/Eastern')
                    now_est = datetime.now(est)
                    today_midnight = now_est.replace(hour=0, minute=0, second=0, microsecond=0)
                    
                    # Filter to today only
                    plot_dates = [d for d in dates if d >= today_midnight]
                    plot_values = [v for d, v in zip(dates, values) if d >= today_midnight]
                else:  # rolling - use full data
                    plot_dates = dates
                    plot_values = values

                ax.plot(plot_dates, plot_values, color='orange')

                fig.patch.set_facecolor('#191A1A')  # Slightly darker gray for figure background
                if daily_change >= 0:
                    ax.set_title(f"฿itcoin Price: ${current_price:,.0f} - 24h Change: +{daily_change}%", color='green', loc='left', fontsize=16)
                else:
                    ax.set_title(f"฿itcoin Price: ${current_price:,.0f} - 24h Change: -{abs(daily_change)}%", color='red', loc='left', fontsize=16)
                # ax.set_xlabel("Time", color='white') # Do we really need this?
                # ax.set_ylabel("Price (USD)", color='white') # Leaving incase someone does!
                
                # Add timestamp
                #TODO Neither are working.
                if time_series == "standard":
                    timestamp = datetime.now().strftime('%-I:%M %p')
                    # timestamp = datetime.now().strftime('%#I:%M %p')
                else:
                    timestamp = datetime.now().strftime("%m/%d/%Y - %H:%M") 
                # anchored_time = AnchoredText(timestamp, loc=2, prop=dict(color='white', size=10), frameon=False)
                # ax.add_artist(anchored_time) # Moving below so I can use one single legend

                # Getting price values
                # price_values = [price[1] for price in prices]
                # high_price, low_price = max(price_values), min(price_values)
                # Getting price values (use filtered data)
                price_values = plot_values
                high_price, low_price = max(price_values), min(price_values)
                formatted_high_price, formatted_low_price = "${:,.0f}".format(high_price), "${:,.0f}".format(low_price)
        
                # Add labels for high and low prices
                plt.plot([], [], label=f'24H High: {formatted_high_price}', linestyle='None', marker='None')
                plt.plot([], [], label=f'24H Low: {formatted_low_price}', linestyle='None', marker='None')
                # Add the legend outside the plot at the bottom
                plt.legend(loc='best', ncol=2)

                text = f"{timestamp}\n24H High: {formatted_high_price}\n24H Low: {formatted_low_price}"
                anchored_time = AnchoredText(text, loc=2, prop=dict(color='white', size=10), frameon=False)
                ax.add_artist(anchored_time)

                # Change axis colors to white
                ax.spines['top'].set_color('white')
                ax.spines['bottom'].set_color('white')
                ax.spines['left'].set_color('white')
                ax.spines['right'].set_color('white')
                
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
                
                fig.tight_layout() # Increased padding for X axis
                # fig.tight_layout(rect=[0, 0.03, 1, 0.95])
                canvas.draw()
                
                # This is overwriting the interval setting for updates. Need to update every hour or on the interval, whichever is smallest.
                last_price_update = current_time
                if app_running:
                    next_update_time = time_until_next_even_hour() * 1000 # Schedule the next update at the top of the next hour
                    root.after(next_update_time, update_price_chart)

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
        fig.subplots_adjust(bottom=0.2)  # Increase bottom margin # Adjust the plot layout to make room for the box
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
                next_update_time = time_until_next_10min() * 1000  # Next 10-min mark
                root.after(next_update_time, update_blockchain_info)
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
    root.config(cursor="none") # Get rid of that blasted cursor!
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