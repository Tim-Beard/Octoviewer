import network
import ntptime
import urequests
import time
import json
from machine import Pin,SPI,PWM
import framebuf3 as framebuf
from lcd import LCD_1inch8

#--- Configuration ---------------------

TIME_OFFSET = 1 # Number of hours difference between API's time and local time (+ve if local time is ahead)

# Replace with your Wi-Fi network details
SSID = 'EE-NCCX77'
PASSWORD = 'KCN6ndJQJnTKCP'

# Base URL for Agile Octopus tariff info. Set as appropriate for your area	
# API docs: https://docs.octopus.energy/rest/guides
API_URL = 'https://api.octopus.energy/v1/products/AGILE-18-02-21/electricity-tariffs/E-1R-AGILE-18-02-21-A/standard-unit-rates/'

# Thresholds for price colouring
HIGH_LEVEL = 25.0
MID_LEVEL = 16.0
LOW_LEVEL = 7.5

MARKER_SPACING = 4	# Hours between time markers on the bar graph

#--------------------------------------

LCD = LCD_1inch8()
BL = 13 # Backlight is GP13

def connect_to_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    if not wlan.isconnected():
        print('Connecting to network', ssid)
        wlan.active(True)
        wlan.connect(ssid, password)
        while not wlan.isconnected():
            time.sleep(1)
    print('Network connected!')
    print('IP address:', wlan.ifconfig()[0])

def get_time():
    try:
        ntptime.settime()
        current_time = time.localtime()
        hour = current_time[3]
        minute = current_time[4]
        formatted_time = '{:02}:{:02}'.format(hour, minute)
        print('Current time:', formatted_time)
    except Exception as e:
        print('Failed to get time:', e)
        
def add_minutes_to_time(time_struct, minutes):
    # Convert the time_struct to a timestamp
    timestamp = time.mktime(time_struct)
    
    # Calculate the number of seconds to add
    seconds_to_add = minutes * 60
    
    # Add the seconds to the timestamp
    new_timestamp = timestamp + seconds_to_add
    
    # Convert the new timestamp back to a time_struct
    new_time_struct = time.localtime(new_timestamp)
    
    return new_time_struct

def format_date(time_struct):
    months = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ]
    
    day = time_struct[2]  # Day of the month
    month = months[time_struct[1] - 1]  # Month (time_struct[1] is 1-12)
    year = time_struct[0]  # Year

    return f"{day} {month} {year}"
        
def get_energy_price(start_time, time_range: bool = False, end_time=None):
    # Returns a list of 1 or more prices. The price at start_time is returned as a single entry list if time_range is false
    # The list of prices between the start and end times is returned if and end time is specified
    # If no end time is specified, it returns all available prices starting at start time. 
    headers = {
        'Content-Type': 'application/json'
    }
    ct = start_time
    
    # Either get all avaialble data from the specified start point
    if (time_range == True) & (end_time == None):
        if start_time[4] < 30:
            ft = '?period_from={:04}-{:02}-{:02}T{:02}:00Z'.format(ct[0], ct[1], ct[2], ct[3])
        else:
            ft = '?period_from={:04}-{:02}-{:02}T{:02}:30Z'.format(ct[0], ct[1], ct[2], ct[3])
    # Or, get the data between two times 
    else:    
        if time_range == False:
            et = ct
        else:
            et = end_time

        if start_time[4] < 30:
            ft = '?period_from={:04}-{:02}-{:02}T{:02}:00Z&period_to={:04}-{:02}-{:02}T{:02}:29Z'.format(ct[0], ct[1], ct[2], ct[3], et[0], et[1], et[2], et[3])
        else:
            ft = '?period_from={:04}-{:02}-{:02}T{:02}:30Z&period_to={:04}-{:02}-{:02}T{:02}:59Z'.format(ct[0], ct[1], ct[2], ct[3], et[0], et[1], et[2], et[3])
        
    
    print(API_URL + ft)
    try:
        response = urequests.get(API_URL + ft, headers=headers)
        if response.status_code == 200:
            data = response.json()
            prices = []
            for result in data['results']:
                price = result['value_inc_vat']
                valid_from_time = result['valid_from']
                prices[:0] = [(price, valid_from_time)] # Add to the front of the list as the API returns the items in reverse order
            # print(prices)
            return prices
        else:
            print('Failed to fetch energy prices. Status code:', response.status_code)
        response.close()
    except Exception as e:
        print('Failed to get energy prices:', e)
        
def get_colour(price):
    # Returns the apprpriate colour for the price, based on the thresholds set
    if price > HIGH_LEVEL:
        return LCD.RED
    elif price > MID_LEVEL:
        return LCD.ORANGE
    elif price > LOW_LEVEL:
        return LCD.YELLOW
    else:
        return LCD.GREEN
    
