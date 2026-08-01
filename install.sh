#!/bin/bash
echo "########################################################################"
echo "Preparing system for install..."
echo "########################################################################"

# Save the opening directory as the project_file_path
project_file_path=$(pwd)
repo_file_name="btc_piDisplay"
program_name="piDisplay.py"
btc_venv="bitcoin_env/bin/activate"

sudo apt-get update # Update package lists
sudo apt-get install -y git python3-venv feh # Install dependencies

echo "########################################################################"
echo "Creating virtual environment..."
python3 -m venv bitcoin_env
echo "Updating DISPLAY variable"
sed -i '38i export DISPLAY=:0.0' $btc_venv
echo "Activating environment"
source $btc_venv
echo "########################################################################"
echo "Installing dependencies..."
# Install Python dependencies
pip install -r requirements.txt
echo "Requirements installed... Exiting venv."
deactivate

# echo "########################################################################"
# for i in {1..2}; do # Sleep for 2 seconds.
#     echo "."
#     sleep 1 # echo three . to create space
# done
# Create executable sh on Desktop
# read -p "Would you like to create a desktop icon to run your script? (Y/N): " user_input
# if [ "${user_input^^}" = "Y" ]; then
cd /home/$USER/Desktop/
cat << EOF > "Run Display.sh" # Update to Run Display.sh
#!/bin/bash

# Activate the virtual environment
source $project_file_path/$btc_venv # This should point to the virtual environment of the repository.

# Run the Python script
python3 $project_file_path/$program_name

EOF
    chmod +x "Run Display.sh"
# fi

echo "########################################################################"
echo "Would you like piDisplay to start automatically on boot?"
echo "This installs a systemd service that launches the display once the desktop session is ready, and restarts it if it ever crashes."
read -p "Enable auto-start on boot? (Y/N): " autostart_input
autostart_enabled=false
if [ "${autostart_input^^}" = "Y" ]; then
    autostart_enabled=true
    echo "Installing systemd service..."
    sudo tee /etc/systemd/system/piDisplay.service > /dev/null << EOF
[Unit]
Description=Bitcoin Node Display (piDisplay)
After=graphical.target
Wants=graphical.target

[Service]
Type=simple
User=$USER
Environment=DISPLAY=:0.0
Environment=XAUTHORITY=/home/$USER/.Xauthority
WorkingDirectory=$project_file_path
ExecStart=$project_file_path/bitcoin_env/bin/python3 $project_file_path/$program_name
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable piDisplay.service
    echo "Service installed and enabled. It will start automatically on the next boot."
    echo "Check status any time with: sudo systemctl status piDisplay.service"
    echo "Tail logs with: journalctl -u piDisplay.service -f"
    echo "Disable auto-start with: sudo systemctl disable --now piDisplay.service"
fi

echo "You will need to set up your RPC node connection (in .env) as well as the desired update intervals (in config.json)..."
read -p "Would you like to do that now? (Y/N): " user_input
if [ "${user_input^^}" = "Y" ]; then
    cd $project_file_path/ # Navigate to the project root folder
    if [ ! -f .env ]; then
        cp .env.example .env # Seed .env from the committed example so there's something to edit.
    fi
    echo "########################################################################"
    echo "First, .env: add RPC_<NAME>_USER / _HOST / _PASSWORD / _PORT for your node."
    echo "<NAME> is whatever profile name you'll use for 'connect_to' in config.json (e.g. RPC_NUC1_USER for connect_to \"NUC1\")."
    echo "This file is gitignored, so it's safe to put real credentials here — never put them in config.json."
    echo "Use CTRL+x to save your updates."
    
    sleep 2
    nano .env # Open the env file for editing

    echo "########################################################################"
    echo "Now, config.json: set 'connect_to' to the profile name you just used in .env."
    echo "'update_intervals' should be updated with SECONDS between refreshes. Example: 60 = refresh every 60 seconds."
    echo "Use CTRL+x to save your updates."
    echo "Opening in 5 seconds..."
    sleep 2
    nano config.json # Open the config file for editing
fi

echo "########################################################################"
echo "Optional: show a receive-address QR code next to Node metrics on the Node screen."
read -p "Bitcoin receive address to display (leave blank to skip): " wallet_address_input
wallet_address_input=$(echo "$wallet_address_input" | xargs) # Trim stray whitespace from pasted input.
cd $project_file_path/
if [ ! -f .env ]; then
    cp .env.example .env # Seed .env from the committed example, in case the RPC setup step above was skipped.
fi
if [ -n "$wallet_address_input" ]; then
    if grep -q '^WALLET_ADDRESS=' .env; then
        sed -i "s|^WALLET_ADDRESS=.*|WALLET_ADDRESS=$wallet_address_input|" .env
    else
        echo "WALLET_ADDRESS=$wallet_address_input" >> .env
    fi
    echo "Saved. The QR code will appear on the Node screen."
else
    # Blank out .env.example's sample WALLET_ADDRESS (if present) so nothing
    # is shown unless you actually entered an address of your own.
    if grep -q '^WALLET_ADDRESS=' .env; then
        sed -i "s|^WALLET_ADDRESS=.*|WALLET_ADDRESS=|" .env
    fi
    echo "Skipped — Developer's default QR code will be shown. Add WALLET_ADDRESS to .env any time to display your own address!"
fi
echo "########################################################################"
for i in {1..3}; do # Sleep for 3 seconds.
    echo "."
    sleep 1 # echo three . to create space
done
echo "Installation complete!"
echo "Launching APP!"

for i in {1..3}; do # Sleep for 3 seconds.
    echo "."
    sleep 1 # echo three . to create space
done

if [ "$autostart_enabled" = true ]; then
    sudo systemctl start piDisplay.service # Launch via the service instead of nohup so there's only ever one instance running.
else
    cd /home/$USER/Desktop/
    nohup "./Run Display.sh" > "$project_file_path/nohup.log" 2>&1 & # Launch app with nohup so you can close the terminal. The app's own log (bitcoin_display.log) is written by piDisplay.py into the repo directory.
fi

echo "########################################################################"