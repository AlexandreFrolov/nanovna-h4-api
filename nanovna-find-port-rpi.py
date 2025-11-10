import serial.tools.list_ports
import serial
import time
import subprocess
import os

def find_nanovna_auto():
    print("Автопоиск NanoVNA на Raspberry Pi...")

    # Проверяем доступные порты
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("Не найдено последовательных портов")
        return None

    print(f"Найдено портов: {len(ports)}")

    for port in ports:
        print(f"Проверка порта: {port.device} - {port.description}")

        # Пропускаем порты, которые вряд ли будут NanoVNA
        if 'ttyAMA' in port.device or 'ttyS' in port.device:
            print(f"Пропуск системного порта: {port.device}")
            continue

        try:
            with serial.Serial(port.device, 115200, timeout=1) as ser:
                print(f"Подключение к {port.device}...")
                time.sleep(2)  # Даем время для инициализации

                # Очищаем буферы
                ser.reset_input_buffer()
                ser.reset_output_buffer()

                # Отправляем команду
                ser.write(b'version\r\n')
                time.sleep(0.5)

                # Читаем ответ
                response = ser.read(100).decode('ascii', errors='ignore')
                print(f"  Ответ: {response.strip()}")

                # Проверяем признаки NanoVNA
                if any(keyword in response.lower() for keyword in ['nanovna', 'ch>', 'version']):
                    return port.device

        except serial.SerialException as e:
            print(f"Ошибка подключения к {port.device}: {e}")
            continue
        except Exception as e:
            print(f"Общая ошибка на {port.device}: {e}")
            continue
    return None

def check_usb_permissions():
    print("Проверка прав доступа...")
    # Проверяем, есть ли пользователь в группе dialout
    try:
        groups = subprocess.check_output(['groups'], text=True).strip().split()
        if 'dialout' in groups:
            print("Пользователь в группе dialout")
        else:
            print("Пользователь не в группе dialout. Добавьте: sudo usermod -a -G dialout $USER")
    except:
        print("Не удалось проверить группы пользователя")

def list_available_ports():
    print("\nДоступные последовательные порты:")
    ports = list(serial.tools.list_ports.comports())
    for i, port in enumerate(ports):
        print(f"  {i+1}. {port.device} - {port.description}")
    return ports

if __name__ == "__main__":
    check_usb_permissions()
    list_available_ports()
    port = find_nanovna_auto()

    if port:
        print(f"\nНайден NanoVNA на порту: {port}")
    else:
        print(f"\nNanoVNA не найден")
