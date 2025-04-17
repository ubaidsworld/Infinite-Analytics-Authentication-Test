import requests
import time
import datetime
import matplotlib.pyplot as plt

# Binance API details
base_url = "https://api.binance.com"
endpoint = "/api/v3/klines"

# Get current time in milliseconds
current_time_ms = int(time.time() * 1000)

# Parameters to fetch the last 1000 price values
params = {
    "symbol": "BTCUSDT",
    "interval": "1h",
    "endTime": current_time_ms,
    "limit": 1000  # 1000 price values
}

# Fetch data from Binance
response = requests.get(base_url + endpoint, params=params)
data = response.json()

# Extracting timestamps and closing prices
timestamps = [int(item[0]) for item in data]  # Open time
closing_prices = [float(item[4]) for item in data]  # Closing price

# Convert timestamps to human-readable format
dates = [datetime.datetime.fromtimestamp(ts / 1000) for ts in timestamps]

# Plotting the data
plt.figure(figsize=(12, 6))
plt.plot(dates, closing_prices, label='BTC Price (USDT)', color='blue')
plt.xlabel('Time')
plt.ylabel('Price (USDT)')
plt.title('BTC/USDT Price Chart - Last 1000 Values')
plt.grid(True)
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
