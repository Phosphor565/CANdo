#!/usr/bin/python3
import argparse
import threading
import time
import random
import pygame as pg
import can
from can import Message
from can import Listener
import cantools

# Load in CAN DB file (.dbc)
db = cantools.database.load_file('CANdo_db.dbc')
# Load messages that will be used in this simulation
speed_message = db.get_message_by_name('Speed')
indicator_message = db.get_message_by_name('TurnSignals')
doors_message = db.get_message_by_name('Doors')
lights_message = db.get_message_by_name('HeadLights')

# Clock to keep timing of simulation, tick_rate = Frames Per Second
# set to 25 to prevent performance issues within VM
clock = pg.time.Clock()
tick_rate = 25

# Keeps track of the indicator state to allow for blinking
indicator_state = False

# Stores a list with 2 background IDs, for lights on/off
background_id = []

# Declares font for speedometer
pg.font.init()
gauge_font = pg.font.SysFont('Comic Sans MS', 140)

# GUI variables, fits background size in pixels (Width, Height)
(width, height) = (1000, 800)
screen = pg.display.set_mode((width, height))
pg.display.set_caption("CANdo   -   A CAN BUS Simulator")

# CAN BUS (One to Send packets, one to Listen for packets)
s_bus = can.interface.Bus(bustype='socketcan', channel='vcan0', bitrate=500000)
l_bus = can.interface.Bus(bustype='socketcan', channel='vcan0', bitrate=500000)

# Boolean variable that dictates whether the threads are running (global)
running = True


# -------------------------------------------------------------------------------------------------------------------
# > GUI

# is passed the car data from Listening thread
# in format > [lights, locks, indicator_l, indicator_r, current_speed, background_id ]
def update_gui(car_data):
    screen.fill((0, 0, 0))
    # Logic to determine which image should be used ________________________________________
    # Set light icon
    if car_data[0]:
        light_dir = "gui_resources/icons/lights_on.png"
    else:
        light_dir = "gui_resources/icons/lights_off.png"

    # Set lock icon
    if car_data[1]:
        lock_dir = "gui_resources/icons/car_doors_closed.png"
    else:
        lock_dir = "gui_resources/icons/car_doors_open.png"

    # Set LEFT indicator
    if car_data[2]:
        if indicator_state:
            l_dir = "gui_resources/indicators/Indicator_Left_on.png"
        else:
            l_dir = "gui_resources/indicators/Indicator_Left_off.png"
    else:
        l_dir = "gui_resources/indicators/Indicator_Left_off.png"

    # Set RIGHT indicator
    if car_data[3]:
        if indicator_state:
            r_dir = "gui_resources/indicators/Indicator_Right_on.png"
        else:
            r_dir = "gui_resources/indicators/Indicator_Right_off.png"
    else:
        r_dir = "gui_resources/indicators/Indicator_Right_off.png"

    # Get car speed
    car_speed = str(car_data[4])

    # Set background image
    if car_data[5] == 0:
        back_dir = "gui_resources/bg/Controller_BG.png"
    elif car_data[5] == 1:
        back_dir = "gui_resources/bg/Controller_BG_light.png"
    elif car_data[5] == 2:
        back_dir = "gui_resources/bg/keyboard_background.png"
    elif car_data[5] == 3:
        back_dir = "gui_resources/bg/keyboard_background_light.png"

    # Creating Image objects in accordance to the cars state _______________________________
    bg = pg.image.load(back_dir)
    light = pg.image.load(light_dir)
    lock = pg.image.load(lock_dir)
    ind_l = pg.image.load(l_dir)
    ind_l = pg.transform.scale(ind_l, (60, 60))
    ind_r = pg.image.load(r_dir)
    kmh = gauge_font.render(car_speed, False, (255, 255, 255))
    ind_r = pg.transform.scale(ind_r, (60, 60))

    # Placing images onto the display (background goes first)
    screen.blit(bg, (0, 0))
    screen.blit(light, (625, 265))
    screen.blit(lock, (260, 265))
    screen.blit(ind_l, (350, 185))
    screen.blit(ind_r, (605, 188))
    screen.blit(kmh, (452, 250))

    # Update display
    pg.display.update()


