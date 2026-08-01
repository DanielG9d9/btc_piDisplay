# Built by Danny Blue-Eyes
from matplotlib.offsetbox import AnchoredOffsetbox, TextArea, VPacker, HPacker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.colors import LinearSegmentedColormap, Normalize
from bitcoinrpc.authproxy import AuthServiceProxy
from matplotlib.offsetbox import AnchoredText
from matplotlib.collections import LineCollection
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
import numpy as np
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
BASE_DIR = pathlib.Path(__file__).resolve().parent
config_path = args.config or os.environ.get('PIDISPLAY_CONFIG')
if not config_path:
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
color_scheme = config.get('color_scheme', 'static').lower()  # 'static' = fixed accent, 'dynamic' = green/red by price direction
COLOR_SCHEME_INTERVAL_MINUTES = {'daily': 1440, 'hourly': 60, '30min': 30, '15min': 15, '5min': 5}
color_scheme_interval = config.get('color_scheme_interval', 'hourly').lower()
color_scheme_interval_minutes = COLOR_SCHEME_INTERVAL_MINUTES.get(color_scheme_interval, 60)
chart_type = config.get('chart_type', 'line').lower()  # 'line' or 'candlestick'
ALTERNATING_INTERVAL_SECONDS = {'30s': 30, '1m': 60, '5m': 300}
chart_alternating = config.get('chart_alternating', 'off').lower()  # 'off' or 'on'
chart_alternating_interval = config.get('chart_alternating_interval', '30s').lower()
chart_alternating_interval_seconds = ALTERNATING_INTERVAL_SECONDS.get(chart_alternating_interval, 30)

# Price refresh cadence always matches color_scheme_interval, so a 5-minute
# interval both fetches and displays fresh data every 5 minutes — no separate
# setting to keep in sync.
config['update_intervals']['price'] = color_scheme_interval_minutes * 60
testing = config['testing']

connect_to = config['connect_to']
rpc_settings = config['rpc_settings'][connect_to]
rpc_user = rpc_settings['rpc_user']
rpc_host = rpc_settings['rpc_host']
rpc_password = rpc_settings['rpc_password']
rpc_port = rpc_settings['rpc_port']
# Relative cache/log paths are resolved against the repo directory (BASE_DIR),
# not the process's working directory, so they land in the repo regardless of
# where the launching script `cd`s to (e.g. install.sh's Desktop launcher).
CACHE_FILE = str(BASE_DIR / config['cache_file'])
MINING_CACHE_FILE = str(BASE_DIR / config.get('mining_cache_file', 'bitcoin_mining_cache.json'))
# How much hashrate/difficulty history to pull for the mining chart. One of
# mempool.space's fixed periods: 3d, 1w, 1m, 3m, 6m, 1y, 2y, 3y, all.
MINING_CHART_PERIOD = config.get('mining_chart_period', '1y')

# Set up logging
log_file = config['testing_log_file'] if testing else config['log_file']
if not os.path.isabs(log_file):
    log_file = str(BASE_DIR / log_file)
