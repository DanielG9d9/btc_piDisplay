#!/bin/bash
echo "########################################################################"
echo "Preparing system for install..."
echo "########################################################################"

# Save the opening directory as the project_file_path
project_file_path=$(pwd)
repo_file_name="btc_piDisplay"
# Update package lists
sudo apt-get update

# Install dependencies
sudo apt-get install -y git python3-venv

# ask user for repository location
# echo "Enter the filepath for the repository: "
# read -p "Example: /home/$USER/Documents/" directory_path

# Check if the directory exists
# if [ ! -d "$directory_path" ]; then
#     echo "Directory does not exist. Creating it now..."
#     mkdir -p "$directory_path"  # Create the directory, including parent directories if needed
# else
#     echo "Directory already exists."
# fi
# CD to future  desired repository location
# cd $repository_folder
# Clone your repository
# git clone git@github.com:DanielG9d9/btc_piDisplay.git
# echo "Repository cloned to: $repository_folder in $repo_file_name"
# cd $repository_folder/$repo_file_name
# Create and activate a virtual environment
#########################
echo "Creating virtual environment..."
python3 -m venv bitcoin_env
echo "Updating DISPLAY variable"
sed -i '38i export DISPLAY=:0.0' filename
echo "Activating environment"
source bitcoin_env/bin/activate

echo "Installing dependencies..."
# Install Python dependencies
pip install -r requirements.txt
echo "Requirements installed... Exiting venv."
deactivate

# Create executable sh on Desktop
read -p "Would you like to create a desktop icon to run your script? (Y/N): " user_input

if [ "${user_input^^}" = "Y" ]; then
    cd /home/$USER/Desktop/
    cat << EOF > "Test Run Display.sh" # Update to Run Display.sh
#!/bin/bash

# Activate the virtual environment
source $project_file_path/bitcoin_env/bin/activate # This should point to the virtual environment of the repository.

# Run the Python script
python3 $project_file_path/piDisplay.py # This should point to the .py for the program.

EOF
    chmod +x "Test Run Display.sh"
fi

# Any additional setup steps
printf '%.3s' "..." # echo three . to create space
read -p "You will need to update the config file with your RPC node connection as well as the desired update intervals...\nWould you like to do that now? (Y/N): " user_input

if [ "${user_input^^}" = "Y" ]; then
    printf "Update rpc_settings with your node information. You may delete any extra examples if you wish! There are three in rpc_settings.\nNext, update the 'connect_to' variable to the name you used in rpc_settings.\n'update_intervals' should be updated with SECONDS.\nUpdate log_file path with your name ($USER) if not satoshi.\nUse CTRL+x to save your updates."
    echo "Continuing in 10 seconds..."
    sleep 10
    cd $project_file_path/ # Navigate to the project root folder
    nano config.json # Open the config file for editing
fi

echo "Installation complete!"
cd /home/$USER/Desktop/
echo "Launching APP!"
"./Test Run Display.sh" # Update to Run Display.sh