# ===================================================================================================================
# -------------------------------------------------------------------------------------------------------------------
# > CAN BUS
# Sends CAN message according to data + message type
# 1 > speed
# 2 > indicator
# 3 > Door state
# 4 > Lights
# other > background noise
# Data formatted in accordance to the signals defined in 'CANdo.dbc'

def send_CAN(data, msg_type):
    if msg_type == 1:
        enc_data = speed_message.encode({'VehicleSpeed': data})
        arb_id = speed_message.frame_id
    elif msg_type == 2:
        enc_data = indicator_message.encode({'LeftTurn': data[0], 'RightTurn': data[1]})
        arb_id = indicator_message.frame_id
    elif msg_type == 3:
        enc_data = doors_message.encode({'DoorState': data})
        arb_id = doors_message.frame_id
    elif msg_type == 4:
        enc_data = lights_message.encode({'LightState': data})
        arb_id = lights_message.frame_id
    else:
        # Data received is in following format
        # > data[id, position_data, length_data]
        arb_id = data[0]
        junk_data = random.randint(1, 150)
        enc_data = []
        for x in range(data[2]):
            if x == data[1]:
                enc_data.insert(x, junk_data)
            else:
                enc_data.insert(x, 0)
    # Send message
    msg = Message(data=enc_data, arbitration_id=arb_id, extended_id=False)
    s_bus.send(msg)


# Listens for CAN message + decodes it, will then update GUI
def recieve_CAN():
    global background_id
    listener = Listener()
    # Keeps track of car state
    doors_close = True
    lights = indicator_r = indicator_l = False
    current_speed = 0

    bg_id = background_id[0]

    while running:
        # Valid message boolean to ensure the GUI only updates when a valid signal is received
        valid_message = False

        # Wait until received
        msg = l_bus.recv()
        listener.on_message_received(msg)

        if msg.arbitration_id == speed_message.frame_id:
            decoded_msg = db.decode_message(msg.arbitration_id, msg.data)
            valid_message = True
            current_speed = decoded_msg['VehicleSpeed']
            current_speed = current_speed.__round__()
        elif msg.arbitration_id == indicator_message.frame_id:
            decoded_msg = db.decode_message(msg.arbitration_id, msg.data)
            valid_message = True
            if decoded_msg['RightTurn']:
                indicator_r = True
            else:
                indicator_r = False
            if decoded_msg['LeftTurn']:
                indicator_l = True
            else:
                indicator_l = False
        elif msg.arbitration_id == doors_message.frame_id:
            decoded_msg = db.decode_message(msg.arbitration_id, msg.data)
            valid_message = True
            if decoded_msg['DoorState'] == "Closed":
                doors_close = False
            elif decoded_msg['DoorState'] == "Open":
                doors_close = True
        elif msg.arbitration_id == lights_message.frame_id:
            decoded_msg = db.decode_message(msg.arbitration_id, msg.data)
            valid_message = True
            if decoded_msg['LightState'] == "On":
                lights = True
                bg_id = background_id[1]
            elif decoded_msg['LightState'] == "Off":
                lights = False
                bg_id = background_id[0]
        # Only update GUI if message is valid to prevent performance issues
        if valid_message:
            # concatenate data within a list and pass it to update_gui
            car_data = [lights, doors_close, indicator_l, indicator_r, current_speed.__round__(), bg_id]
            update_gui(car_data)


# Selects random message from array of potential Junk messages and passes it to send_CAN
def random_CAN(random_data):
    if random_data:
        end_data_array = len(random_data) - 1
        data_select = random.randint(0, end_data_array)
        # send random data [] > data[id, position_data, length_data]
        send_CAN(random_data[data_select], 10)


# ===================================================================================================================
# -------------------------------------------------------------------------------------------------------------------
# > LOGIC

# Creates random IDs that will be used to create noise on the CAN BUS, ensures that it doesnt clash with
# any previously set ID's. Volume of random data is dictated by the difficulty set.
# The more data, the more noisy the CAN BUS
def generate_random(volume):
    # Takes volume of background noise and generates entries according to the volume
    if volume == 1:
        data_count = 20
    elif volume == 2:
        data_count = 50
    else:
        data_count = 100

    random_messages = []
    used_ids = [speed_message.frame_id, indicator_message.frame_id, doors_message.frame_id, lights_message.frame_id]
    successful = 0
    while successful < data_count:
        exists = False
        # Generate random ID + check if it has already been used
        random_id = random.randint(50, 999)
        for x in range(4):
            if used_ids[x] == random_id:
                exists = True

        # If ID is free to use
        if not exists:
            # generate a random length of data array + random pos within that length
            random_length = random.randint(1, 7)
            random_pos = random.randint(0, random_length)

            random_message = [random_id, random_pos, random_length]
            random_messages.append(random_message)
            successful = successful + 1

    return random_messages


