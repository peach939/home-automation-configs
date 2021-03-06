# SHT85

I tried a number of attempts of getting an accurate temperature and humidity sensor to connect to my WeMos. The main ones I tried were the cheap DHT22 (see [humidor_dht22.py](humidor_dht22.py)) and the BME280 temperature/humidity/pressure sensor, specifically from [KeeYees 3pcs BME280 Compatible with BMP280 Digital 5V Temperature Humidity Sensor Atmospheric Barometric Pressure Board IIC I2C Breakout for Arduino: Amazon.com: Industrial & Scientific](https://www.amazon.com/gp/product/B07KYJNFMD/ref=ppx_yo_dt_b_asin_title_o00_s00?ie=UTF8&psc=1) (see [humidor.py](humidor.py)). Neither of these were anywhere near accurate enough. I developed a test rig that consisted of a small plastic Cambro food storage cube with sealing lid, three WeMos units with various sensors, a Dallas One Wire 18S20 for temperature reference, and a Z-Wave multi-sensor that I'd determined to be relatively accurate for comparison. For humidity, I used a "trick" that I read in a number of places, of filling a small bowl with about half a cup of salt and wetting it just to the point that it reached the consistency of wet sand; this is supposed to maintain 75% humidity in a small enclosed space. Sure enough, within 18 hours, the Z-Wave humidity sensor read 75%. All of my test sensors (DHT22 and BMP280) read between 42 and 54 %RH. Their temperature readings were also wildly (i.e. ~25% of the current value) different from what the Z-Wave sensor and 18S20 agreed on. Unfortunately, these inaccuracies were _not_ linear when I removed all sensors from the enclosed cube and set them either in room air or in my cigar humidor.

This experience led me to search for more-accurate, factory-calibrated temperature and relative humidity sensors, ideally one that I could use with a microcontroller such as the WeMos D1 without too much work or fabrication. My search led me to the $25 USD [Sensirion SHT85](https://www.sensirion.com/en/environmental-sensors/humidity-sensors/sht85-pin-type-humidity-sensor-enabling-easy-replaceability/) which is based on their SHT35 I2C sensor but in a tiny 4-pin package instead of SMD. I certainly wouldn't trust myself to hand solder leads to the 1.27mm pitch pins, but I was able to get a solder-cup socket for it from Mouser, and was able to make the connections by hand. I'd highly recommend this.

## Communication

The datasheet for the SHT85 is available here: [pdf](https://www.sensirion.com/fileadmin/user_upload/customers/sensirion/Dokumente/2_Humidity_Sensors/Datasheets/Sensirion_Humidity_Sensors_SHT85_Datasheet.pdf). I'm really not a low-level communication person and have virtually no I2C experience.

I tried to find an existing MicroPython driver but couldn't, but was able to find the MIT-licensed [agners/micropython-scd30](https://github.com/agners/micropython-scd30) (also published to PyPI). I also found the data sheet for the sensor that library supports, the [SCD30 (pdf)](https://www.sensirion.com/fileadmin/user_upload/customers/sensirion/Dokumente/9.5_CO2/Sensirion_CO2_Sensors_SCD30_Interface_Description.pdf) and they seemed more or less similar. I was also able to find a number of SHT35 libraries or tutorials for the Raspberry Pi, including [this 14core tutorial](https://www.14core.com/wiring-sensiron-shtxx-temperature-sensor-w-d-python/), the MIT-licensed [OlivierdenOuden/Sensirion_SHT35](https://github.com/OlivierdenOuden/Sensirion_SHT35), this seeedstudio [example using a MIT-licensed grove library](https://wiki.seeedstudio.com/Grove-I2C_High_Accuracy_Temp%26Humi_Sensor-SHT35/). I finally stumbled on this [Adafruit CircuitPython SHT31D example](https://learn.adafruit.com/adafruit-sht31-d-temperature-and-humidity-sensor-breakout/python-circuitpython) which is based on the MIT-licensed [adafruit/Adafruit_CircuitPython_SHT31D](https://github.com/adafruit/Adafruit_CircuitPython_SHT31D) library which is in turn based on the MIT-licensed [adafruit/Adafruit_CircuitPython_BusDevice](https://github.com/adafruit/Adafruit_CircuitPython_BusDevice).

## Implementation

I soldered the ends of some breadboard jumpers to the 4-pin socket, providing an easy connection to the headers on the WeMos without exposing the sensor itself to high temperatures. In retrospect, I could've actually color-coded these logically...

| SHT85 Pin | Wire Color | Purpose     | WeMos Pin | GPIO Pin |
|:----------|:-----------|:------------|:----------|:---------|
| 1         | Black      | SCL (Clock) | D1        | 5        |
| 2         | Violet     | VDD (3v3)   | 3v3       | -        |
| 3         | White      | VSS (Gnd)   | G         | -        |
| 4         | Gray       | SDA (Data)  | D2        | 4        |

See [humidor_sht85.py](humidor_sht85.py).

## Notes

As of this commit, it's not going well. Nothing was showing up on address 44, and when I run the current script, I just get:

```
Scanning I2C...

 ets Jan  8 2013,rst cause:2, boot mode:(3,7)

load 0x40100000, len 31024, room 16 
tail 0
chksum 0xb4
load 0x3ffe8000, len 1104, room 8 
tail 8
chksum 0x74
load 0x3ffe8450, len 824, room 0 
tail 8
chksum 0x45
csum 0x45
����'�s��n|�dl$l b��|{�$�'��'�d`��r�$�d�d`��r�$�d�d`��r�$���l$`rl��;d����c��c|lb���c|�Č�ldc��o��'��$o���d�d$���d`�o�����cld섏c���cl�crd;l{�n����cs���ld��Č�l{l#�c��g����cs����ld�����d{�
```