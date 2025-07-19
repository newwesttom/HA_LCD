from machine import Pin, SPI, PWM
import network
import time
import urequests
from HA_CONFIG import BASE_URL, TOKEN, labels, states
from WIFI_CONFIG import SSID, PASSWORD, firmware_url
import random
from ota import OTAUpdater

# Initialize LCD and backlight - These settings are for the waveshare pico 1.14" LCD
BL = 13
CS = 9
RST = 12
SCK = 10
MOSI = 11
DC = 8
pwm = PWM(Pin(BL))
pwm.freq(1000)
pwm.duty_u16(32768)
keyA = Pin(15,Pin.IN,Pin.PULL_UP)
keyB = Pin(17,Pin.IN,Pin.PULL_UP)
key2 = Pin(2 ,Pin.IN,Pin.PULL_UP) #上
key3 = Pin(3 ,Pin.IN,Pin.PULL_UP)#中
key4 = Pin(16 ,Pin.IN,Pin.PULL_UP)#左
key5 = Pin(18 ,Pin.IN,Pin.PULL_UP)#下
key6 = Pin(20 ,Pin.IN,Pin.PULL_UP)#右

backgroundcolor = 0x000099
# Initialize Startup States
statetxt = ['NA', 'NA', 'NA', 'NA']
labeltxt = ['NA', 'NA', 'NA', 'NA']
scrollpos = 0
changed = 0    

import framebuf
import framebuf2 as framebuf

# LCD class
class LCD_1inch14(framebuf.FrameBuffer):
    def __init__(self):
        self.width = 240
        self.height = 135
        self.cs = Pin(CS, Pin.OUT)
        self.rst = Pin(RST, Pin.OUT)
        self.cs(1)
        self.spi = SPI(1, 10000000, polarity=0, phase=0, sck=Pin(SCK), mosi=Pin(MOSI), miso=None)
        self.dc = Pin(DC, Pin.OUT)
        self.dc(1)
        self.buffer = bytearray(self.height * self.width * 2)
        super().__init__(self.buffer, self.width, self.height, framebuf.RGB565)
        self.init_display()
        self.red   = 0xf800
        self.green = 0x07e0
        self.blue  = 0x001f
        self.white = 0xffff

    def write_cmd(self, cmd):
        self.cs(1)
        self.dc(0)
        self.cs(0)
        self.spi.write(bytearray([cmd]))
        self.cs(1)

    def write_data(self, buf):
        self.cs(1)
        self.dc(1)
        self.cs(0)
        self.spi.write(bytearray([buf]))
        self.cs(1)

    def init_display(self):
        self.rst(1)
        self.rst(0)
        self.rst(1)
        self.write_cmd(0x36)
        self.write_data(0x70)
        self.write_cmd(0x3A)
        self.write_data(0x05)
        self.write_cmd(0xB2)
        for d in [0x0C, 0x0C, 0x00, 0x33, 0x33]: self.write_data(d)
        self.write_cmd(0xB7); self.write_data(0x35)
        self.write_cmd(0xBB); self.write_data(0x19)
        self.write_cmd(0xC0); self.write_data(0x2C)
        self.write_cmd(0xC2); self.write_data(0x01)
        self.write_cmd(0xC3); self.write_data(0x12)
        self.write_cmd(0xC4); self.write_data(0x20)
        self.write_cmd(0xC6); self.write_data(0x0F)
        self.write_cmd(0xD0); self.write_data(0xA4); self.write_data(0xA1)
        self.write_cmd(0xE0)
        for d in [0xD0,0x04,0x0D,0x11,0x13,0x2B,0x3F,0x54,0x4C,0x18,0x0D,0x0B,0x1F,0x23]: self.write_data(d)
        self.write_cmd(0xE1)
        for d in [0xD0,0x04,0x0C,0x11,0x13,0x2C,0x3F,0x44,0x51,0x2F,0x1F,0x1F,0x20,0x23]: self.write_data(d)
        self.write_cmd(0x21)
        self.write_cmd(0x11)
        self.write_cmd(0x29)

    def show(self):
        self.write_cmd(0x2A)
        for d in [0x00, 0x28, 0x01, 0x17]: self.write_data(d)
        self.write_cmd(0x2B)
        for d in [0x00, 0x35, 0x00, 0xBB]: self.write_data(d)
        self.write_cmd(0x2C)
        self.cs(1)
        self.dc(1)
        self.cs(0)
        self.spi.write(self.buffer)
        self.cs(1)
        
    def render(self,image_name,offset_x=0,offset_y=0,background=None,show_rendering=True):
        '''Method to render 16-Bit images on the LCD panel

            Args:
                image_name: path of the encoded image
                offset_x: x co-ordinate of starting position
                offset_y: y co-ordinate of starting position
                background: color of the background
                show_rendering: if True, the process of rendering is shown, else a loading screen is shown
        '''
        self.fill(background)

        f = open(image_name,'r')

        row_count = 0

        while True:
            data = f.readline()
            if not data:
                break
            px_ptr = 0
            # All Even Positions will be Pixel Counts and
            # odd positions will be Pixel Color Values
            data = data.split(',')
            for i in range(len(data)):
                # Reading Count of Homogenous Pixels
                if i%2 == 0:
                    px_count = int(data[i])
                # Reading the Color of the Homogenous Pixels
                else:
                    color = int('0x'+data[i])
                    if color != background:
                        self.hline(px_ptr+offset_x,row_count+offset_y,px_count,color)            
                    px_ptr += px_count
                    
            row_count += 1
            if show_rendering:
                self.show()
            




