# CANdo
A simple CAN bus instrument cluster simulation written in Python. 

This project was inspired by ICSim, by [ZombieCraig](https://github.com/zombieCraig/ICSim).

## Setup
To install the requirments for this project run the following command
```
pip install -r requirements.txt
```

To create the virtual CAN adapter used by this project run the following commands
```
sudo modprobe can
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set up vcan0
```
A setup_vcan.sh file has been included for convenience

## Usage
To start the simulation simply run 
```
python3 CANdo.py
```

The following arguments can be used to change how CANdo runs

- -g = if you wish to use a gamepad
- -X = Dissables background noise (cheating if your practicing reverse engineering CAN signals)
- -d = Difficulty, the following difficulties can be set 1 = EASY, 2 = MEDIUM, 3 = HARD (Medium is default), the harder the difficulty the more background noise