log_kwargs = dict(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
try:
    logging.basicConfig(filename=log_file, **log_kwargs)
except OSError:
    # Configured log path (e.g. the Pi's log_file) doesn't exist on this machine.
    fallback_log = str(BASE_DIR / "bitcoin_display.log")
    logging.basicConfig(filename=fallback_log, **log_kwargs)
    logging.warning(f"Could not open configured log file '{log_file}'; falling back to '{fallback_log}'.")

# RPC connection
rpc_connection = AuthServiceProxy(f"http://{rpc_user}:{rpc_password}@{rpc_host}:{rpc_port}", timeout=30)

# Global Variables (Globals)
last_price_update = 0 # Variable for tracking when to update price
last_blockchain_update = 0 # Variable for tracking when to update blockchain info
fig = None # Creating global fig
canvas = None # Creating global canvas
previous_chain, previous_network, previous_fees = None, None, None
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
chart_alternation_timer_id = None
# Timestamp of the last time the countdown-triggered update was fired. Used
# to avoid repeatedly forcing updates during the ~1s window where the
# countdown displays "00:00" as update_countdown runs every 100ms.
last_countdown_trigger_time = 0
current_screen = "main"  # "main" or "more"
chart_mode = "price"  # "price" or "mining" — which chart the main screen shows
last_mining_update = 0  # Variable for tracking when to update mining info
chart_frame = None
more_fig = None
more_canvas = None
more_ax = None
countdown_label = None
exit_button = None
more_button = None
mining_button = None
options_button = None
toolbar_frame = None
settings_window = None

SETTINGS_OPTIONS = {
    'viewing_mode': ['static', 'rolling'],
    'color_scheme': ['static', 'dynamic'],
    'chart_type': ['line', 'candlestick', 'baseline'],
    'color_scheme_interval': ['daily', 'hourly', '30min', '15min', '5min'],
    'chart_alternating': ['off', 'on'],
    'chart_alternating_interval': ['30s', '1m', '5m'],
}
SETTINGS_LABELS = {
    'viewing_mode': 'Viewing Mode',
    'color_scheme': 'Color Scheme',
    'chart_type': 'Chart Type',
    'color_scheme_interval': 'Interval',
    'chart_alternating': 'Chart',
}

# Display Settings pop-up sizing: fonts, padding and button sizes are all
# multiplied by this, so the window stays proportional. It's a touch target on
# the Pi's small screen, so everything is deliberately oversized rather than
# desktop-sized; build_settings_window() scales back down if the result would
# not fit the display.
SETTINGS_SCALE = 2

PALETTE = {
    'page': '#0d0d0d',
    'surface': '#1a1a19',
    'primary': '#ffffff',
    'secondary': '#c3c2b7',
    'muted': '#898781',
    'grid': '#2c2c2a',
    'baseline': '#383835',
    'good': '#0ca30c',
    'critical': '#d03b3b',
    'accent': '#005678',
}

# Colors the 1-week hashrate trend line relative to its own min/max, matching
# mempool.space's mining chart (green at the low end shading through yellow
# to red/pink at the high end) instead of one flat color.
HASHRATE_GRADIENT = LinearSegmentedColormap.from_list(
    'hashrate_gradient', [PALETTE['good'], '#e8a33d', '#d6336c']
)

def save_config_value(key, value):
    """Persist a single display setting to config.json, without disturbing
    other keys or writing back runtime-derived fields (e.g. update_intervals.price).
    Re-reads the file fresh so it only ever patches the one key."""
    try:
        with open(config_path, 'r') as f:
            on_disk = json.load(f)
        on_disk[key] = value
        with open(config_path, 'w') as f:
            json.dump(on_disk, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving config setting '{key}': {e}")

def apply_setting_change(key, value):
    """Update a display setting live, persist it to config.json, and
    immediately re-render the chart from cache so the change is visible
    right away (used by the More screen's settings controls)."""
    global viewing_mode, color_scheme, chart_type, color_scheme_interval, color_scheme_interval_minutes
    global chart_alternating, chart_alternating_interval, chart_alternating_interval_seconds

    # Whether this key affects the price chart's own rendering (and so needs
    # an immediate re-render) — false for the chart-alternation settings,
    # which just start/stop a timer and shouldn't yank the visible chart
    # back to price out from under the mining dashboard.
    affects_price_chart = True

    if key == 'viewing_mode':
        viewing_mode = value
    elif key == 'color_scheme':
        color_scheme = value
    elif key == 'chart_type':
        chart_type = value
    elif key == 'color_scheme_interval':
        color_scheme_interval = value
        color_scheme_interval_minutes = COLOR_SCHEME_INTERVAL_MINUTES.get(value, 60)
        config['update_intervals']['price'] = color_scheme_interval_minutes * 60
    elif key == 'chart_alternating':
        chart_alternating = value
        affects_price_chart = False
        restart_chart_alternation()
    elif key == 'chart_alternating_interval':
        chart_alternating_interval = value
        chart_alternating_interval_seconds = ALTERNATING_INTERVAL_SECONDS.get(value, 30)
        affects_price_chart = False
        restart_chart_alternation()

    save_config_value(key, value)
    if affects_price_chart and chart_mode == "price":
        # These settings only affect the price chart; the mining dashboard
        # ignores them, so don't yank the visible chart away from it.
        update_price_chart_from_cache()

def update_display():
    global app_running
    if not app_running:
        return  # Don't do anything if the app is not running
    if chart_mode == "mining":
        update_mining_dashboard()  # Checks its own schedule internally
    else:
        update_price_chart()       # Checks its own schedule internally
    update_blockchain_info()  # Checks its own schedule internally
    if app_running:
        display_timer_id = root.after(300000, update_display)

def create_display():
    global root, fig, canvas, chart_frame, exit_button, more_button, mining_button, options_button, countdown_label, toolbar_frame
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

    # Calculate initial countdown
    try:
        initial_seconds = time_until_next_aligned_update(config['update_intervals']['price'])
        initial_minutes = int(initial_seconds // 60)
        initial_secs = int(initial_seconds % 60)
        initial_text = f"{initial_minutes:02d}:{initial_secs:02d}"
    except:
        initial_text = "00:00"

    # Single toolbar frame so the countdown/Node/Options/Exit controls share one
    # baseline and consistent spacing instead of being independently
    # placed by relx (which drifts out of alignment as widget widths differ).
    global toolbar_frame
    toolbar_frame = tk.Frame(root, bg=PALETTE['page'])
    toolbar_frame.place(relx=1.0, rely=0.0, anchor='ne', x=-10, y=8)

    button_style = dict(
        bg=PALETTE['page'], bd=0, highlightthickness=0,
        activebackground=PALETTE['surface'],
        font=('Segoe UI', 10), padx=10, pady=4,
    )

    countdown_label = tk.Label(
        toolbar_frame, text=initial_text, bg=PALETTE['page'], fg=PALETTE['secondary'],
        font=('Consolas', 11), padx=10, pady=4
    )
    countdown_label.pack(side=tk.LEFT)

    more_button = tk.Button(
        toolbar_frame, text="Node", command=show_more_screen,
        fg=PALETTE['accent'], activeforeground=PALETTE['accent'],
        **button_style
    )
    more_button.pack(side=tk.LEFT)

    mining_button = tk.Button(
        toolbar_frame, text="Mining", command=toggle_chart_mode,
        fg=PALETTE['accent'], activeforeground=PALETTE['accent'],
        **button_style
    )
    mining_button.pack(side=tk.LEFT)

    options_button = tk.Button(
        toolbar_frame, text="Options", command=show_settings_window,
        fg=PALETTE['accent'], activeforeground=PALETTE['accent'],
        **button_style
    )
    options_button.pack(side=tk.LEFT)

    exit_button = tk.Button(
        toolbar_frame, text="Exit", command=proper_exit,
        fg=PALETTE['secondary'], activeforeground=PALETTE['critical'],
        **button_style
    )
    exit_button.pack(side=tk.LEFT)

    chart_frame = ttk.Frame(root)
    chart_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    style = ttk.Style()
    style.theme_use('clam')

    if IS_PI:
        screen_width = root.winfo_screenwidth() / root.winfo_screenheight() * 10
        screen_height = 4.0  # Fixed height ratio
        fig = plt.Figure(figsize=(screen_width, screen_height))
    else:
        fig = plt.Figure(figsize=(10, 4))
    canvas = FigureCanvasTkAgg(fig, master=chart_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    toolbar_frame.lift()
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
        
        # Load from cache instead of forcing update
        if chart_mode == "mining":
            update_mining_dashboard_from_cache()
        else:
            update_price_chart_from_cache()
        update_blockchain_info(force_update=True)

        # Ensure UI elements are visible
        toolbar_frame.lift()

        current_screen = "main"
        return
    
    # Switch to more screen
    current_screen = "more"
    canvas.get_tk_widget().pack_forget()  # Hide main chart
    
    # Create more chart directly in chart_frame, matching the main chart's aspect ratio
    if IS_PI:
        screen_width = root.winfo_screenwidth() / root.winfo_screenheight() * 10
        screen_height = 4.0
        more_fig = plt.Figure(figsize=(screen_width, screen_height))
    else:
        more_fig = plt.Figure(figsize=(10, 4))
    more_ax = more_fig.add_subplot(111)
    more_fig.patch.set_facecolor(PALETTE['page'])
    more_ax.set_facecolor(PALETTE['surface'])
    
    more_canvas = FigureCanvasTkAgg(more_fig, master=chart_frame)
    more_canvas.draw()
    more_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    update_more_metrics()

def toggle_chart_mode():
    """Switch the main screen's chart between the price chart and the mining
    dashboard. Only meaningful while the main screen is showing — if the Node
    screen is up, this just flips which chart comes back when it's closed."""
    global chart_mode, mining_button

    chart_mode = "mining" if chart_mode == "price" else "price"
    mining_button.config(text="Price" if chart_mode == "mining" else "Mining")

    if current_screen != "main":
        return  # Node screen is showing; the new mode takes effect when it closes.

    if chart_mode == "mining":
        update_mining_dashboard()
    else:
        update_price_chart_from_cache()

def restart_chart_alternation():
    """(Re)start the auto-alternation timer per the current
    chart_alternating/chart_alternating_interval settings. Cancels any
    existing timer first, so it's safe to call whenever either setting
    changes, or once at startup to pick up what was loaded from config."""
    global chart_alternation_timer_id

    if chart_alternation_timer_id is not None:
        try:
            root.after_cancel(chart_alternation_timer_id)
        except Exception:
            pass
        chart_alternation_timer_id = None

    if chart_alternating == "on" and root is not None and app_running:
        chart_alternation_timer_id = root.after(
            chart_alternating_interval_seconds * 1000, alternate_chart
        )

def alternate_chart():
    """Timer callback for chart_alternating: flip the main screen's chart
    (price <-> mining) and reschedule itself. Reuses toggle_chart_mode so
    the manual "Mining"/"Price" toolbar button stays in sync with whichever
    chart is showing."""
    global chart_alternation_timer_id
    if app_running and chart_alternating == "on":
        toggle_chart_mode()
        chart_alternation_timer_id = root.after(
            chart_alternating_interval_seconds * 1000, alternate_chart
        )
    else:
        chart_alternation_timer_id = None

def close_settings_window():
    """Tear down the Display Settings pop-up if it's open."""
    global settings_window
    if settings_window is not None:
        try:
            settings_window.destroy()
        except tk.TclError:
            pass
        settings_window = None

def style_option_button(button, selected):
    """Paint a settings option button as either the active choice (filled with
    the accent color) or an inactive one."""
    if selected:
        button.config(
            bg=PALETTE['accent'], fg=PALETTE['primary'],
            activebackground=PALETTE['accent'], activeforeground=PALETTE['primary'],
        )
    else:
        button.config(
            bg=PALETTE['page'], fg=PALETTE['secondary'],
            activebackground=PALETTE['baseline'], activeforeground=PALETTE['primary'],
        )

def choose_setting(key, value, group):
    """Apply the tapped option and move the highlight onto it. `group` is the
    {option: button} mapping for that one setting's row."""
    apply_setting_change(key, value)
    for option, button in group.items():
        style_option_button(button, option == value)

def show_settings_window():
    """Open the Display Settings pop-up (viewing mode, color scheme, chart type,
    color scheme interval) over whichever screen is showing. Changes apply
    immediately and persist to config.json. Clicking Options again closes it."""
    if settings_window is not None:
        # Already open — the Options button toggles it shut.
        close_settings_window()
        return
    build_settings_window(SETTINGS_SCALE)

def build_settings_window(scale, refit=True):
    """Build the pop-up at the given size scale. If the result overspills the
    screen — the Pi's panel is only 800x480, and font metrics differ per
    platform — it's rebuilt once at whatever scale actually fits, rather than
    leaving the Close button off the bottom edge."""
    global settings_window

    s = scale
    heading_font = ('Segoe UI', max(int(round(11 * s)), 8), 'bold')
    body_font = ('Segoe UI', max(int(round(10 * s)), 8))
    pad = max(int(round(4 * s)), 2)

    settings_window = tk.Toplevel(root)
    settings_window.title("Display Settings")
    settings_window.configure(bg=PALETTE['surface'])
    settings_window.transient(root)
    settings_window.protocol("WM_DELETE_WINDOW", close_settings_window)

    if IS_PI:
        # The main window is borderless fullscreen with no cursor, so the
        # pop-up matches: no title bar to close it with, Close button only.
        settings_window.overrideredirect(True)
        settings_window.config(cursor="none")
        container = tk.Frame(
            settings_window, bg=PALETTE['surface'],
            highlightbackground=PALETTE['baseline'], highlightthickness=max(int(s), 1)
        )
    else:
        settings_window.resizable(False, False)
        container = tk.Frame(settings_window, bg=PALETTE['surface'])
    container.pack(fill=tk.BOTH, expand=True)

    heading = tk.Label(
        container, text="DISPLAY SETTINGS", bg=PALETTE['surface'], fg=PALETTE['primary'],
        font=heading_font, anchor='w'
    )
    heading.grid(row=0, column=0, columnspan=2, sticky='w', padx=int(14 * s), pady=(int(12 * s), int(8 * s)))

    keys = ('viewing_mode', 'color_scheme', 'chart_type', 'color_scheme_interval')
    for i, key in enumerate(keys, start=1):
        label = tk.Label(
            container, text=SETTINGS_LABELS[key], bg=PALETTE['surface'], fg=PALETTE['secondary'],
            font=body_font, anchor='w'
        )
        label.grid(row=i, column=0, sticky='w', padx=(int(14 * s), int(6 * s)), pady=int(4 * s))

        # Every option is its own button rather than a dropdown. A ttk combobox
        # popdown decides what you chose from the list's curselection, which only
        # follows <Motion> as a mouse pointer travels over the rows — a
        # touchscreen tap arrives with no such motion, so the list would close
        # having "re-selected" the value that was already current. Buttons take a
        # single tap wherever it lands, and show the whole choice set at once.
        options_row = tk.Frame(container, bg=PALETTE['surface'])
        options_row.grid(row=i, column=1, sticky='w', padx=(0, int(14 * s)), pady=int(4 * s))

        group = {}
        for option in SETTINGS_OPTIONS[key]:
            button = tk.Button(
                options_row, text=option, font=body_font,
                bd=0, highlightthickness=0, padx=pad * 2, pady=pad,
            )
            button.pack(side=tk.LEFT, padx=(0, int(3 * s)))
            button.config(command=lambda k=key, v=option, g=group: choose_setting(k, v, g))
            group[option] = button

        for option, button in group.items():
            style_option_button(button, option == globals()[key])

    # "Chart" row: an Alternating on/off toggle plus, right next to it, how
    # often it flips — one row rather than two, since the interval is only
    # meaningful in the context of the toggle beside it.
    chart_row = len(keys) + 1
    chart_label = tk.Label(
        container, text=SETTINGS_LABELS['chart_alternating'], bg=PALETTE['surface'], fg=PALETTE['secondary'],
        font=body_font, anchor='w'
    )
    chart_label.grid(row=chart_row, column=0, sticky='w', padx=(int(14 * s), int(6 * s)), pady=int(4 * s))

    chart_options_row = tk.Frame(container, bg=PALETTE['surface'])
    chart_options_row.grid(row=chart_row, column=1, sticky='w', padx=(0, int(14 * s)), pady=int(4 * s))

    def sub_label(parent, text):
        lbl = tk.Label(parent, text=text, bg=PALETTE['surface'], fg=PALETTE['muted'], font=body_font)
        lbl.pack(side=tk.LEFT, padx=(0, int(6 * s)))
        return lbl

    sub_label(chart_options_row, "Alternating")
    alternating_group = {}
    for option in SETTINGS_OPTIONS['chart_alternating']:
        button = tk.Button(
            chart_options_row, text=option, font=body_font,
            bd=0, highlightthickness=0, padx=pad * 2, pady=pad,
        )
        button.pack(side=tk.LEFT, padx=(0, int(3 * s)))
        button.config(command=lambda v=option, g=alternating_group: choose_setting('chart_alternating', v, g))
        alternating_group[option] = button
    for option, button in alternating_group.items():
        style_option_button(button, option == chart_alternating)

    sub_label(chart_options_row, "Every")
    interval_group = {}
    for option in SETTINGS_OPTIONS['chart_alternating_interval']:
        button = tk.Button(
            chart_options_row, text=option, font=body_font,
            bd=0, highlightthickness=0, padx=pad * 2, pady=pad,
        )
        button.pack(side=tk.LEFT, padx=(0, int(3 * s)))
        button.config(command=lambda v=option, g=interval_group: choose_setting('chart_alternating_interval', v, g))
        interval_group[option] = button
    for option, button in interval_group.items():
        style_option_button(button, option == chart_alternating_interval)

    close_button = tk.Button(
        container, text="Close", command=close_settings_window,
        bg=PALETTE['surface'], fg=PALETTE['secondary'], bd=0, highlightthickness=0,
        activebackground=PALETTE['page'], activeforeground=PALETTE['primary'],
        font=body_font, padx=int(10 * s), pady=int(4 * s),
    )
    close_button.grid(row=chart_row + 1, column=0, columnspan=2, sticky='e',
                      padx=int(14 * s), pady=(int(10 * s), int(12 * s)))

    settings_window.bind('<Escape>', lambda event: close_settings_window())

    settings_window.update_idletasks()
    win_w = settings_window.winfo_width()
    win_h = settings_window.winfo_height()
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()

    if refit and (win_w > screen_w or win_h > screen_h):
        # Too big for this display — measure what we overshot by and rebuild
        # once at a scale that fits, leaving a small margin.
        fit = min(screen_w * 0.96 / win_w, screen_h * 0.96 / win_h)
        close_settings_window()
        build_settings_window(max(scale * fit, 1.0), refit=False)
        return

    # Center over the main window rather than letting the WM place it,
    # which on the Pi's borderless fullscreen would land it at 0,0. Clamped to
    # the screen so a wide row of options can't push the Close button off the
    # edge of a small panel.
    x = root.winfo_rootx() + (root.winfo_width() - win_w) // 2
    y = root.winfo_rooty() + (root.winfo_height() - win_h) // 2
    x = min(max(x, 0), max(root.winfo_screenwidth() - win_w, 0))
    y = min(max(y, 0), max(root.winfo_screenheight() - win_h, 0))
    settings_window.geometry(f"+{x}+{y}")
    settings_window.lift()

def update_more_metrics():
    global more_fig, more_ax, more_canvas
    if current_screen != "more" or more_ax is None:
        return

    more_ax.clear()
    more_ax.set_facecolor(PALETTE['surface'])
    more_fig.patch.set_facecolor(PALETTE['page'])
    more_ax.axis('off')

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
    
    chain_name = blockchain_info.get('chain', 'unknown') if blockchain_info else 'unknown'
    difficulty = blockchain_info.get('difficulty', 0) if blockchain_info else 0
    difficulty_text = format_difficulty(difficulty)
    total_connections = network_info.get('connections', 0) if network_info else 0
    latest_block = blockchain_info.get('blocks', 0) if blockchain_info else 0
    fee_rates_usd = [0, 0, 0]
    if fees:
        fee_rates_usd = [fee * 0.00000001 * current_price for fee in fees]
    usd_value = address_balance * current_price

    def label(text):
        return TextArea(text, textprops=dict(color=PALETTE['secondary'], fontsize=13))

    def value(text, color=None):
        return TextArea(text, textprops=dict(color=color or PALETTE['primary'], fontsize=13, fontweight='bold'))

    rows = [
        HPacker(children=[label("Last Update:"), value(last_update)], align="left", pad=0, sep=6),
        HPacker(children=[label("Network:"), value(f"{chain_name}net")], align="left", pad=0, sep=6),
        HPacker(children=[label("Peers:"), value(str(total_connections))], align="left", pad=0, sep=6),
        HPacker(children=[label("Latest Block:"), value(f"{latest_block:,}")], align="left", pad=0, sep=6),
        HPacker(children=[label("Difficulty:"), value(difficulty_text)], align="left", pad=0, sep=6),
        HPacker(children=[label("Fees (sat/vB):"),
                           value(f"L:{fees[0]} M:{fees[1]} H:{fees[2]}" if fees else "N/A")], align="left", pad=0, sep=6),
        HPacker(children=[label("Fees (USD):"),
                           value(f"L:${fee_rates_usd[0]:,.2f} M:${fee_rates_usd[1]:,.2f} H:${fee_rates_usd[2]:,.2f}" if fees else "N/A")], align="left", pad=0, sep=6),
        HPacker(children=[label("24h High:"), value(f"${high_24h:,.0f}", PALETTE['good'])], align="left", pad=0, sep=6),
        HPacker(children=[label("24h Low:"), value(f"${low_24h:,.0f}", PALETTE['critical'])], align="left", pad=0, sep=6),
        HPacker(children=[label("Address Balance:"), value(f"{address_balance:.3f} BTC (${usd_value:,.0f})", PALETTE['accent'])], align="left", pad=0, sep=6),
    ]
    box = VPacker(children=rows, align="left", pad=0, sep=8)
    heading = TextArea("NODE METRICS", textprops=dict(color=PALETTE['primary'], fontsize=18, fontweight='bold'))

    for child in more_ax.get_children():
        if isinstance(child, AnchoredOffsetbox):
            child.remove()

    anchored_heading = AnchoredOffsetbox(loc='upper left', child=heading, pad=0.6, frameon=False,
                                          bbox_to_anchor=(0.02, 0.98), bbox_transform=more_ax.transAxes, borderpad=0)
    anchored_box = AnchoredOffsetbox(loc='upper left', child=box, pad=0.8, frameon=True,
                                      bbox_to_anchor=(0.02, 0.86), bbox_transform=more_ax.transAxes, borderpad=0)
    anchored_box.patch.set_boxstyle("round,pad=0.6")
    anchored_box.patch.set_facecolor(PALETTE['page'])
    anchored_box.patch.set_edgecolor(PALETTE['baseline'])
    anchored_box.patch.set_alpha(0.9)

    more_ax.add_artist(anchored_heading)
    more_ax.add_artist(anchored_box)

    more_fig.tight_layout()
    more_canvas.draw()

def proper_exit():
    global app_running, root, price_timer_id, blockchain_timer_id, display_timer_id, chart_alternation_timer_id
    app_running = False

    # Cancel known timer IDs safely
    for timer_id in [price_timer_id, blockchain_timer_id, display_timer_id, chart_alternation_timer_id]:
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
            if chart_mode == "mining":
                update_mining_dashboard(force_update=True)
            else:
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
def time_until_next_aligned_update(interval_seconds):
    """Seconds remaining until the next wall-clock boundary that's a multiple
    of interval_seconds since the top of the hour (e.g. a 5-minute interval
    lands on :00, :05, :10, ...). The grid resets at the top of every hour,
    so the first wait after startup may be shorter than a full interval."""
    now = datetime.now()
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    elapsed = (now - hour_start).total_seconds()
    intervals_passed = int(elapsed // interval_seconds)
    next_boundary = hour_start + timedelta(seconds=(intervals_passed + 1) * interval_seconds)
    if next_boundary > hour_start + timedelta(hours=1):
        next_boundary = hour_start + timedelta(hours=1)
    return (next_boundary - now).total_seconds()
def update_countdown():
    """Update the countdown label with time until next price update (updates 10x per second for smooth animation)

    When the countdown reaches the aligned update boundary, force a price update
    once to ensure the chart is redrawn immediately instead of relying solely on
    the scheduled timer. Uses last_countdown_trigger_time to avoid repeated
    triggers while the countdown shows 00:00 across multiple 100ms ticks."""
    global countdown_label, app_running, root, last_countdown_trigger_time
    
    if countdown_label is None or root is None:
        return
    
    try:
        # Calculate time until the next price update, per config['update_intervals']['price']
        seconds_remaining = time_until_next_aligned_update(config['update_intervals']['price'])

        # Format as MM:SS
        minutes = int(seconds_remaining // 60)
        secs = int(seconds_remaining % 60)
        
        countdown_text = f"{minutes:02d}:{secs:02d}"
        countdown_label.config(text=countdown_text)

        # If we're very close to the boundary, trigger an immediate update once.
        # This guarantees the display is refreshed right when the countdown hits 00:00.
        if seconds_remaining <= 0.5:
            now = time.time()
            if now - last_countdown_trigger_time > 1.0:
                last_countdown_trigger_time = now
                try:
                    update_price_chart(force_update=True)
                except Exception as e:
                    logging.error(f"Error forcing price update from countdown: {e}")

        # Update 10 times per second for smooth real-time countdown (every 100ms)
        if app_running:
            root.after(100, update_countdown)
    except Exception as e:
        logging.error(f"Error updating countdown: {e}")
        try:
            countdown_label.config(text="--:--")
        except:   
            pass

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
        return None

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

def load_price_from_cache():
    """Load price data from cache without fetching new data"""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as cache_file:
                cached_data = json.load(cache_file)
                current_price = cached_data.get("current_price")
                daily_change = cached_data.get("daily_change")
                prices = cached_data.get("prices")
                print("Loaded price data from cache.")
                return current_price, daily_change, prices
        else:
            print("Cache file does not exist.")
            return None, None, None
    except Exception as e:
        logging.error(f"Error loading price from cache: {e}")
        return None, None, None
def get_bitcoin_price():
    """Fetch current Bitcoin price and historical data"""
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

        # Previous 24h of price history. Using days=1 on the plain market_chart
        # endpoint (rather than market_chart/range) gets 5-minute granularity
        # for free — /range is capped at hourly on CoinGecko's free tier.
        historical_url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=1"
        historical_response = requests.get(historical_url)
        historical_response.raise_for_status()
        historical_data = historical_response.json()
        prices = historical_data['prices']
        
        if prices:
            previous_close_price = prices[0][1]
            daily_change = (current_price - previous_close_price) / previous_close_price * 100
            daily_change = round(daily_change, 2)
            return current_price, daily_change, prices
        else:
            return current_price, None, None
    except requests.RequestException as e:
        logging.error(f"Error fetching price data: {e}")
        return None, None, None

def get_bitcoin_ohlc():
    """Fetch real 30-minute OHLC candles from CoinGecko (actual exchange-derived
    open/high/low/close, not approximated from the plain price series)."""
    try:
        url = "https://api.coingecko.com/api/v3/coins/bitcoin/ohlc?vs_currency=usd&days=1"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()  # [[timestamp_ms, open, high, low, close], ...]
    except requests.RequestException as e:
        logging.error(f"Error fetching OHLC data: {e}")
        return None

def get_difficulty_adjustment():
    """Fetch current difficulty-epoch progress from mempool.space: blocks and
    time remaining until the next retarget, and the estimated % change."""
    try:
        url = "https://mempool.space/api/v1/difficulty-adjustment"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error fetching difficulty adjustment: {e}")
        return None

def get_mining_hashrate_history(period=MINING_CHART_PERIOD):
    """Fetch network hashrate/difficulty history from mempool.space over the
    given period (one of mempool's fixed windows: 3d, 1w, 1m, 3m, 6m, 1y, 2y,
    3y, all). Returns daily hashrate samples plus one difficulty sample per
    retarget, along with the latest 1-week-average hashrate and difficulty."""
    try:
        url = f"https://mempool.space/api/v1/mining/hashrate/{period}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error fetching mining hashrate history: {e}")
        return None

def fetch_and_cache_mining_data():
    """Fetch fresh difficulty-adjustment and hashrate/difficulty history, and
    cache both together so the mining dashboard has something to show
    instantly (via load_mining_from_cache) next launch or when data's not due
    for a refresh yet."""
    difficulty_adj = get_difficulty_adjustment()
    hashrate_data = get_mining_hashrate_history()
    if difficulty_adj is not None and hashrate_data is not None:
        try:
            with open(MINING_CACHE_FILE, 'w') as cache_file:
                json.dump({
                    "difficulty_adjustment": difficulty_adj,
                    "hashrate_data": hashrate_data,
                    "timestamp": time.time()
                }, cache_file)
        except Exception as e:
            logging.error(f"Error caching mining data: {e}")
    return difficulty_adj, hashrate_data

def load_mining_from_cache():
    """Load mining data from cache without fetching new data."""
    try:
        if os.path.exists(MINING_CACHE_FILE):
            with open(MINING_CACHE_FILE, 'r') as cache_file:
                cached_data = json.load(cache_file)
                return cached_data.get("difficulty_adjustment"), cached_data.get("hashrate_data")
        return None, None
    except Exception as e:
        logging.error(f"Error loading mining data from cache: {e}")
        return None, None

def show_chart_message(text):
    """Clear the main chart and show a centered status message."""
    global fig, canvas, ax
    if ax is None:
        fig.clear()
        ax = fig.add_subplot(111)
    else:
        ax.clear()
    ax.set_facecolor(PALETTE['surface'])
    ax.axis('off')
    ax.text(
        0.5, 0.5, text,
        ha='center', va='center', color=PALETTE['primary'], fontsize=14,
        transform=ax.transAxes
    )
    fig.patch.set_facecolor(PALETTE['page'])
    canvas.draw()

def _floor_to_interval(dt, interval_minutes):
    """Floor a datetime to the start of its color_scheme_interval bucket, keeping its date."""
    total_minutes = dt.hour * 60 + dt.minute
    floored_minutes = (total_minutes // interval_minutes) * interval_minutes
    return dt.replace(hour=floored_minutes // 60, minute=floored_minutes % 60, second=0, microsecond=0)

def _plot_dynamic_price_line(ax, plot_dates, plot_values):
    """Draw the price line/fill as a series of segments (sized per
    color_scheme_interval), each colored green or red depending on whether
    price rose or fell during that segment."""
    buckets = []  # [(bucket_key, [(date, value), ...]), ...]
    for d, v in zip(plot_dates, plot_values):
        bucket_key = _floor_to_interval(d, color_scheme_interval_minutes)
        if buckets and buckets[-1][0] == bucket_key:
            buckets[-1][1].append((d, v))
        else:
            buckets.append((bucket_key, [(d, v)]))

    baseline = min(plot_values)
    prev_point = None
    for _, points in buckets:
        bucket_dates = [p[0] for p in points]
        bucket_values = [p[1] for p in points]
        if len(points) > 1:
            seg_color = PALETTE['good'] if bucket_values[-1] >= bucket_values[0] else PALETTE['critical']
        elif prev_point is not None:
            seg_color = PALETTE['good'] if bucket_values[0] >= prev_point[1] else PALETTE['critical']
        else:
            seg_color = PALETTE['good']

        # Prepend the previous bucket's last point so segments connect with no visual gap.
        if prev_point is not None:
            bucket_dates = [prev_point[0]] + bucket_dates
            bucket_values = [prev_point[1]] + bucket_values

        ax.plot(bucket_dates, bucket_values, color=seg_color, linewidth=2, zorder=3, solid_capstyle='round')
        ax.fill_between(bucket_dates, bucket_values, baseline, color=seg_color, alpha=0.15, zorder=2, linewidth=0)
        prev_point = points[-1]

def _real_ohlc_candles():
    """Fetch CoinGecko's real 30-min candles and aggregate them up to
    color_scheme_interval. Returns a list of (bucket_key, open, high, low, close)
    or None if unavailable (network error, or interval too fine to benefit)."""
    if testing or color_scheme_interval_minutes <= 30:
        return None
    raw = get_bitcoin_ohlc()
    if not raw:
        return None

    candles = [(datetime.fromtimestamp(c[0] / 1000), c[1], c[2], c[3], c[4]) for c in raw]
    if viewing_mode == "static":
        est = pytz.timezone('US/Eastern')
        now_est = datetime.now(est)
        today_midnight = now_est.replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)
        today_end = now_est.replace(hour=23, minute=59, second=59, microsecond=999999).replace(tzinfo=None)
        candles = [c for c in candles if today_midnight <= c[0] <= today_end]

    buckets = []  # [(bucket_key, [(open, high, low, close), ...]), ...]
    for d, o, h, l, c in candles:
        bucket_key = _floor_to_interval(d, color_scheme_interval_minutes)
        if buckets and buckets[-1][0] == bucket_key:
            buckets[-1][1].append((o, h, l, c))
        else:
            buckets.append((bucket_key, [(o, h, l, c)]))

    return [
        (bucket_key, ohlc[0][0], max(o[1] for o in ohlc), min(o[2] for o in ohlc), ohlc[-1][3])
        for bucket_key, ohlc in buckets
    ]

def _approximate_candles_from_prices(plot_dates, plot_values):
    """Approximate candles by bucketing the plain price series (open/close =
    first/last price in the bucket, high/low = its min/max). Used when the
    interval is too fine for CoinGecko's real 30-min OHLC to help (15min, 5min)."""
    if len(plot_values) < 2:
        return []
    buckets = []  # [(bucket_key, [value, ...]), ...]
    for d, v in zip(plot_dates, plot_values):
        bucket_key = _floor_to_interval(d, color_scheme_interval_minutes)
        if buckets and buckets[-1][0] == bucket_key:
            buckets[-1][1].append(v)
        else:
            buckets.append((bucket_key, [v]))
    return [(k, vs[0], max(vs), min(vs), vs[-1]) for k, vs in buckets]

def _plot_candlestick_price(ax, plot_dates, plot_values):
    """Draw the price series as OHLC candlesticks. Intervals coarser than
    CoinGecko's native 30-minute OHLC granularity (hourly, daily) use real
    exchange-derived candles; finer intervals (15min, 5min) approximate
    candles from the plain price series, which is all that's available at
    that resolution."""
    candles = _real_ohlc_candles() or _approximate_candles_from_prices(plot_dates, plot_values)
    if not candles:
        return

    interval_days = color_scheme_interval_minutes / (24 * 60)
    body_width = interval_days * 0.7
    price_range = max(c[2] for c in candles) - min(c[3] for c in candles)
    min_body_height = price_range * 0.002 if price_range else 0.01

    for bucket_key, open_, high, low, close in candles:
        x = mdates.date2num(bucket_key) + interval_days / 2

        if color_scheme == "dynamic":
            candle_color = PALETTE['good'] if close >= open_ else PALETTE['critical']
        else:
            candle_color = PALETTE['accent']

        ax.vlines(x, low, high, color=candle_color, linewidth=1, zorder=2)
        body_bottom = min(open_, close)
        body_height = max(abs(close - open_), min_body_height)
        ax.bar(x, body_height, bottom=body_bottom, width=body_width,
               color=candle_color, edgecolor=candle_color, zorder=3)

def _plot_baseline_price(ax, plot_dates, plot_values):
    """Draw the price line/fill relative to a baseline (the first visible
    price point). In dynamic color_scheme, price above the baseline is green
    and below is red, with segments split exactly at each crossing so the
    color change lands on the baseline line; in static, one fixed accent
    color is used throughout."""
    if not plot_values:
        return
    baseline = plot_values[0]
    ax.axhline(baseline, color=PALETTE['baseline'], linewidth=1, linestyle='--', zorder=1)

    if color_scheme != "dynamic" or len(plot_values) < 2:
        ax.plot(plot_dates, plot_values, color=PALETTE['accent'], linewidth=2, zorder=3)
        ax.fill_between(plot_dates, plot_values, baseline, color=PALETTE['accent'], alpha=0.15, zorder=2)
        return

    for i in range(len(plot_values) - 1):
        x0, x1 = plot_dates[i], plot_dates[i + 1]
        y0, y1 = plot_values[i], plot_values[i + 1]
        above0, above1 = y0 >= baseline, y1 >= baseline

        if above0 == above1:
            color = PALETTE['good'] if above0 else PALETTE['critical']
            ax.plot([x0, x1], [y0, y1], color=color, linewidth=2, zorder=3, solid_capstyle='round')
            ax.fill_between([x0, x1], [y0, y1], baseline, color=color, alpha=0.15, zorder=2, linewidth=0)
        else:
            # Crosses the baseline — split at the interpolated crossing point
            # so each half is colored for the side it's actually on.
            t = (baseline - y0) / (y1 - y0)
            x_cross = x0 + (x1 - x0) * t
            color0 = PALETTE['good'] if above0 else PALETTE['critical']
            color1 = PALETTE['good'] if above1 else PALETTE['critical']
            ax.plot([x0, x_cross], [y0, baseline], color=color0, linewidth=2, zorder=3, solid_capstyle='round')
            ax.plot([x_cross, x1], [baseline, y1], color=color1, linewidth=2, zorder=3, solid_capstyle='round')
            ax.fill_between([x0, x_cross], [y0, baseline], baseline, color=color0, alpha=0.15, zorder=2, linewidth=0)
            ax.fill_between([x_cross, x1], [baseline, y1], baseline, color=color1, alpha=0.15, zorder=2, linewidth=0)

def render_price_chart(current_price, daily_change, prices):
    """Render the bitcoin price chart onto the shared fig/ax/canvas."""
    global fig, canvas, ax
    fig.clear()
    ax = fig.add_subplot(111)
    ax.set_facecolor(PALETTE['surface'])
    fig.patch.set_facecolor(PALETTE['page'])
    fig.subplots_adjust(left=0.08, right=0.99, top=0.90, bottom=0.15)

    dates = [datetime.fromtimestamp(price[0] / 1000) for price in prices]
    values = [price[1] for price in prices]

    if viewing_mode == "static":
        est = pytz.timezone('US/Eastern')
        now_est = datetime.now(est)
        today_midnight = now_est.replace(hour=0, minute=0, second=0, microsecond=0)
        today_midnight_naive = today_midnight.replace(tzinfo=None)
        today_end_naive = today_midnight.replace(hour=23, minute=59, second=59, microsecond=999999).replace(tzinfo=None)
        plot_dates = [d for d in dates if today_midnight_naive <= d <= today_end_naive]
        plot_values = [v for d, v in zip(dates, values) if today_midnight_naive <= d <= today_end_naive]
    else:
        plot_dates, plot_values = dates, values

    if chart_type == "candlestick":
        _plot_candlestick_price(ax, plot_dates, plot_values)
    elif chart_type == "baseline":
        _plot_baseline_price(ax, plot_dates, plot_values)
    elif color_scheme == "dynamic" and len(plot_values) > 1:
        _plot_dynamic_price_line(ax, plot_dates, plot_values)
    else:
        ax.plot(plot_dates, plot_values, color=PALETTE['accent'], linewidth=2, zorder=3)
        if plot_values:
            ax.fill_between(plot_dates, plot_values, min(plot_values), color=PALETTE['accent'], alpha=0.15, zorder=2)

    ax.set_axisbelow(True)
    ax.grid(axis='y', color=PALETTE['grid'], linewidth=0.6, alpha=0.7, zorder=0)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    for side in ('bottom', 'left'):
        ax.spines[side].set_color(PALETTE['baseline'])
        ax.spines[side].set_linewidth(0.8)

    ax.tick_params(axis='x', colors=PALETTE['muted'])
    ax.tick_params(axis='y', colors=PALETTE['muted'])

    if time_series.lower() == "standard":
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%-I:%M %p'))
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'${x:,.0f}'))

    ax.set_title(f"฿itcoin  ${current_price:,.0f}", loc='left', fontsize=18,
                 fontweight='bold', color=PALETTE['primary'], pad=14)

    if daily_change is not None:
        if daily_change > 0:
            badge_text, badge_color = f"+{daily_change}%", PALETTE['accent']
        elif daily_change == 0:
            badge_text, badge_color = f"{daily_change}%", PALETTE['good']
        else:
            badge_text, badge_color = f"-{abs(daily_change)}%", PALETTE['critical']
        ax.text(
            0.98, 0.94, badge_text, transform=ax.transAxes,
            ha='right', va='top', fontsize=12, fontweight='bold', color=PALETTE['primary'],
            bbox=dict(boxstyle='round,pad=0.35', facecolor=badge_color, edgecolor='none'),
            zorder=4
        )

    if viewing_mode == "static":
        ax.set_xlim(today_midnight_naive, today_end_naive)
        ax.margins(x=0.01, y=0.05)  # Small x-padding to prevent clipping

    fig.tight_layout(pad=0.5, h_pad=0.8, w_pad=0.5)
    canvas.draw()

def _dashboard_scale(fig):
    """Font-scale factor for the mining dashboard, relative to this app's
    desktop baseline figure size (10x4 in). The figure is resized by Tk to
    match whatever window/screen it's actually drawn in, but matplotlib
    fontsizes are absolute points — without this, text sized for the
    desktop crowds or overflows the much smaller canvas a constrained Pi
    display renders into. Clamped so a tiny screen doesn't shrink text to
    unreadable, and a larger-than-baseline window doesn't balloon it."""
    base_w, base_h = 10.0, 4.0
    fig_w, fig_h = fig.get_size_inches()
    scale = min(fig_w / base_w, fig_h / base_h)
    return max(0.55, min(scale, 1.15))

def _draw_stat_tile(fig, grid_cell, label, big_text, unit_text, sub_text, value_color=None, scale=1.0):
    """Draw one stat card (label / big value [+ small unit] / subtext)
    into a gridspec cell. The unit is placed flush after the big value by
    measuring its actual rendered width — mixed font sizes on one baseline
    aren't something a single Text object can do, and a fixed character-width
    guess drifts across the different figure sizes this app runs at (Pi vs.
    desktop). sub_text may be a plain string (rendered in the muted color) or
    a list of (text, color) segments for mixed-color subtext, e.g. a colored
    +/-% figure inline with muted surrounding words. scale comes from
    _dashboard_scale() and keeps these fixed-point fontsizes proportionate
    to the actual rendered figure size."""
    tile_ax = fig.add_subplot(grid_cell)
    tile_ax.axis('off')
    tile_ax.set_xlim(0, 1)
    tile_ax.set_ylim(0, 1)

    tile_ax.text(0.5, 0.80, label, transform=tile_ax.transAxes,
                 ha='center', va='top', fontsize=13 * scale, fontweight='bold', color=PALETTE['accent'])

    big_color = value_color or PALETTE['primary']
    big = tile_ax.text(0.0, 0.38, big_text, transform=tile_ax.transAxes,
                        ha='left', va='center', fontsize=24 * scale, fontweight='bold', color=big_color)

    unit = None
    if unit_text:
        fig.canvas.draw()
        bbox = big.get_window_extent(renderer=fig.canvas.get_renderer())
        x_end = tile_ax.transAxes.inverted().transform((bbox.x1, 0))[0]
        unit = tile_ax.text(x_end + 0.03, 0.34, unit_text, transform=tile_ax.transAxes,
                     ha='left', va='center', fontsize=12 * scale, color=PALETTE['secondary'])

    # Re-center the value (+ unit, if present) as one group now that its
    # actual rendered width is known - the pair was built left-aligned at 0
    # above so the unit could be measured flush against the value.
    fig.canvas.draw()
    group_x1 = (unit or big).get_window_extent(renderer=fig.canvas.get_renderer()).x1
    group_width = tile_ax.transAxes.inverted().transform((group_x1, 0))[0]
    offset = 0.5 - group_width / 2
    big.set_x(offset)
    if unit is not None:
        unit.set_x(x_end + 0.03 + offset)

    if sub_text:
        parts = sub_text if isinstance(sub_text, list) else [(sub_text, PALETTE['muted'])]
        sub_texts = []
        x = 0.0
        for part_text, part_color in parts:
            t = tile_ax.text(x, 0.02, part_text, transform=tile_ax.transAxes,
                              ha='left', va='bottom', fontsize=10 * scale, color=part_color)
            fig.canvas.draw()
            bbox = t.get_window_extent(renderer=fig.canvas.get_renderer())
            x = tile_ax.transAxes.inverted().transform((bbox.x1, 0))[0]
            sub_texts.append(t)
        sub_offset = 0.5 - x / 2
        for t in sub_texts:
            t.set_x(t.get_position()[0] + sub_offset)

def render_mining_dashboard(blockchain_data, difficulty_adj, hashrate_data):
    """Render the mining-focused dashboard onto the shared fig/ax/canvas: a
    row of stat tiles (blocks remaining to retarget, the estimated difficulty
    change, and a next-halving countdown) above a dual-axis hashrate/
    difficulty history chart."""
    global fig, canvas, ax
    fig.clear()
    fig.patch.set_facecolor(PALETTE['page'])
    scale = _dashboard_scale(fig)

    gs = fig.add_gridspec(2, 3, height_ratios=[1.5, 3.2], hspace=0.7, wspace=0.3,
                           top=0.88, bottom=0.13, left=0.11, right=0.92)

    remaining_blocks = difficulty_adj.get('remainingBlocks', 0)
    remaining_days = difficulty_adj.get('remainingTime', 0) / 1000 / 86400
    difficulty_change = difficulty_adj.get('difficultyChange', 0)
    previous_retarget = difficulty_adj.get('previousRetarget')
    time_avg_ms = difficulty_adj.get('timeAvg') or 600000

    # Prefer the node's own view of chain height; fall back to deriving it
    # from mempool.space's next-retarget height so the dashboard still works
    # (e.g. RPC unreachable) using only the mining API.
    current_height = blockchain_data.get('blocks') if blockchain_data else None
    if current_height is None:
        next_retarget_height = difficulty_adj.get('nextRetargetHeight')
        if next_retarget_height is not None:
            current_height = next_retarget_height - remaining_blocks

    if current_height is not None:
        avg_block_time_s = time_avg_ms / 1000
        _, _, halving_date = get_next_halving_info(current_height, avg_block_time_s)
        halving_days_total = max((halving_date - datetime.now()).days, 0)
        halving_years, halving_days = divmod(halving_days_total, 365)
    else:
        halving_date = None
        halving_years = halving_days = 0

    _draw_stat_tile(
        fig, gs[0, 0], "Remaining", f"{remaining_blocks:,}", "blocks",
        f"In ~{remaining_days:.0f} days" if remaining_days >= 1 else "In <1 day",
        scale=scale
    )

    change_color = PALETTE['good'] if difficulty_change >= 0 else PALETTE['critical']
    arrow = "▲" if difficulty_change >= 0 else "▼"
    prev_text = ""
    if previous_retarget is not None:
        prev_color = PALETTE['good'] if previous_retarget >= 0 else PALETTE['critical']
        sign = "+" if previous_retarget >= 0 else "-"
        prev_text = [
            ("Previous: ", PALETTE['muted']),
            (f"{sign}{abs(previous_retarget):.2f}", prev_color),
            ("%", PALETTE['muted']),
        ]
    _draw_stat_tile(
        fig, gs[0, 1], "Estimate", f"{arrow} {abs(difficulty_change):.2f}%", None,
        prev_text, value_color=change_color, scale=scale
    )

    if halving_date is not None:
        halving_big = f"{halving_date.strftime('%b')} {halving_date.day}, {halving_date.year}"
        if halving_years > 0:
            year_word = "year" if halving_years == 1 else "years"
            halving_sub = f"In ~{halving_years} {year_word}, {halving_days} days"
        else:
            halving_sub = f"In ~{halving_days} days"
    else:
        halving_big, halving_sub = "N/A", ""
    _draw_stat_tile(fig, gs[0, 2], "Next Halving", halving_big, None, halving_sub, scale=scale)

    ax = fig.add_subplot(gs[1, :])
    ax.set_facecolor(PALETTE['surface'])

    current_hashrate = hashrate_data.get('currentHashrate', 0)
    current_difficulty = hashrate_data.get('currentDifficulty', 0)

    hr_entries = hashrate_data.get('hashrates', [])
    hr_dates = [datetime.fromtimestamp(e['timestamp']) for e in hr_entries]
    hr_values = [e['avgHashrate'] for e in hr_entries]

    # 1-week rolling mean of the daily samples, to overlay a smoothed trend
    # on top of the noisier daily-mean series.
    window = 7
    hr_1w = []
    for i in range(len(hr_values)):
        chunk = hr_values[max(0, i - window + 1):i + 1]
        hr_1w.append(sum(chunk) / len(chunk))

    if hr_dates:
        # Color both the noisy daily line and its smoothed trend by relative
        # position within their shared min/max (green at the low end shading
        # through yellow to red/pink at the high end), mirroring
        # mempool.space's mining chart instead of one flat color per line.
        hr_dates_num = mdates.date2num(hr_dates)
        hr_norm = Normalize(vmin=min(hr_values + hr_1w), vmax=max(hr_values + hr_1w))

        def _gradient_line(values, linewidth, alpha, zorder):
            # avgHashrate samples are huge Python ints (~1e20, past int64
            # range), so they must be cast to float explicitly — otherwise
            # np.array() silently produces dtype=object, which set_array()
            # then rejects.
            values = np.asarray(values, dtype=float)
            points = np.array([hr_dates_num, values]).T.reshape(-1, 1, 2)
            segments = np.concatenate([points[:-1], points[1:]], axis=1)
            lc = LineCollection(
                segments, cmap=HASHRATE_GRADIENT, norm=hr_norm,
                linewidth=linewidth, alpha=alpha, zorder=zorder
            )
            lc.set_array(values[:-1])
            ax.add_collection(lc)

        _gradient_line(hr_values, 0.8, 0.8, 2)
        _gradient_line(hr_1w, 3, 1.0, 4)
        ax.set_xlim(min(hr_dates_num), max(hr_dates_num))
        ax.set_ylim(min(hr_values) * 0.97, max(hr_values) * 1.03)

    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: format_hashrate(v)))
    ax.tick_params(axis='y', colors=PALETTE['muted'], labelsize=9 * scale)
    ax.tick_params(axis='x', colors=PALETTE['muted'], labelsize=9 * scale)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    ax.set_axisbelow(True)
    ax.grid(axis='y', color=PALETTE['grid'], linewidth=0.6, alpha=0.5, zorder=0)

    ax2 = ax.twinx()
    diff_entries = hashrate_data.get('difficulty', [])
    diff_dates = [datetime.fromtimestamp(e['time']) for e in diff_entries]
    diff_values = [e['difficulty'] for e in diff_entries]
    if diff_dates:
        # Extend the last known difficulty out to the most recent hashrate
        # date so the step line spans the full width of the chart instead of
        # stopping short at the last retarget.
        if hr_dates and diff_dates[-1] < hr_dates[-1]:
            diff_dates = diff_dates + [hr_dates[-1]]
            diff_values = diff_values + [diff_values[-1]]
        ax2.step(diff_dates, diff_values, where='post', color='#d6336c', linewidth=2, zorder=3)

    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v / 1e12:,.0f}T"))
    ax2.tick_params(axis='y', colors=PALETTE['muted'], labelsize=9 * scale)
    ax2.grid(False)

    ax.spines['top'].set_visible(False)
    ax2.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(PALETTE['baseline'])
    ax.spines['bottom'].set_color(PALETTE['baseline'])
    ax2.spines['right'].set_color(PALETTE['baseline'])

    hashrate_val = ax.text(0.0, 1.02, format_hashrate(current_hashrate), transform=ax.transAxes, ha='left', va='bottom',
            fontsize=16 * scale, fontweight='bold', color=PALETTE['primary'])
    difficulty_val = ax.text(1.0, 1.02, format_difficulty(current_difficulty), transform=ax.transAxes, ha='right', va='bottom',
            fontsize=16 * scale, fontweight='bold', color=PALETTE['primary'])

    # Center each header over its value's actual rendered width rather than
    # over the axes edge, since the values aren't fixed-width.
    fig.canvas.draw()
    disp_to_axes = ax.transAxes.inverted()
    hr_bbox = hashrate_val.get_window_extent(renderer=fig.canvas.get_renderer())
    diff_bbox = difficulty_val.get_window_extent(renderer=fig.canvas.get_renderer())
    hr_center = disp_to_axes.transform(((hr_bbox.x0 + hr_bbox.x1) / 2, 0))[0]
    diff_center = disp_to_axes.transform(((diff_bbox.x0 + diff_bbox.x1) / 2, 0))[0]

    ax.text(hr_center, 1.13, "Hashrate (1w)", transform=ax.transAxes, ha='center', va='bottom',
            fontsize=12 * scale, fontweight='bold', color=PALETTE['accent'])
    ax.text(diff_center, 1.13, "Difficulty", transform=ax.transAxes, ha='center', va='bottom',
            fontsize=12 * scale, fontweight='bold', color=PALETTE['accent'])

    canvas.draw()

def update_price_chart_from_cache():
    """Update the price chart using cached data without fetching new data"""
    global app_running
    if not app_running:
        return  # Don't do anything if the app is not running

    try:
        current_price, daily_change, prices = load_price_from_cache()
        if current_price is None or not prices:
            show_chart_message("No cached price data available.\nPlease wait for next update.")
            return

        render_price_chart(current_price, daily_change, prices)

        # Redraw node info if available
        if previous_chain is not None:
            update_node_table(previous_chain, previous_network, previous_fees)

    except Exception as e:
        logging.error(f"Error updating price chart from cache: {e}")
        show_chart_message("Error loading cached price data.")

def update_price_chart(force_update=False):
    global last_price_update, app_running, root, price_timer_id
    if not app_running:
        return  # Don't do anything if the app is not running

    current_time = time.time()
    next_delay_ms = 300000  # Default retry delay (5 min) if we don't get usable data

    try:
        did_fetch = force_update or last_price_update == 0 or (current_time - last_price_update >= config['update_intervals']['price']) # If it's a force update, hasn't been updated, or the interval time has been met.
        if did_fetch:
            current_price, daily_change, prices = get_bitcoin_price()
            # Cache the data after fetching
            if current_price is not None:
                with open(CACHE_FILE, 'w') as cache_file:
                    json.dump({
                        "current_price": current_price,
                        "daily_change": daily_change,
                        "prices": prices,
                        "timestamp": time.time()
                    }, cache_file)
        else:
            # Load from cache when not updating
            current_price, daily_change, prices = load_price_from_cache()

        if prices and len(prices) > 0: # If we have price data and it's not empty
            render_price_chart(current_price, daily_change, prices)
            # Only stamp last_price_update when we actually fetched fresh data.
            # Re-stamping on a cache-only render (not due yet) would perpetually
            # skew this timestamp forward by whatever latency the previous fetch
            # took, so current_time - last_price_update would never clear the
            # interval again and the price would silently stop refreshing.
            if did_fetch:
                last_price_update = current_time
            next_delay_ms = time_until_next_aligned_update(config['update_intervals']['price']) * 1000

            # Redraw node info if available
            if previous_chain is not None:
                update_node_table(previous_chain, previous_network, previous_fees)
        else:
            logging.error("No price data available when updating price chart; will retry shortly.")
            show_chart_message("No price data available.\nRetrying shortly.")

    except Exception as e:
        logging.error(f"Error updating price chart: {e}")
        show_chart_message("Error loading price data.")
    finally:
        # Always reschedule, whether this run succeeded, found no data, or errored,
        # so the chart never gets permanently stuck.
        if app_running:
            if price_timer_id is not None:
                root.after_cancel(price_timer_id)
            price_timer_id = root.after(int(next_delay_ms), update_price_chart)

def update_mining_dashboard_from_cache():
    """Update the mining dashboard using cached data without fetching new
    data (mirrors update_price_chart_from_cache, used when returning to the
    main screen from the Node screen)."""
    try:
        difficulty_adj, hashrate_data = load_mining_from_cache()
        if difficulty_adj is None or hashrate_data is None:
            show_chart_message("No cached mining data available.\nPlease wait for next update.")
            return
        render_mining_dashboard(previous_chain, difficulty_adj, hashrate_data)
    except Exception as e:
        logging.error(f"Error updating mining dashboard from cache: {e}")
        show_chart_message("Error loading cached mining data.")

def update_mining_dashboard(force_update=False):
    """Fetch (or reuse cached) mining data and render the mining dashboard.
    Mirrors update_price_chart's fetch-on-schedule/fallback-to-cache shape,
    using its own interval (config['update_intervals']['mining'], default 15
    minutes — difficulty/hashrate move far slower than price)."""
    global last_mining_update, app_running
    if not app_running:
        return

    current_time = time.time()
    mining_interval = config.get('update_intervals', {}).get('mining', 900)

    try:
        did_fetch = force_update or last_mining_update == 0 or (current_time - last_mining_update >= mining_interval)
        if did_fetch:
            difficulty_adj, hashrate_data = fetch_and_cache_mining_data()
        else:
            difficulty_adj, hashrate_data = load_mining_from_cache()

        if difficulty_adj is None or hashrate_data is None:
            # Fetch failed (or wasn't due) and there's nothing usable yet — try the cache once more.
            difficulty_adj, hashrate_data = load_mining_from_cache()

        if difficulty_adj is not None and hashrate_data is not None:
            render_mining_dashboard(previous_chain, difficulty_adj, hashrate_data)
            if did_fetch:
                last_mining_update = current_time
        else:
            logging.error("No mining data available when updating mining dashboard; will retry shortly.")
            show_chart_message("No mining data available.\nRetrying shortly.")
    except Exception as e:
        logging.error(f"Error updating mining dashboard: {e}")
        show_chart_message("Error loading mining data.")

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
    # Format blocks and headers with thousands separators (e.g. 960,015)
    blockchain_blocks = f"{blockchain_data['blocks']:,}/{blockchain_data['headers']:,}"
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
        low_fee, medium_fee, high_fee = fees if fees else (None, None, None)
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
    global app_running, root, last_blockchain_update, blockchain_chain, blockchain_blocks, blockchain_verification_progress, node_connections, cpu_temp, previous_chain, previous_network, previous_fees, saved_timestamp, blockchain_timer_id
    if not app_running:
        return  # Don't do anything if the app is not running
    current_time = time.time()
    if not (force_update or (current_time - last_blockchain_update >= config['update_intervals']['blockchain'])): # 600 seconds = 10 minutes
        return  # Not due yet

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
        next_delay_ms = time_until_next_aligned_update(config['update_intervals']['blockchain']) * 1000
    except Exception as e: # Failure of RPC connection, or bad data returned from it
        logging.error(f"{get_timestamp()} - Error updating blockchain info: {e}")
        next_delay_ms = 60000  # Retry in 1 minute rather than recursing immediately

    if app_running:
        if blockchain_timer_id is not None:
            root.after_cancel(blockchain_timer_id)
        blockchain_timer_id = root.after(int(next_delay_ms), update_blockchain_info)

def format_difficulty(difficulty):
    if difficulty >= 1_000_000_000_000:  # If it's in trillions
        return f"{difficulty / 1_000_000_000_000:.2f}T"
    elif difficulty >= 1_000_000_000:  # If it's in billions
        return f"{difficulty / 1_000_000_000:.2f}B"
    elif difficulty >= 1_000_000:  # If it's in millions
        return f"{difficulty / 1_000_000:.2f}M"
    else:
        return f"{difficulty:,.2f}"

def format_hashrate(hashrate_hs):
    """Format a hashrate given in H/s, picking whichever unit (ZH/s down to
    TH/s) keeps the number readable — matches how mempool.space labels its
    hashrate axis, where the network's current ~900 EH/s and >1 ZH/s peaks
    both need to read cleanly on the same chart."""
    if hashrate_hs >= 1e21:
        return f"{hashrate_hs / 1e21:.2f} ZH/s"
    elif hashrate_hs >= 1e18:
        return f"{hashrate_hs / 1e18:.0f} EH/s"
    elif hashrate_hs >= 1e15:
        return f"{hashrate_hs / 1e15:.0f} PH/s"
    elif hashrate_hs >= 1e12:
        return f"{hashrate_hs / 1e12:.0f} TH/s"
    else:
        return f"{hashrate_hs:,.0f} H/s"

def get_next_halving_info(current_height, avg_block_time_seconds=600):
    """Project the next halving's block height and date from the current
    block height and a recent average block time (seconds/block). Halvings
    land every 210,000 blocks."""
    halving_interval = 210_000
    next_halving_block = ((current_height // halving_interval) + 1) * halving_interval
    remaining_blocks = next_halving_block - current_height
    estimated_date = datetime.now() + timedelta(seconds=remaining_blocks * avg_block_time_seconds)
    return next_halving_block, remaining_blocks, estimated_date

def main():
    global root
    try:
        root = create_display()
        update_display() # Start the scheduling loop
        
        # Schedule countdown to start after GUI is ready
        root.after(500, update_countdown)

        # Picks up chart_alternating if it was already "on" in config.
        restart_chart_alternation()

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