def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    print("Trying: " + SSID)
    wlan.connect(ssid, password)
    while not wlan.isconnected():
        time.sleep(0.5)
    print("Connected:", wlan.ifconfig())


import urequests

def get_entity_state(entity_id, token, base_url):
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json"
    }

    url = base_url + "/api/states/" + entity_id
    #print("URL: " + url)

    try:
        response = urequests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            result = data["state"]
        else:
            result = "Error"
        response.close()
        return result
    except Exception as e:
        print("Request failed:", e)
        return "Error"


def draw_table(labels, values):
    row_count = len(labeltxt)
    x1 = 1
    y1 = 1
    n = 133
    rowsize = n // row_count
      
    for i in range(len(statetxt)):
        ii = i + scrollpos
        if statetxt[i] in ['on', 'off']:
            statetxt[i] = convert_door_value(statetxt[i])
        
    LCD.fill(backgroundcolor)
    LCD.vline(104,1,133, 0xbbbb)
    for i in range(row_count):
        ii = i + scrollpos #adjust for scroll postiion
        LCD.hline(1, y1, 238, 0xaaaa)
        LCD.circle(2, y1+20, 8 , c=1, f=True)
        display_state(15,y1+10, labeltxt[i]) #Write labels to LCD         
        display_state(112,y1+10, statetxt[i]) #Write states to LCD
        
        y1 = y1 + rowsize
    LCD.show()
    
    
def display_state(x,y,txt):

    LCD.large_text(txt, x, y, 2, 1)  # double size text

def convert_door_value(v):
    if (v == 'off'):
      return('Closed')
    if (v == 'on'):
      return('Open')
    else:
      return('Unknown')
      
    
def get_HA():
    # Home Assistant
    for i in 0,1,2,3:
        print("scroll:" + str(scrollpos))
        labeltxt[i] = get_entity_state(labels[i + scrollpos], TOKEN, BASE_URL)
        print(scrollpos)
        statetxt[i] = get_entity_state(states[i + scrollpos], TOKEN, BASE_URL)
    draw_table(labels, states)





def random_hex_color():
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

# Example usage




#Main Program

LCD = LCD_1inch14()
print("LCD init")

connect_wifi(SSID, PASSWORD)
ota_updater = OTAUpdater(SSID, PASSWORD, firmware_url, "main.py")
ota_updater.download_and_install_update_if_available()


get_HA() # connect to HA and get the states. #Initial Values to compare in the while loop below.

while(1):

    s1 = [states[0],states[1],states[2],states[3]]
    l1 = [labels[0],labels[1],labels[2],labels[3]]
    get_HA() # connect to HA and get the states.

    #test if values changed
    for i in range(len(s1)):   
       
       if s1[i] != states[i]: 
           changed = 1
       else:
           changed = 0
            
       if changed != 0:   
           if l1[i] != labels[i]: 
               changed = 1
           else:
               changed = 0
                
    if changed == 1:
       draw_table(4, labels[1], states[1], labels[2], states[2], labels[3], states[3], labels[4], states[4])
        
    for i in range(0,9):
        if(keyA.value() == 0):
            connect_wifi(SSID, PASSWORD)
        if(keyB.value() == 0):
            backgroundcolor = random_hex_color()
            draw_table(labels, states)
        if(key5.value() == 0):
            print("5")
            if scrollpos != (len(states) -4):
                scrollpos = scrollpos + 1
            draw_table(labels, states)
            
        if(key2.value() == 0):
            print("2")
            if scrollpos > 0:
                scrollpos = scrollpos - 1
            draw_table(labels, states)
                
        time.sleep(1)





