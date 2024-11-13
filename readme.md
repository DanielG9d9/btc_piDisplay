# Bitcoin Node Display

This project is intended to easily give Bitcoin node runners a display for their nodes. You can create a brandnew raspberry pi configuration and connect to an existing node via RPC or run the display on top of your current node!

My build consists of a raspberry pi 4 (8gb), 1 TB HHD, and a 5" display from [Amazon](https://www.amazon.com/dp/B0CXTFN8K9).

## Table of Contents


- [Features](#features)
- [Pre-requisites](#pre-requisites)
- [Installation](#install)
- [Manual Start](#manually-starting-the-program)
- [Debug / Testing](#debug--testing)
<!-- - [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact) -->

## Features

- Graphical display of bitcoin price movement (24 hour).
- Displays 24 hour percentage change with color coordinated title.
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
Follow these steps if you're trying to run a new Pi Display.
1. Download the Pi imager from [here](https://www.raspberrypi.com/software/).
2. Open the imager.
3. Insert your Pi SD card into your computer.
4. Select your Pi device, OS, and storage option from the menu.
    - Raspberry Pi OS (64-bit) is what I used.
5. Click Next. You can opt to customize your settings so the Pi can connect to WiFi as soon as it boots. Make sure you click 'YES' after changing the settings.
    - Some beneficial settings include enabling SSH and setting country WLAN and timezone. Those can be changed from desktop preferences on the Pi though too.
    - ENABLE SSH AND USE PASSWORD AUTHENTICATION!
6. Confirm settings and write to the SD card.
7. Boot the Pi with the SD card and ensure you have WiFi.

## Install Display

Follow these steps to install and set up the project:
1. Navigate to where the repository will live.
    ```bash
    cd /home/$USER/Documents # Replace $USER with your user profile name.

2. Clone the repository: 
    - I have used /home/$USER/Documents as my repository directory.
    ```bash
    git clone https://github.com/DanielG9d9/btc_piDisplay.git # This will clone the repository to the directory you run the command from.

3. Navigate to the repository folder you just created:
    - If you are not starting from the line above you may need to 'cd' from root `cd /home/$USER/Documents/btc_piDisplay # Replace $USER with your user profile name.`
    ```bash
    cd btc_piDisplay/
4. Run the install.sh file.
    ```bash
    ./install.sh # Run the script file to install dependencies.

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
    nohup python3 piDisplay.py # Use nohup to ensure the script does not stop when you close the terminal.
## Debug & Testing
If you encounter errors an output log should be created at the location specified in the config file. By default it is set as `"log_file": "/home/$USER/Desktop/bitcoin_display.log"` and should be updated to your custom path when setting other config parameters. More specifically, $USER should be changed to your profile name. If you don't know what your profile name is run the command `whoami` in the terminal of the raspberry pi.