#!/bin/bash

sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y git
sudo apt-get install -y python3-dev tmux python3-pip python3-venv build-essential libasound2-dev portaudio19-dev libatlas-base-dev

mkdir ~/data

python3 -m venv myenv
source myenv/bin/activate

VENV_DIR="$HOME/myenv"

# Define the marker to identify the block in .bashrc
MARKER="# >>> Auto-activate venv on SSH login >>>"

# Check if the marker already exists in .bashrc
if grep -q "$MARKER" "$HOME/.bashrc"; then
    echo "Auto-activation block already exists in .bashrc. No changes made."
else
    echo "Appending auto-activation block to .bashrc..."

    cat <<EOF >> "$HOME/.bashrc"

$MARKER
if [ -n "\$SSH_CONNECTION" ]; then
    if [ -f "$VENV_DIR/bin/activate" ]; then
        source "$VENV_DIR/bin/activate"
        echo "Activated virtual environment: $VENV_DIR"
    fi
fi
# <<< Auto-activate venv on SSH login <<<
EOF

    echo "Auto-activation block appended to .bashrc."
fi

source ~/.bashrc

pip3 install sounddevice

TFVER=2.16.1
WHL="tflite_runtime-${TFVER/-/}-cp311-none-linux_aarch64.whl"
BASE_URL="https://github.com/PINTO0309/TensorflowLite-bin/releases/download/v${TFVER}/"
curl -L -o $WHL $BASE_URL$WHL

pip3 install wheel
pip3 install -U $WHL

pip3 install numpy==1.26.4

# # Old paths, now included in repo
# GHURL="https://raw.githubusercontent.com/birdnet-team/BirdNET-Analyzer/master"
# MODEL="/birdnet_analyzer/checkpoints/V2.4/BirdNET_GLOBAL_6K_V2.4_Model_INT8.tflite"
# LABELS="/birdnet_analyzer/labels/V2.4/BirdNET_GLOBAL_6K_V2.4_Labels_en_uk.txt"
# curl -L -o model_int8.tflite $GHURL$MODEL
# curl -L -o labels.txt $GHURL$LABELS


SETUP_CMDS=(
	"printf \"Setting up i2c and SPI..\\n\""
	"sudo raspi-config nonint do_spi 0"
	"sudo raspi-config nonint do_i2c 0"
	"printf \"Setting up serial for PMS5003..\\n\""
	"sudo raspi-config nonint do_serial_cons 1"
	"sudo raspi-config nonint do_serial_hw 0"
)

for ((i = 0; i < ${#SETUP_CMDS[@]}; i++)); do
	CMD="${SETUP_CMDS[$i]}"
	# Attempt to catch anything that touches config.txt and trigger a backup
	if [[ "$CMD" == *"raspi-config"* ]] || [[ "$CMD" == *"$CONFIG_DIR/$CONFIG_FILE"* ]] || [[ "$CMD" == *"\$CONFIG_DIR/\$CONFIG_FILE"* ]]; then
		do_config_backup
	fi
	if [[ ! "$CMD" == printf* ]]; then
		printf "Running: \"%s\"\n" "$CMD"
	fi
	eval "$CMD"
	check_for_error
done


CONFIG_TXT=(
    "dtoverlay=pi3-miniuart-bt"
    "dtoverlay=adau7002-simple"
	"test"
)

CONFIG_DIR="/boot/firmware"
CONFIG_FILE=config.txt

for CONFIG_LINE in "${CONFIG_TXT[@]}"; do
    if [[ -n "$CONFIG_LINE" ]]; then
        echo "Adding $CONFIG_LINE to $CONFIG_DIR/$CONFIG_FILE"
        sudo sed -i "s|^#${CONFIG_LINE}|${CONFIG_LINE}|" "$CONFIG_DIR/$CONFIG_FILE"
        if ! grep -q "^${CONFIG_LINE}" "$CONFIG_DIR/$CONFIG_FILE"; then
            printf "%s\n" "$CONFIG_LINE" | sudo tee -a "$CONFIG_DIR/$CONFIG_FILE" > /dev/null
        fi
    fi
done

pip3 install pimoroni-bme280 enviroplus pms5003 st7735 ltr559 pillow fonts font-roboto gpiod gpiodevice pandas

# # Not needed for now
# git clone https://github.com/pimoroni/enviroplus-python
# cd enviroplus-python
# ./install.sh
# cd ..


cd juara-field-sensors

read -p "Do you want to reboot now? (y/n): " confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
    echo "Rebooting..."
    sudo reboot
else
    echo "Reboot canceled."
fi
