#!/bin/bash
#
# 02_maas-commission_wol.sh - Enable Wake On LAN when network interface started
#
# --- Start MAAS 1.0 script metadata ---
# name: 00_maas-commission_wol.sh
# title: Enable Wake On LAN when network interface started
# description: Enable Wake On LAN when network interface started
# script_type: commissioning
# parallel: any
# timeout: 00:05:00
# --- End MAAS 1.0 script metadata ---
 
# Function to check the distribution and install wakeonlan
install_wakeonlan() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        case "$ID" in
            ubuntu|debian)
                echo "Detected Debian-based distribution."
                sudo apt update && sudo apt install -y wakeonlan
                ;;
            fedora)
                echo "Detected Fedora distribution."
                sudo dnf install -y wakeonlan
                ;;
            centos|rhel)
                echo "Detected CentOS/RHEL distribution."
                sudo yum install -y wakeonlan
                ;;
            arch)
                echo "Detected Arch Linux distribution."
                sudo pacman -Syu wakeonlan
                ;;
            *)
                echo "Unsupported Linux distribution: $ID"
                exit 1
                ;;
        esac
    else
        echo "Cannot determine the Linux distribution."
        exit 1
    fi
}
 
# Main script execution
echo "Installing wakeonlan..."
install_wakeonlan
 
if [[ $? -eq 0 ]]; then
    echo "wakeonlan installed successfully."
else
    echo "Failed to install wakeonlan."
    exit 1
fi
 
# Identify the network interface with the specified flags
INTERFACE=$(ip -o link show | grep "<BROADCAST,MULTICAST,UP,LOWER_UP>" | awk -F': ' '{print $2}' | awk '{print $1}' | xargs)
if [ -n "$INTERFACE" ]; then
  echo "Network interface identified: $INTERFACE"
   
  # Install ethtool if not already installed
  if ! command -v ethtool &> /dev/null; then
    echo "ethtool is not installed. Installing ethtool..."
    sudo apt-get update && sudo apt-get install -y ethtool
  fi
   
  # Enable Wake-on-LAN
  sudo ethtool -s "$INTERFACE" wol g
   
  # Verify that Wake-on-LAN has been enabled
  WOL_STATUS=$(sudo ethtool "$INTERFACE" | grep "Wake-on:" | awk 'NR==2 {print $1$2}')
   
  if [ "$WOL_STATUS" == "Wake-on:g" ]; then
    echo "Wake-on-LAN successfully enabled on interface $INTERFACE"
  else
    echo "Failed to enable Wake-on-LAN on interface $INTERFACE. Current Wake-on status: $WOL_STATUS"
  fi
else
  echo "No network interface with the specified flags found."
fi
 
# Create the enable_wol.sh script
ENABLE_WOL_SCRIPT="/usr/local/bin/enable_wol.sh"
echo "#!/bin/bash
# Identify the network interface with the specified flags
INTERFACE=\$(ip -o link show | grep \"<BROADCAST,MULTICAST,UP,LOWER_UP>\" | awk -F': ' '{print \$2}' | awk '{print \$1}' | xargs)
if [ -n \"\$INTERFACE\" ]; then
  echo \"Network interface identified: \$INTERFACE\"
   
  # Enable Wake-on-LAN
  sudo ethtool -s \"\$INTERFACE\" wol g
   
  # Verify that Wake-on-LAN has been enabled
  WOL_STATUS=\$(sudo ethtool \"\$INTERFACE\" | grep \"Wake-on:\" | awk 'NR==2 {print \$1\$2}')
   
  if [ \"\$WOL_STATUS\" == \"Wake-on:g\" ]; then
    echo \"Wake-on-LAN successfully enabled on interface \$INTERFACE\"
  else
    echo \"Failed to enable Wake-on-LAN on interface \$INTERFACE. Current Wake-on status: \$WOL_STATUS\"
  fi
else
  echo \"No network interface with the specified flags found.\"
fi" | sudo tee $ENABLE_WOL_SCRIPT
 
# Make the enable_wol.sh script executable
sudo chmod +x $ENABLE_WOL_SCRIPT
 
# Create the systemd service file
SERVICE_FILE="/etc/systemd/system/enable_wol.service"
echo "[Unit]
Description=Enable Wake-on-LAN
After=network.target
 
[Service]
Type=oneshot
ExecStart=$ENABLE_WOL_SCRIPT
 
[Install]
WantedBy=multi-user.target" | sudo tee $SERVICE_FILE
 
# Reload systemd to recognize the new service
sudo systemctl daemon-reload
 
# Enable the service to run at startup
sudo systemctl enable enable_wol.service
 
# Start the service immediately
sudo systemctl start enable_wol.service
