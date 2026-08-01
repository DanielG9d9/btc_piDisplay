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

echo "You will need to update the config file with your RPC node connection as well as the desired update intervals..."
read -p "Would you like to do that now? (Y/N): " user_input
if [ "${user_input^^}" = "Y" ]; then
    echo "########################################################################"
    echo "Update rpc_settings with your node information here!"
    echo "You may delete any extra examples if you wish! There are two in rpc_settings."
    echo "Next, update the 'connect_to' variable to the name you used in rpc_settings."
    echo "'update_intervals' should be updated with SECONDS between refreshes. Example: 60 = refresh every 60 seconds."
    echo "Use CTRL+x to save your updates."
    echo "Opening in 10 seconds..."
    sleep 10
    cd $project_file_path/ # Navigate to the project root folder
    nano config.json # Open the config file for editing
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