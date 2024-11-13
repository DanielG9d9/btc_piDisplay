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
sudo apt-get install -y git python3-venv # Install dependencies

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

# Create executable sh on Desktop
read -p "Would you like to create a desktop icon to run your script? (Y/N): " user_input

if [ "${user_input^^}" = "Y" ]; then
    cd /home/$USER/Desktop/
    cat << EOF > "Run Display.sh" # Update to Run Display.sh
#!/bin/bash

# Activate the virtual environment
source $project_file_path/$btc_venv # This should point to the virtual environment of the repository.

# Run the Python script
python3 $project_file_path/$program_name

EOF
    chmod +x "Run Display.sh"
fi
echo "########################################################################"
# Any additional setup steps
printf '%.3s' "..." # echo three . to create space
echo "You will need to update the config file with your RPC node connection as well as the desired update intervals..."
read -p "Would you like to do that now? (Y/N): " user_input
if [ "${user_input^^}" = "Y" ]; then
    echo "Update rpc_settings with your node information here!"
    echo "You may delete any extra examples if you wish! There are three in rpc_settings."
    echo "Next, update the 'connect_to' variable to the name you used in rpc_settings."
    echo "'update_intervals' should be updated with SECONDS between refreshes. Example: 60 = refresh every 60 seconds."
    printf "Update log_file path with your name ($USER) if not satoshi."
    echo "Use CTRL+x to save your updates."
    echo "Continuing in 5 seconds..."
    for i in {1..3}; do # Sleep for 6 seconds.
    echo "."
    sleep 2
done
    cd $project_file_path/ # Navigate to the project root folder
    nano config.json # Open the config file for editing
fi
# Should we setup a custom background??
echo "########################################################################"
printf '%.3s' "..." # echo three . to create space
echo "Installation complete!"
cd /home/$USER/Desktop/
echo "Launching APP!"
printf '%.3s' "..." # echo three . to create space
nohup "./Run Display.sh" > /home/$USER/Desktop/bitcoin_display.log 2>&1 & # Launch app with nohop so you can close the terminal.# Update to Run Display.sh
echo "########################################################################"
echo "********************** DONE ********************************************"