# Handles further logic on what signal to be sent via the CAN BUS
# left indicator    > [1, 0]
# right indicator   > [0, 1]
# BOTH OFF          > [0, 0]

def send_indicator(indicator_side, end):
    global indicator_state
    if not indicator_state and not end:
        if indicator_side == 1:
            indicator_state = True
            send_CAN([1, 0], 2)
        elif indicator_side == 2:
            indicator_state = True
            send_CAN([0, 1], 2)
    else:
        indicator_state = False
        send_CAN([0, 0], 2)


# Implements a timing mechanism to make sure the indicator blinks on/off
def blink_indicator(last_indication, indicator_side):
    current_time = round(time.time() * 1000)
    if current_time > last_indication + 500:
        send_indicator(indicator_side, False)
        return current_time
    return last_indication


# toggles the locks
# 0 = off   1 = on
def toggle_locks(state):
    if state:
        send_CAN(0, 3)
        return False
    if not state:
        send_CAN(1, 3)
        return True


# toggles the lights
# 0 = off   1 = on
def toggle_lights(state):
    if state:
        send_CAN(0, 4)
        return False
    if not state:
        send_CAN(1, 4)
        return True


# calculates the speed of the car taking into consideration the rate of acceleration or breaking
def calculate_speed(accelerating_rate, breaking_rate, current_speed):
    if accelerating_rate > 0 and breaking_rate < accelerating_rate:
        mod = accelerating_rate / 4
        speed = current_speed + mod
        return speed
    if current_speed >= 0:
        if breaking_rate > 0:
            mod = breaking_rate / 2
            speed = current_speed - mod
            return speed
        elif breaking_rate == 0 and accelerating_rate == 0:
            speed = current_speed - 0.05
            return speed

    return current_speed


# ===================================================================================================================
# -------------------------------------------------------------------------------------------------------------------
# > CONTROLS

# Handles keyboard as controls
def keyboard_controls(random_data):
    global running
    global tick_rate
    locks = True
    lights = indicator_r = indicator_l = False
    current_speed = 0
    last_indication = 0
    breaking_rate = 0
    acceleration_rate = 0
    print("Starting sim...\n")
    while running:
        clock.tick(tick_rate)
        random_CAN(random_data)
        for event in pg.event.get():
            if event.type == pg.QUIT:
                print("Closing...")
                running = False
            elif event.type == pg.KEYDOWN:
                if event.key == pg.K_UP:
                    acceleration_rate = 0.5
                    breaking_rate = 0
                if event.key == pg.K_DOWN:
                    breaking_rate = 0.5
                    acceleration_rate = 0
                if event.key == pg.K_LEFT:
                    indicator_l = True
                if event.key == pg.K_RIGHT:
                    indicator_r = True
                if event.key == pg.K_RETURN:
                    lights = toggle_lights(lights)
                if event.key == pg.K_RSHIFT:
                    locks = toggle_locks(locks)
            elif event.type == pg.KEYUP:
                if event.key == pg.K_UP:
                    acceleration_rate = 0
                if event.key == pg.K_DOWN:
                    breaking_rate = 0
                if event.key == pg.K_LEFT:
                    indicator_l = False
                    send_indicator(1, True)
                if event.key == pg.K_RIGHT:
                    indicator_r = False
                    send_indicator(2, True)

        if indicator_l:
            last_indication = blink_indicator(last_indication, 1)
        if indicator_r:
            last_indication = blink_indicator(last_indication, 2)

        current_speed = calculate_speed(acceleration_rate, breaking_rate, current_speed)
        send_CAN(current_speed.__round__(), 1)


