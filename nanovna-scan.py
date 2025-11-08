import serial
import time

# Параметры соединения для Windows
PORT = "COM3"       # Укажите ваш реальный порт NanoVNA
BAUDRATE = 115200

def send_command(ser, cmd):
    """Отправка команды NanoVNA и чтение ответа"""
    ser.write((cmd + '\r\n').encode('utf-8'))
    time.sleep(0.1)
    response = ser.read_all().decode('utf-8', errors='ignore')
    return response.strip()

def main():
    with serial.Serial(PORT, BAUDRATE, timeout=0.5) as ser:
        print(f"Подключение к NanoVNA-H4 через {PORT}...")
        time.sleep(1.0)

        # Проверка связи
        print("Ответ на команду 'version':")
        version_info = send_command(ser, 'version')
        print(version_info or "Нет ответа.")

        # Настройка диапазона сканирования
        start_freq = 10000000   # 10 МГц
        stop_freq = 30000000    # 30 МГц
        points = 101

        send_command(ser, f'sweep {start_freq} {stop_freq} {points}')
        print(f'Диапазон установлен: {start_freq/1e6:.1f}–{stop_freq/1e6:.1f} МГц, {points} точек')

        # Основной цикл опроса
        while True:
            # Чтение данных S11 (реальная и мнимая части)
            response = send_command(ser, 'data 0')
            if response:
                print("Данные S11 (первые 200 символов):")
                print(response[:200] + '...')

            # Чтобы не перегружать порт
            time.sleep(2)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nОпрос завершён пользователем.")
    except serial.SerialException as e:
        print(f"Ошибка порта {PORT}: {e}")
