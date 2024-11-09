from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
from datetime import datetime, timedelta
import requests
import tkinter as tk
from tkinter import ttk
import os
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
import time
from datetime import datetime
import logging
import json

CACHE_FILE = 'bitcoin_price_cache.json'
get_rpc = True # Turn on if not testing on local (desktop) Turns on rpc stuff.
last_price_update = 0 # Variable for tracking when to update price
last_blockchain_update = 0 # Variable for tracking when to update blockchain info
fig = None # Creating global fig
canvas = None # Creating global canvas
labels = {} # Adding global label
# Global variables to hold blockchain info
blockchain_chain = ""
blockchain_blocks = ""
blockchain_verification_progress = ""
node_connections = ""
cpu_temp = ""

# Replace with your Parmanode's RPC credentials
connect_to = 'raspiblitz' # or "parmanode"
if connect_to == 'raspiblitz':
    rpc_user = 'raspibolt'
    rpc_host = '192.168.86.68'  # localhost
else:
    rpc_user = 'satoshi'
    rpc_host = '192.168.86.49'  # localhost

rpc_password = 'Waffle9d9RPC123PaSSw0rd'
rpc_port = '8332'  # default Bitcoin Core RPC port


rpc_connection = AuthServiceProxy(f"http://{rpc_user}:{rpc_password}@{rpc_host}:{rpc_port}", timeout=240)