# Handles gamepad as controls
def gamepad_controls(random_data):
    pg.joystick.init()
    current_speed = 0
    last_indication = 0
    global tick_rate
    print("Starting sim...\n")

    # Gets the controls of the connected gamepad
    gamepads = [pg.joystick.Joystick(x) for x in range(pg.joystick.get_count())]
    # Checks to see that a gamepad exists
    if len(gamepads) > 0:
        gamepads[0].init()
        axes = gamepads[0].get_numaxes()
        deadzone_trigger = 0
        lights = indicator_r = indicator_l = False
        locks = True
        global running
        while running:
            clock.tick(tick_rate)
            random_CAN(random_data)
            breaking_rate = 0
            acceleration_rate = 0
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    print("Closing...")
                    running = False
                elif event.type == pg.JOYBUTTONDOWN:
                    if event.button == 0:
                        lights = toggle_lights(lights)
                    elif event.button == 1:
                        locks = toggle_locks(locks)
                    elif event.button == 4:
                        indicator_l = True
                    elif event.button == 5:
                        indicator_r = True
                elif event.type == pg.JOYBUTTONUP:
                    if event.button == 4:
                        indicator_l = False
                        send_indicator(1, True)
                    elif event.button == 5:
                        indicator_r = False
                        send_indicator(2, True)
            # get the axis of triggers
            for i in range(axes):
                axis = gamepads[0].get_axis(i)
                if i == 2 and axis > deadzone_trigger:
                    breaking_rate = axis
                if i == 5 and axis > deadzone_trigger:
                    acceleration_rate = axis

            if indicator_l:
                last_indication = blink_indicator(last_indication, 1)
            if indicator_r:
                last_indication = blink_indicator(last_indication, 2)

            current_speed = calculate_speed(acceleration_rate, breaking_rate, current_speed)
            send_CAN(current_speed.__round__(), 1)

    else:
        print("ERROR - Controller not detected")
        running = False
        # Sends dummy CAN message to prevent hanging as Listener thread waits for a message
        send_CAN([1, 2, 3], 10)


# ===================================================================================================================
# -------------------------------------------------------------------------------------------------------------------
# MISC
# Prints the header
def print_header():
    print("""
   _____          _   _     _                     
  / ____|   /\   | \ | |   | |                    
 | |       /  \  |  \| | __| | ___                
 | |      / /\ \ | . ` |/ _` |/ _ \               
 | |____ / ____ \| |\  | (_| | (_) |    
  \_____/_/    \_\_| \_|\__,_|\___/    (_) (_) (_)
                                                  
    """)
    print("A CAN BUS simulating program\n")


# =====================================================================================================================
# --------------------------------------------------------------------------------------------------------------------
# THREADING
# Handles the listening thread that listens for incoming CAN messages and updates the GUI according to the messages
def listener_thread():
    recieve_CAN()


# Handles a sending thread which takes in user inputs and produces packets to be sent on the CAN BUS
def sender_thread(keyboard, random_noise, noise_volume):
    random_data = []
    if random_noise:
        random_data = generate_random(noise_volume)
    if keyboard:
        print("Controller set to - KEYBOARD\n")
        keyboard_controls(random_data)
    else:
        print("Controller set to - GAMEPAD\n")
        gamepad_controls(random_data)


# =====================================================================================================================

# MAIN
def main():
    # This will be choice
    print_header()
    parser = argparse.ArgumentParser()
    parser.add_argument("-g", "--gamepad", help="Instructs CANdo that you wish to use a gamepad (keyboard is default)",
                        action="store_false")
    parser.add_argument("-X", help="Disables background noise (Cheating if reverse engineering)", action="store_false")
    parser.add_argument("-d", "--difficulty", choices=[1, 2, 3], default=2, nargs="?",
                        help="used to set volume of background data, that makes it harder to reverse engineer "
                             "signals. 1 = EASY, 2 = MEDIUM, 3 = HARD (MEDIUM is default)",
                        type=int, metavar='')

    args = parser.parse_args()
    keyboard_selected = args.gamepad
    random_noise = args.X
    noise_volume = args.difficulty

    # Setting background ID according to what controller is selected
    global background_id
    if keyboard_selected:
        background_id = [2, 3]
    else:
        background_id = [0, 1]

    # Starts Sender Thread and Listener Thread
    # SENDER    = Handles controls + Encoding / Sending CAN messages
    # LISTENER  = Listens for and decodes CAN messages + updates GUI

    sender_thread1 = threading.Thread(target=sender_thread, args=(keyboard_selected, random_noise, noise_volume))
    listener_thread1 = threading.Thread(target=listener_thread)
    sender_thread1.start()
    listener_thread1.start()


if __name__ == "__main__":
    main()
