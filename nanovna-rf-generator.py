import serial
import time

def ultra_simple_generator(port='COM3', frequency_hz=1000000):
    """Ультра-простая версия - только одна команда в цикле"""
    ser = serial.Serial(port, 115200, timeout=0.1)
    time.sleep(2)
    
    freq_khz = frequency_hz // 1000
    command = f"generator {freq_khz}\n".encode()
    
    print("Ультра-простой режим...")
    
    try:
        while True:
            ser.write(command)
            time.sleep(0.08)  # Оптимальная пауза
    except KeyboardInterrupt:
        print("\nОстановка")
    finally:
        ser.write(b"generator 0\n")
        ser.close()

if __name__ == "__main__":
    ultra_simple_generator('COM3', 1000000)