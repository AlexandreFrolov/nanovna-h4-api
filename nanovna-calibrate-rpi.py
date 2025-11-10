#!/usr/bin/env python3
import serial
import time

def simple_calibrate():
    ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
    time.sleep(2)

    steps = [
        "cal reset",
        "cal open",
        "cal short",
        "cal load",
        "cal thru",
        "cal done",
        "save 0"
    ]

    prompts = [
        "Сброс... (Enter)",
        "OPEN подключен? (Enter)",
        "SHORT подключен? (Enter)",
        "LOAD подключен? (Enter)",
        "THRU подключен? (Enter)",
        "Расчет... (Enter)",
        "Сохранение... (Enter)"
    ]

    for i, (cmd, prompt) in enumerate(zip(steps, prompts)):
        input(f"{i+1}/7 {prompt}")
        ser.write((cmd + '\r\n').encode())
        time.sleep(1)
        print(ser.read(100).decode())

    ser.close()
    print("Готово!")

if __name__ == "__main__":
    simple_calibrate()
