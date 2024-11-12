# Bitcoin Node Display

This project is intended to easily give Bitcoin node runners a display for their nodes. You can create a brandnew raspberry pi configuration and connect to an existing node via RPC or run the display on top of your current node!

My build consists of a raspberry pi 4 (8gb), 1 TB HHD, and a 5" display from [Amazon](https://www.amazon.com/dp/B0CXTFN8K9).

## Table of Contents


- [Features](#features)
- [Pre-requisites](#pre-requisites)
- [Installation](#installation)
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
3. You should be able to connect to the target display via ssh or terminal.

## Installation

Follow these steps to install and set up the project:

1. Clone the repository: 
    - Be sure to cd into the folder you want this to live in
   ```bash
   cd /home/$USER/Documents # Replace $USER with your user profile name.
   git clone https://github.com/DanielG9d9/btc_piDisplay.git # This will clone the repository to the directory you run the command from.

2. Navigate to the repository folder
    ```bash
    cd /home/$USER/Documents/btc_piDisplay
3. Run the install.sh file
    ```bash
    ./install.sh