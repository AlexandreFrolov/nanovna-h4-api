import serial.tools.list_ports
import serial
import time

def find_nanovna_auto():
    print("Автопоиск NanoVNA...")
    for port in serial.tools.list_ports.comports():
        try:
            with serial.Serial(port.device, 115200, timeout=1) as ser:
                time.sleep(2)
                ser.write(b'version\r\n')
                time.sleep(0.5)
                response = ser.read(100).decode('ascii', errors='ignore')
                
                if 'nanovna' in response.lower() or 'ch>' in response:
                    print(f"Найден по ответу: {port.device}")
                    return port.device
                    
        except:
            continue
    print("NanoVNA не найден!")
    return None

def get_nanovna_port():
    port = find_nanovna_auto()
    if port:
        print(f"Используется порт: {port}")
    else:
        print("NanoVNA не найден!")
    return port

if __name__ == "__main__":
    port = get_nanovna_port()
    if port:
        print(f"Подключение к {port}")
    else:
        print("Проверьте подключение NanoVNA")