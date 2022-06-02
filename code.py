# Modified/adapted/start from: https://learn.adafruit.com/adafruit-matrixportal-m4

import gc
import time
import board
import busio
import supervisor
from digitalio import DigitalInOut
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_esp32spi import adafruit_esp32spi_wifimanager
import neopixel
import math
import displayio
import adafruit_display_text.label
import adafruit_lis3dh
from adafruit_matrixportal.matrix import Matrix
from adafruit_bitmap_font import bitmap_font

DEVICECONFIG = "DJ" # use LK for Lui and Ken's board
print("Starting " + DEVICECONFIG + " Board...") 

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

# If you are using a board with pre-defined ESP32 Pins:
esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)

SMALL_FONT = bitmap_font.load_font('/fonts/helvR10.bdf')
SYMBOL_FONT = bitmap_font.load_font('/fonts/6x10.bdf')
SMALL_FONT.load_glyphs('0123456789:/.%❤️')
SYMBOL_FONT.load_glyphs('\u21A5\u21A7\u2764\uFE0F')

spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
"""Use below for Most Boards"""
status_light = neopixel.NeoPixel(
    board.NEOPIXEL, 1, brightness=0.2
)  # Uncomment for Most Boards

# Turn on the lign on wifi access
wifi = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(esp, secrets, status_light)

# ONE-TIME INITIALIZATION FOR DISPLAY-----------------------------------------------

panelName = "messagepanel"

if (DEVICECONFIG == "LK"):
    panelName = "lkmessagepanel"

MATRIX = Matrix(bit_depth=6)
DISPLAY = MATRIX.display
ACCEL = adafruit_lis3dh.LIS3DH_I2C(busio.I2C(board.SCL, board.SDA),
                                   address=0x19)
_ = ACCEL.acceleration # Dummy reading to blow out any startup residue
time.sleep(0.1)
DISPLAY.rotation = (int(((math.atan2(-ACCEL.acceleration.y,
                                     -ACCEL.acceleration.x) + math.pi) /
                         (math.pi * 2) + 0.875) * 4) % 4) * 90

GROUP = displayio.Group()
# 0 = main text
GROUP.append(adafruit_display_text.label.Label(SMALL_FONT, color=0x666666, scale=1, text=DEVICECONFIG + ' starting...' ))
GROUP[0].x = 0
GROUP[0].y = DISPLAY.height // 2 - 7

# 1 = dot to display action
GROUP.append(adafruit_display_text.label.Label(SMALL_FONT, color=0x0000FF, text='.'))

# 2 = clock
GROUP.append(adafruit_display_text.label.Label(SMALL_FONT, color=0x666666, scale=1, text='00:00'))
GROUP[2].x = 37
GROUP[2].y = 27

# 2 = minutes lapsed
GROUP.append(adafruit_display_text.label.Label(SMALL_FONT, color=0x666666, scale=1, text='00'))
GROUP[3].x = 0
GROUP[3].y = 27

DISPLAY.show(GROUP)

prevMessage = ""
minuteCounter = 0
lastTimeUpdated = "00:00"

def getWeather():
    try:
        wResp = wifi.get(secrets["weatherUrl"], headers={"X-AIO-KEY": secrets["aio_key"]} )
        currentWeather = wResp.json()["current"]
        wResp.close()
        wResp = None

        celsiusTemp = round((currentWeather["temperature"]-32)/1.8)

        print(currentWeather)
        GROUP[0].text = currentWeather["summary"]
        GROUP[2].text = str(celsiusTemp) + "/" + str(round(currentWeather["temperature"]))
        GROUP[3].text = "uv:"+ str(currentWeather["uvIndex"])
        
    except (ValueError, RuntimeError) as e:
        print("Weather retrieve failed\n", e)        
        wifi.reset()

while True:

    # Access time API
    print("Querying time...\n")
    GROUP[1].text = "."
    GROUP[1].color = 0xFF0000 #red
    currentTime = ""

    try:
        clockResponse = wifi.get("https://io.adafruit.com/api/v2/time/ISO-8601")
        currentTime = clockResponse.text
        print(clockResponse.text)
        clockResponse.close()
        
    except (ValueError, RuntimeError) as e:
        print("Clock retrieve failed\n", e)
        GROUP[0].text = "Oh oh time..."
        GROUP[0].scale = 1
        GROUP[0].x = 1
        wifi.reset()
        continue
        
    clockResponse = None
    
    # Get current time and display
    timeUpdated = str(currentTime)[11:16]       
    GROUP[2].text = timeUpdated

    # Time is different? then at least one min passed
    if(lastTimeUpdated != timeUpdated):
        minuteCounter = minuteCounter + 1
        lastTimeUpdated = timeUpdated

    # Get latest message 
    print("Retrieving last message...", end="")
    GROUP[1].text = "."
    GROUP[1].color = 0x00FF00 #green

    try:
        response = wifi.get(
            "https://io.adafruit.com/api/v2/"
            + secrets["aio_username"]
            + "/feeds/" + panelName # feed name
            + "/data/last",
            headers={"X-AIO-KEY": secrets["aio_key"]}, 
        )

        json_resp = response.json()
        displayText = json_resp['value']
        response.close()

    except (ValueError, RuntimeError) as e:
        print("Text retrieve failed\n", e)
        GROUP[0].text = "Oh oh text..."
        GROUP[0].scale = 1
        GROUP[0].x = 1
        wifi.reset()
        continue

    response = None
    json_resp = None

    # Get latest message 
    print("Updating screen...", end="")
    GROUP[1].text = "."
    GROUP[1].color = 0xFFFFFF #white

    # Display last message
    print("\n"+displayText)
    time.sleep(1)

    # Review if last message is the same as a minute ago. If new message, reset the minuteCounter
    if(displayText != prevMessage):
        prevMessage = displayText
        minuteCounter = 1

    # Remove dot
    GROUP[1].text = ""       
    #display the minutes lapsed
    GROUP[3].text = str(minuteCounter) + "m"
    
    # calculate the scroll size
    lenDisplayText = (len(displayText) * 10) + 1   
    scrollPos = 64
    timesDisplayed = 0

    # Display the original text
    GROUP[0].scale = 2
    GROUP[0].x = scrollPos
    GROUP[0].text = displayText

    print("\nScroller: ")
    # scroll text to display 5 times
    while timesDisplayed < 5:
        GROUP[0].x = scrollPos
        time.sleep(0.03)
        scrollPos = scrollPos - 1
        if scrollPos < -1*lenDisplayText:
            timesDisplayed = timesDisplayed + 1
            print(str(timesDisplayed))
            scrollPos = 64

    GROUP[0].text = ">.<"
    GROUP[0].x = 0  
    GROUP[0].scale = 1        

    #display the weather for 20 sec
    getWeather()
    time.sleep(20)



    gc.collect()                
 