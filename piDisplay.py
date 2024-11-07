from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
from datetime import datetime, timedelta
import requests
import tkinter as tk
from tkinter import ttk
import os

# Replace with your Parmanode's RPC credentials
rpc_user = 'satoshi'
rpc_password = 'Waffle9d9RPC123PaSSw0rd'
rpc_host = '192.168.86.49'  # localhost
rpc_port = '8332'  # default Bitcoin Core RPC port

rpc_connection = AuthServiceProxy(f"http://{rpc_user}:{rpc_password}@{rpc_host}:{rpc_port}")

# Functions
def get_cpu_temp():
    temp = os.popen("vcgencmd measure_temp").readline()
    return float(temp.replace("temp=","").replace("'C",""))
def get_bitcoin_price():
    # Current price
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
    response = requests.get(url)
    current_data = response.json()
    current_price = current_data["bitcoin"]["usd"]

    # Previous close price (24 hours ago)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1)

    # Convert to timestamps
    start_timestamp = int(start_date.timestamp())
    end_timestamp = int(end_date.timestamp())

    historical_url = f"https://api.coingecko.com/api/v3/coins/bitcoin/market_chart/range?vs_currency=usd&days=1&start={start_timestamp}&end={end_timestamp}"
    historical_response = requests.get(historical_url)
    historical_data = historical_response.json()

    # Get the prices for the last 24 hours
    prices = historical_data['prices']
    
    if prices:
        previous_close_price = prices[0][1]  # The first entry is the oldest price (previous close)
        daily_change = (current_price - previous_close_price) / previous_close_price  # Calculate daily change
        return current_price, daily_change
    else:
        return current_price, None, None  # Handle case where no historical data is returned
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
    root = tk.Tk()
    root.title("Bitcoin Node Information")
    root.attributes('-fullscreen', True) # Full screen this bish
    root.configure(bg='black')

    frame = ttk.Frame(root, padding="10")
    frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    labels = {}
    row = 0
    for key in ["Bitcoin Price", "Chain", "Blocks", "Headers", "Verification Progress", "Difficulty", "Connections", "CPU Temperature"]:
        ttk.Label(frame, text=f"{key}:").grid(column=0, row=row, sticky=tk.W)
        labels[key] = ttk.Label(frame, text="")
        labels[key].grid(column=1, row=row, sticky =tk.W)
        row += 1

    def update_display():
        try:
            # Attempt to reconnect if the connection is closed
            if not rpc_connection._BaseProxy__client.connected:
                rpc_connection._BaseProxy__client.reconnect()
            blockchain_info = rpc_connection.getblockchaininfo()
            network_info = rpc_connection.getnetworkinfo()
            current_price, daily_change = get_bitcoin_price()
            
            if daily_change >= 0:
                labels["Bitcoin Price"].config(text=f"${current_price:,.0f} (+{daily_change})")
            else:
                labels["Bitcoin Price"].config(text=f"${current_price:,.0f} (-{daily_change})")

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
            except:
                print("Failed to reconnect. Will try again in the next update.")
        except Exception as e:
            print(f"An error occurred: {e}")

        # Schedule the next update
        root.after(60000, update_display)

    # update_display() # Initial call to update display
    return root

# Create and run the display
root = create_display(rpc_connection)
root.mainloop()