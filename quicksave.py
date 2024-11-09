from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
from datetime import datetime, timedelta
import requests
import tkinter as tk
from tkinter import ttk
import os
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
import time

get_rpc = True # Turn on if not testing on local (desktop) Turns on rpc stuff.

last_price_update = 0 # Variable for tracking when to update price

# Replace with your Parmanode's RPC credentials
rpc_user = 'satoshi'
rpc_password = 'Waffle9d9RPC123PaSSw0rd'
rpc_host = '192.168.86.49'  # localhost
rpc_port = '8332'  # default Bitcoin Core RPC port

rpc_connection = AuthServiceProxy(f"http://{rpc_user}:{rpc_password}@{rpc_host}:{rpc_port}", timeout=120)

# Functions
def get_cpu_temp():
    temp = os.popen("vcgencmd measure_temp").readline()
    return float(temp.replace("temp=","").replace("'C",""))
def on_escape(event):
    root.quit()
def get_bitcoin_price():
    try:
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
            return current_price, daily_change, prices
        else:
            return current_price, None, None
    except requests.RequestException as e:
        print(f"Error fetching price data: {e}")
        return None, None, None
def create_price_chart(prices):
    fig, ax = plt.subplots(figsize=(20, 10))
    dates = [datetime.fromtimestamp(price[0]/1000) for price in prices]
    values = [price[1] for price in prices]
    ax.plot(dates, values)
    ax.set_title("Bitcoin Price (Last 24 Hours)")
    ax.set_xlabel("Time")
    ax.set_ylabel("Price (USD)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    return fig 
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
    global last_price_update
    last_price_update = time.time() - 3600
    
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

    labels = {}
    row = 0
    for key in ["Bitcoin Price", "Cat Neuters", "Chain", "Blocks", "Headers", "Verification Progress", "Difficulty", "Connections", "CPU Temperature"]:
        ttk.Label(frame, text=f"{key}:").grid(column=0, row=row, sticky=tk.W)
        labels[key] = ttk.Label(frame, text="")
        labels[key].grid(column=1, row=row, sticky =tk.W)
        row += 1
    # Create a frame for the chart
    chart_frame = ttk.Frame(root)
    chart_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Create an initial empty chart
    fig = plt.Figure(figsize=(8, 3))
    canvas = FigureCanvasTkAgg(fig, master=chart_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
    def update_display():
        global last_price_update
        current_time = time.time()
        
        if current_time - last_price_update >= 3600: # 3600 seconds = 1 hour
            try:
                current_price, daily_change, prices = get_bitcoin_price()
                if prices: # Update the chart if price data exists
                    fig.clear()
                    ax = fig.add_subplot(111)
                    dates = [datetime.fromtimestamp(price[0]/1000) for price in prices]
                    values = [price[1] for price in prices]
                    ax.plot(dates, values)
                    ax.set_title("Bitcoin Price (Last 24 Hours)")
                    ax.set_xlabel("Time")
                    ax.set_ylabel("Price (USD)")
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                    plt.xticks(rotation=45)
                    fig.tight_layout()
                    canvas.draw()
                    create_price_chart(prices)
            except Exception as e:
                print(f"Error getting Bitcoin price: {e}")
                current_price, daily_change = None, None, None

            if daily_change >= 0:
                labels["Bitcoin Price"].config(text=f"${current_price:,.0f} (+{daily_change}%)")
            else:
                labels["Bitcoin Price"].config(text=f"${current_price:,.0f} (-{daily_change}%)")
            labels['Cat Neuters'].config(text=current_price / 50)
        if get_rpc:
            try:
                blockchain_info = rpc_connection.getblockchaininfo()
            except Exception as e:
                print(f"Error getting blockchain info: {e}")
            blockchain_info = None

            try:
                network_info = rpc_connection.getnetworkinfo()
            except Exception as e:
                print(f"Error getting network info: {e}")
                network_info = None
            try:    
                labels["Chain"].config(text=blockchain_info['chain'])
                labels["Blocks"].config(text=str(blockchain_info['blocks']))
                labels["Headers"].config(text=str(blockchain_info['headers']))
                labels["Verification Progress"].config(text=f"{blockchain_info['verificationprogress'] * 100:.2f}%")
                difficulty = blockchain_info['difficulty']
                formatted_difficulty = format_difficulty(difficulty)
                labels["Difficulty"].config(text=formatted_difficulty)
                labels["Connections"].config(text=str(network_info['connections']))
                
                cpu_temp = get_cpu_temp()
                labels["CPU Temperature"].config(text=f"{cpu_temp:.1f}°C")
            except JSONRPCException as json_exception:
                print(f"A JSON RPC Exception occurred: {json_exception}")
            # Attempt to reconnect
            try:
                rpc_connection._BaseProxy__client.reconnect()
            except Exception as e:
                print(f"Failed to reconnect. Will try again in the next update. {e}")
        
        
        exit_button.lift() # Ensure the exit button stays on top
        # Schedule the next update
        root.after(60000, update_display)
    update_display() # Initial call to update display
    return root

# Create and run the display
root = create_display(rpc_connection)
root.mainloop()