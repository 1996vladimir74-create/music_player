# Final wiring checklist

## RC522

```text
RC522        NodeMCU
SDA/SS  ->   D8
SCK     ->   D5
MOSI    ->   D7
MISO    ->   D6
RST     ->   3.3V
3.3V    ->   3V3
GND     ->   GND
```

## DFPlayer Mini

```text
DFPlayer      NodeMCU
RX       <-   D2 through 1 kOhm
TX       ->   RX
VCC      <-   5V bus
GND      ->   GND
SPK1     ->   speaker wire 1
SPK2     ->   speaker wire 2
```

Do not connect SPK1 or SPK2 to GND.

## EC11 encoder

```text
EC11         NodeMCU
A       ->   D1
B       ->   D3
SW      ->   D4
GND     ->   GND
```

The firmware enables internal pull-ups. Encoder must be released during reset/upload.

## Track buttons

The two buttons share A0 through the already-approved resistor ladder.

```text
3.3V --- 1 kOhm --- A0
                    |
                    +--- button PREVIOUS --- 330 Ohm --- GND
                    |
                    +--- button NEXT ------- 1 kOhm ----- GND
```

The firmware recognizes the two voltage regions and ignores simultaneous press.

## Motor

```text
5V BUS  -> motor +
motor - -> HW-532/LR7843 motor output
HW-532 control/input -> D0
HW-532 GND -> GND
```

Place the 1N5819 flyback diode across the motor terminals according to the diode orientation shown for the approved MOSFET module circuit.

## WS2812B ring

```text
WS2812 5V   -> 5V BUS
WS2812 GND  -> GND
WS2812 DATA -> TX / GPIO1 through 330-470 Ohm
```

## Power

```text
USB-C -> IP5306
Battery -> IP5306 B+ / B-
IP5306 5V -> 5V BUS
IP5306 GND -> common GND
```

Keep the 470-1000 uF capacitor on the 5V bus close to the DFPlayer/WS2812 supply area and the 100 uF local decoupling close to the modules as previously planned.
