import serial.tools.list_ports
import serial
import time

def find_nanovna_auto():
    """Автоматическое определение порта NanoVNA"""
    
    # Характерные VID:PID для NanoVNA
    NANOVNA_VID_PID = [
        ('1a86', '7523'),  # CH340
        ('0403', '6001'),  # FT232
        ('10c4', 'ea60'),  # CP210x
    ]
    
    print("Автопоиск NanoVNA...")
    
    # Сначала ищем по VID:PID
    for port in serial.tools.list_ports.comports():
        if 'VID' in port.hwid and 'PID' in port.hwid:
            for vid, pid in NANOVNA_VID_PID:
                if f'VID_{vid}' in port.hwid and f'PID_{pid}' in port.hwid:
                    print(f"Найден по VID:PID: {port.device}")
                    return port.device
    
    # Если не нашли по VID:PID, тестируем все порты
    print("Поиск по тестированию портов...")
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

# Простая версия для использования в других программах
def get_nanovna_port():
    """Возвращает порт NanoVNA или None если не найден"""
    port = find_nanovna_auto()
    if port:
        print(f"✅ Используется порт: {port}")
    else:
        print("❌ NanoVNA не найден!")
    return port

if __name__ == "__main__":
    port = get_nanovna_port()
    if port:
        print(f"Подключение к {port}")
    else:
        print("Проверьте подключение NanoVNA")