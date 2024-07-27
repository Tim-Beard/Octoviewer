import network
import ntptime
import urequests
import time
import json

# Replace with your Wi-Fi network details
SSID = 'your_SSID'
PASSWORD = 'your_PASSWORD'

# Replace with your Agile Octopus API key and endpoint
API_KEY = 'your_API_KEY'
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
        
        # Add 10 minutes
        minute += 10
        if minute >= 60:
            minute -= 60
            hour += 1
            if hour >= 24:
                hour -= 24
        
        formatted_time = '{:02}:{:02}'.format(hour, minute)
        print('Current time + 10 minutes:', formatted_time)
    except Exception as e:
        print('Failed to get time:', e)

def get_energy_price(start_time, time_range: bool = False, end_time=None):
    headers = {
        'Content-Type': 'application/json'
    }
    ct = start_time

    if (time_range == True) and (end_time == None):
        if start_time[4] < 30:
            ft = '?period_from={:04}-{:02}-{:02}T{:02}:00Z'.format(ct[0], ct[1], ct[2], ct[3])
        else:
            ft = '?period_from={:04}-{:02}-{:02}T{:02}:30Z'.format(ct[0], ct[1], ct[2], ct[3])
    
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
                valid_from_str = result['valid_from']
                valid_from_time = valid_from_str # time.strptime(valid_from_str, "%Y-%m-%dT%H:%M:%SZ")
                prices.append((price, valid_from_time))
            #formatted_prices = [('£{:.4f}'.format(price / 100), valid_from) for price, valid_from in prices]
            print('Energy prices and valid times:', prices)
            return prices
        else:
            print('Failed to fetch energy prices. Status code:', response.status_code)
        response.close()
    except Exception as e:
        print('Failed to get energy prices:', e)

def main():
    connect_to_wifi(SSID, PASSWORD)
    get_time()
    # Example usage of get_energy_price function
    start_time = (2024, 7, 24, 12, 0, 0, 0, 0)  # Example start time
    end_time = (2024, 7, 24, 14, 0, 0, 0, 0)  # Example end time
    prices = get_energy_price(start_time, time_range=True, end_time=end_time)
    print(prices)

if __name__ == '__main__':
    main()