logging.basicConfig(
    filename='bitcoin_display.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
# Functions
def get_cpu_temp():
    temp = os.popen("vcgencmd measure_temp").readline()
    return float(temp.replace("temp=","").replace("'C",""))
def on_escape(event):
    root.quit()
def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def get_bitcoin_price():
    try:
        # Check if cache file exists
        if os.path.exists(CACHE_FILE):
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
            previous_close_price = prices[0][1]  # The first entry is the oldest price (previous close)
            daily_change = (current_price - previous_close_price) / previous_close_price * 100 # Daily Change as percentage
            daily_change = round(daily_change, 2)
            # Save the fetched data to cache
            with open(CACHE_FILE, 'w') as cache_file:
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
        print(f"Error fetching price data: {e}")
        logging.error(f"Error fetching price data: {e}")
        return None, None, None
def update_price_chart():
    global last_price_update, fig, canvas, labels
    current_time = time.time()
    print(f"Update Price Chart function: Check time? : {current_time-last_price_update} : Update over 3600")
    if current_time - last_price_update >= 3600:  # Update every hour
        try:
            current_price, daily_change, prices = get_bitcoin_price()
            if prices:
                fig.clear()
                ax = fig.add_subplot(111)
                ax.set_facecolor('#202222') # Set the background color # Light gray background
                dates = [datetime.fromtimestamp(price[0]/1000) for price in prices]
                values = [price[1] for price in prices]
                ax.plot(dates, values, color='orange') # Color of plt line (price)
                fig.patch.set_facecolor('#191A1A')  # Slightly darker gray for figure background
                ax.set_title(f"Bitcoin Price (Last 24 Hours) - Current Price: ${current_price:,.0f}", color='white')
                ax.set_xlabel("Time", color='white')
                ax.set_ylabel("Price (USD)", color='white')
                # Change axis colors to white
                ax.spines['top'].set_color('white')
                ax.spines['bottom'].set_color('white')
                ax.spines['left'].set_color('white')
                ax.spines['right'].set_color('white')
                # Change tick parameters
                ax.tick_params(axis='x', colors='white')  # X-axis ticks
                ax.tick_params(axis='y', colors='white')  # Y-axis ticks
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                plt.xticks(rotation=45)
                print(f"Blockchain Status: {blockchain_verification_progress}")
                # Legend stuff here
                if blockchain_verification_progress == 100:
                    sync_text = 'OK'
                else:
                    sync_text = 'Sync In Progress'
                legend_text = f"{connect_to}: {blockchain_chain}net\nBlocks: {blockchain_blocks} {sync_text} {blockchain_verification_progress}"
                dummy_line = Line2D([0], [0], color='none')  # No visible line # Create a dummy Line2D object for the legend (invisible)
                ax.legend([dummy_line], [legend_text], loc='upper left', fontsize='medium', facecolor='white', framealpha=0.5) # Create a custom legend without a line
                
                fig.tight_layout(pad=1.5) # Increased padding for X axis
                canvas.draw()

            if daily_change >= 0:
                labels["Bitcoin Price"].config(text=f"${current_price:,.0f} (+{daily_change}%)")
            else:
                labels["Bitcoin Price"].config(text=f"${current_price:,.0f} ({daily_change}%)")
            print(f"Last Update: {last_price_update} vs. Current Time {current_time}")
            last_price_update = current_time
            print(f"Last Update: {last_price_update} vs. Current Time {current_time}")
        except Exception as e:
            print(f"Error updating price chart: {e}")
            logging.error(f"Error updating price chart: {e}")

def update_blockchain_info():
    global last_blockchain_update, labels, blockchain_chain, blockchain_blocks, blockchain_verification_progress, node_connections, cpu_temp

    current_time = time.time()
    print(f"Update Blockchain info?: {current_time - last_blockchain_update} >= 600")
    if current_time - last_blockchain_update >= 600: # 600 seconds = 10 minutes
        if get_rpc:
            try:
                print("Yes\nGetting blockchain info")
                blockchain_info = rpc_connection.getblockchaininfo()
                # print(blockchain_info)
                print("Getting network info")
                network_info = rpc_connection.getnetworkinfo()
                # print(network_info)
                # Store blockchain info in global variables
                blockchain_chain = blockchain_info['chain']
                blockchain_blocks = f"{blockchain_info['blocks']}/{blockchain_info['headers']}"
                blockchain_verification_progress = f"{blockchain_info['verificationprogress'] * 100:.2f}%"
                node_connections = f"{network_info['connections']}"
                
                # Difficulty formatting
                difficulty = blockchain_info['difficulty']
                formatted_difficulty = format_difficulty(difficulty)
                # labels["Difficulty"].config(text=formatted_difficulty)
                # labels["Connections"].config(text=str(network_info['connections']))
                
                cpu_temp = get_cpu_temp()
                # labels["CPU Temperature"].config(text=f"{cpu_temp:.1f}°C")
                last_blockchain_update = current_time  # Update the last update time
            except Exception as e:
                print(f"{get_timestamp()} - Error updating blockchain info: {e}")
                logging.error(f"{get_timestamp()} - Error updating blockchain info: {e}")
                try: # Attempt to reconnect
                    rpc_connection._BaseProxy__client.reconnect()
                except Exception as e:
                    print(f"{get_timestamp()} - Failed to reconnect. Will try again in the next update. {e}")
                    logging.error(f"{get_timestamp()} - Failed to reconnect. Will try again in the next update. {e}")

def format_difficulty(difficulty):
    if difficulty >= 1_000_000_000_000:  # If it's in trillions
        return f"{difficulty / 1_000_000_000_000:.2f}T"
    elif difficulty >= 1_000_000_000:  # If it's in billions
        return f"{difficulty / 1_000_000_000:.2f}B"
    elif difficulty >= 1_000_000:  # If it's in millions
        return f"{difficulty / 1_000_000:.2f}M"
    else:
        return f"{difficulty:,.2f}"

def create_display(rpc_connection):
    global last_price_update, fig, canvas, labels
    root = tk.Tk()
    root.title("Bitcoin Node Information")
    root.attributes('-fullscreen', True) # Full screen this bish
    # root.configure(bg='black')

    #Configure grid
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(1, weight=1)
    
    root.bind('<Escape>', on_escape) # this line binds the Escape key
    exit_button = tk.Button(root, text="Exit", command=root.quit, bg='red', fg='white') # Add this line to create an exit button on touch screen
    exit_button.place(relx=1.0, rely=0.0, anchor='ne')  # Place in top-right corner
    # Variables for long press detection
    press_start_time = [None]
    long_press_duration = 2  # seconds

    def on_press(event):
        press_start_time[0] = time.time()

    def on_release(event):
        if press_start_time[0] is not None:
            press_duration = time.time() - press_start_time[0]
            if press_duration >= long_press_duration:
                root.quit()
        press_start_time[0] = None

    root.bind('<ButtonPress-1>', on_press)
    root.bind('<ButtonRelease-1>', on_release)
    frame = ttk.Frame(root, padding="10")
    frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Create a frame for the chart
    chart_frame = ttk.Frame(root)
    chart_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Create an initial empty chart
    fig = plt.Figure(figsize=(8, 3))
    canvas = FigureCanvasTkAgg(fig, master=chart_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
    def update_display():
        print("Restarting from update_display")
        exit_button.lift()  # Ensure the exit button stays on top
        print("Updating price again?")
        update_price_chart()
        print("Inside update_display looking to update blockchain info")
        update_blockchain_info()
        print("Waiting 10 minute now.")
        root.after(60000 * 10, update_display)  # Schedule next price update in 1 minute
            
    # Initial calls when launching app
    update_price_chart()
    root.after(100, update_blockchain_info)  # Start blockchain update after 100ms   
    root.after(100, update_display)  # Schedule regular updates 
    return root

# Create and run the display
root = create_display(rpc_connection)
root.mainloop()