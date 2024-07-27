import network
import ntptime
import urequests
import time
import json
from machine import Pin,SPI,PWM
import framebuf
from lcd import LCD_1inch8

BL = 13


# Replace with your Wi-Fi network details
SSID = 'EE-NCCX77'
PASSWORD = 'KCN6ndJQJnTKCP'

API_URL = 'https://api.octopus.energy/v1/products/AGILE-18-02-21/electricity-tariffs/E-1R-AGILE-18-02-21-A/standard-unit-rates/'

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
        
def get_energy_price():
    headers = {
        'Content-Type': 'application/json'
    }
    ct = time.localtime()
    if ct[4] < 30:
        ft = '?period_from={:04}-{:02}-{:02}T{:02}:00Z&period_to={:04}-{:02}-{:02}T{:02}:29Z'.format(ct[0],ct[1], ct[2], ct[3],ct[0],ct[1], ct[2], ct[3])
    else:
        ft = '?period_from={:04}-{:02}-{:02}T{:02}:30Z&period_to={:04}-{:02}-{:02}T{:02}:59Z'.format(ct[0],ct[1], ct[2], ct[3],ct[0],ct[1], ct[2], ct[3])
    print(API_URL + ft)
    try:
        response = urequests.get(API_URL + ft, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # Assuming the API returns a JSON with a "results" field containing "price_in_pence_per_kwh"
            current_price = data['results'][0]['value_inc_vat']  # Adjust according to actual API response
            print('Current energy price: £{:.4f}'.format(current_price / 100))
            return current_price
        else:
            print('Failed to fetch energy price. Status code:', response.status_code)
        response.close()
    except Exception as e:
        print('Failed to get energy price:', e)

def main():
    connect_to_wifi(SSID, PASSWORD)
    get_time()
    pwm = PWM(Pin(BL))
    pwm.freq(1000)
    pwm.duty_u16(32768)#max 65535

    LCD = LCD_1inch8()
    #color BRG

    ntptime.settime()
    price = get_energy_price()
    
    while True:
        current_time = time.localtime()
        hour = current_time[3]
        minute = current_time[4]
        second = current_time[5]
        formatted_time = '{:02}:{:02}:{:02}'.format(hour, minute, second)
        LCD.fill(LCD.BLACK)
        LCD.text(formatted_time,30,48,LCD.WHITE)
        LCD.text(str(price),30,58,LCD.WHITE)
        LCD.show()
        time.sleep_ms(1000)
        

if __name__ == '__main__':
    main()