def parse_time_string(time_string):
    # Extracts the date/time elements from a date string returned by the API 
    # Example: "2024-07-24T12:00:00Z"
    year = int(time_string[0:4])
    month = int(time_string[5:7])
    day = int(time_string[8:10])
    hour = int(time_string[11:13])
    minute = int(time_string[14:16])
    second = int(time_string[17:19])
    # Return a tuple compatible with MicroPython's time format
    return (year, month, day, hour, minute, second, 0, 0)

def draw_bar_graph(fb, bar_values, bar_colours, x_start, y_start, max_width, min_val, max_val, bar_width):
    # Draws a bar graph of the price values, and adds time markers
    # Bar colours are coded according to the prices
    
    # Calculate the total height of the bar graph based on max an min values
    graph_height = max_val - min_val
    num_bars = min(len(bar_values), max_width // bar_width)
    if bar_width > 1:
        bar_gap = 1
    else:
        bar_gap = 0
        
    if min_val < 0:
        y_start = y_start - min_val

    for i in range(num_bars):
        value = bar_values[i][0]
        colour = bar_colours[i]
        # Calculate the height of the bar
        bar_height = int(value) #int((value - min_val) * graph_height / (max_val - min_val))
        # Ensure bar height is within the bounds of the graph height
        bar_height = max(-5, min(bar_height, graph_height))

        # Draw the bar
        x = x_start + i * bar_width
        if value > 0:
            fb.fill_rect(x, y_start-bar_height, bar_width-bar_gap, bar_height, colour)
        else:
            fb.fill_rect(x, y_start, bar_width-bar_gap, -bar_height, colour)
        # Draw time markers
        valid_time = parse_time_string(bar_values[i][1])
        hour = (valid_time[3] + TIME_OFFSET) % 24
        if valid_time[4] == 0:
            if (hour % MARKER_SPACING == 0):
                fb.line(x-1, y_start - max_val, x-1, y_start - min_val, LCD.WHITE)
                if hour == 0:
                    fb.fill_rect(x-10, y_start - min_val-1, 18,10,LCD.WHITE)
                    fb.text('{:02}'.format(hour), x-9, y_start - min_val, LCD.BLACK)
                else:
                    fb.text('{:02}'.format(hour), x-9, y_start - min_val, LCD.WHITE)



def main():
    connect_to_wifi(SSID, PASSWORD)
    get_time()
    
    # Backlight setting - adjust the duty to adjust brightness
    pwm = PWM(Pin(BL))
    pwm.freq(1000)
    pwm.duty_u16(16000)#max 65535

    LCD = LCD_1inch8()	# Initialse LCD

    # Fetch the initial price list
    list_prices = get_energy_price(time.localtime(), True)
    now_price = list_prices[0][0]
    next_price = list_prices[1][0]
    
    # Define bargraph parameters
    x_start = 2
    y_start = 105  # Bottom of the graph
    max_width = 160
    min_val = -5
    max_val = 35
    bar_width = 3
    
    while True:
        current_time = time.localtime()
        minute = current_time[4]
        hour = current_time[3]
        # Every half hour, update the prices
        if minute == 0 or minute == 30:
            list_prices = get_energy_price(current_time, True)
            now_price = list_prices[0][0]
            next_price = list_prices[1][0]
        
        if hour == 0 and minute == 0:
            get_time()	# Update the time once a day, to correct any drift
            
        current_time = add_minutes_to_time(current_time, TIME_OFFSET * 60) # 'localtime' is an hour behind actual local time
        hour = current_time[3]
        
        # Write the date and time on the screen
        formatted_time = format_date(current_time) + ' {:02}:{:02}'.format(hour, minute)
        LCD.fill(LCD.BLACK)
        LCD.text(formatted_time,0,0,LCD.WHITE)
        
        # Write the now/next prices table
        LCD.rect(0,12,116,28,LCD.WHITE)
        LCD.rect(0,40,116,28,LCD.WHITE)
        LCD.text_mx_my('Now:  {:.2f}p'.format(now_price), 2, 14, 1, 3, LCD.WHITE)
        LCD.text_mx_my('Next: {:.2f}p'.format(next_price), 2, 42, 1, 3, LCD.WHITE)
        LCD.fill_rect(116,12,40,28, get_colour(now_price))
        LCD.fill_rect(116,40,40,28, get_colour(next_price))
        LCD.rect(116,12,40,28,LCD.WHITE)
        LCD.rect(116,40,40,28,LCD.WHITE)
        
        # Draw the bargraph
        bar_colours = [get_colour(list_prices[i][0]) for i in range(len(list_prices))]
        draw_bar_graph(LCD, list_prices, bar_colours, x_start, y_start, max_width, min_val, max_val, bar_width)

        
        LCD.show()
        time.sleep(60) # Redraw every minute to update the time
        

if __name__ == '__main__':
    main()