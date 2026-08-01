# Bitcoin Node Display (piDisplay)

This project is intended to easily give Bitcoin node runners a display for their nodes. You can create a brandnew raspberry pi configuration and connect to an existing node via RPC or run the display on top of your current node!

My build consists of a raspberry pi 4 (8gb), 1 TB HHD, and a 5" display from [Amazon](https://www.amazon.com/dp/B0CXTFN8K9).

## Table of Contents


- [Features](#features)
- [Pre-requisites](#pre-requisites)
- [Installing piDisplay](#Installing-piDisplay)
- [Manual Start](#manually-starting-the-program)
- [Debug / Testing](#debug--testing)
<!-- - [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact) -->

## Features

- Graphical display of bitcoin price movement (24 hour).
- Displays 24 hour percentage change with color coordinated title.
- Mining dashboard (toggle with the "Mining" button): blocks remaining to the next difficulty adjustment, the estimated difficulty change, a next-halving countdown, and a 1-week hashrate / difficulty history chart (via mempool.space).
- Displays node information such as
    - Name of node
    - Connected chain
    - Block height and sync status
    - Low, medium, and high fee status.
    - Current difficulty.
    - CPU Temperature (pi)
- Testing capabilities included to run mock price data

## Pre-requisites
1. You should have a bitcoin node operational on your local network.
2. You should know the RPC login information (user/pwd).
3. You should be able to connect to the target display via ssh (Termius or VS Code) or terminal with a keyboard connected to the Pi.

Recommended node software:
1. Parmanode - https://parmanode.com/install/ (Install it on RaspiPi OS not Linux)
2. RaspiBlitz - https://github.com/raspiblitz/raspiblitz

## Ready pi
Follow these steps if you're trying to run a new Pi Display. You can copy / paste directly into the terminal.
1. Download the Pi imager from [here](https://www.raspberrypi.com/software/).
2. Open the imager.
3. Insert your Pi SD card into your computer.
4. Select your Pi device, OS, and storage option from the menu.
    - Raspberry Pi OS (64-bit) is what I used.
5. Click Next. You can opt to customize your settings so the Pi can connect to WiFi as soon as it boots. Make sure you click 'YES' after changing the settings.
    - If you set your hostname to satoshi then you won't need to update a filepath later on if that's worth anything.
    - Some beneficial settings include enabling SSH and setting country WLAN and timezone. Those can be changed from desktop preferences on the Pi though too.
    - ENABLE SSH AND USE PASSWORD AUTHENTICATION!
6. Confirm settings and write to the SD card.
7. Boot the Pi with the SD card and ensure you have WiFi.

## Install piDisplay

Follow these steps to install and set up the project:
1. Navigate to where the repository will live.
    ```bash
    cd /home/$USER/Documents # No need to replace $USER with your user profile name.

2. Clone the repository: 
    - I have used /home/$USER/Documents as my repository directory.
    ```bash
    git clone https://github.com/DanielG9d9/btc_piDisplay.git # This will clone the repository to the directory you run the command from.

3. Navigate to the repository folder you just created:
    - If you are not starting from the line above you may need to 'cd' from root `cd /home/$USER/Documents/btc_piDisplay # No need to replace $USER with your user profile name.`
    ```bash
    cd btc_piDisplay/
4. Run the install.sh file.
    ```bash
    ./install.sh # Run the script file to install dependencies.  
### Customizing the config file!  

| Variable | Option |
|---|---|
| `connect_to` | Name of the device you want to connect to - configured at the bottom of the config.json.|
| `time_series` | Accepts 'standard' time or will default to 24-hour format |
| `update_intervals` | Specify how often the data should update.Integers are in seconds. |
| `price` | Seconds to update -> Hourly = '3600' |
| `blockchain` | Seconds to update -> 10-minutes = '600' |
| `viewing_mode` | 'Rolling' or 'Static' - Rolling will always show full 24 hours of price data. Static will start at midnight and update with new price data until it resets the following day at midnight. |
| `chart_alternating` | 'off' or 'on' - When on, the main screen automatically alternates between the price chart and the mining dashboard. Also toggleable from Display Settings. |
| `chart_alternating_interval` | '30s', '1m', or '5m' - How often the main screen switches when `chart_alternating` is on. |
| `testing` | Specify if testing so the program will use fake data and work on a desktop display. Can also pass --testing in start command: ```python piDisplay.py --testing``` |
    
## Manually Starting The Program
If you need to manually start the display after a reboot or any reason you can easily do so by double clicking the Run Display.sh icon and "Execute."  
  
You can also start the display remotely from your terminal via ssh!
1. Navigate to your repository folder
    ```bash
    cd /home/$USER/Documents/btc_piDisplay # Navigate to your saved directory.
2. Open the virtual environment.
    ```bash
    source bitcoin_env/bin/activate # Launch the bitcoin_env virtual environment.
3. Run the script from the virtual environment.  
    ```bash
    nohup "/.Run Display.sh" > "$(pwd)/nohup.log" 2>&1 & # Use nohup to ensure the script does not stop when you close the terminal.
## Debug & Testing
If you encounter errors an output log should be created at the location specified in the config file. By default it is set as `"log_file": "bitcoin_display.log"`, a relative path resolved against the repository directory, so the log always lands next to `piDisplay.py` regardless of your current working directory when the app is launched.

Need to kill the app from terminal? Use `pkill -f piDisplay.py`