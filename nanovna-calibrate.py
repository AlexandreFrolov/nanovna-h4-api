import serial
import time

# === Настройки соединения ===
PORT = "COM3"        # Порт NanoVNA (проверьте в диспетчере устройств)
BAUDRATE = 115200

def send_command(ser, cmd, wait=0.2):
    """Отправка команды NanoVNA и чтение ответа"""
    ser.write((cmd + '\r\n').encode('utf-8'))
    time.sleep(wait)
    return ser.read_all().decode('utf-8', errors='ignore').strip()

def calibrate(ser):
    print("\n🔧 Начало процедуры калибровки NanoVNA-H4")

    # === Настройка диапазона сканирования ===
    start_freq = 50_000        # 50 кГц
    stop_freq = 1_500_000_000  # 1500 МГц
    points = 201               # Количество точек (можно 101–401)

    print(f"→ Установка диапазона: {start_freq/1e3:.1f} кГц – {stop_freq/1e6:.1f} МГц, {points} точек")
    send_command(ser, f"sweep {start_freq} {stop_freq} {points}")
    print(send_command(ser, "frequencies")[:200] + "...")

    # === Последовательность калибровки ===
    print("→ Сброс текущей калибровки")
    print(send_command(ser, "cal reset"))

    input("\nПодключите OPEN (открытый порт CH0) и нажмите Enter...")
    print(send_command(ser, "cal open"))

    input("Подключите SHORT (замыкание на CH0) и нажмите Enter...")
    print(send_command(ser, "cal short"))

    input("Подключите LOAD (50Ω) к CH0 и нажмите Enter...")
    print(send_command(ser, "cal load"))

    input("Соедините CH0 и CH1 (THRU) и нажмите Enter...")
    print(send_command(ser, "cal thru"))

    # === Завершение калибровки ===
    print("\n→ Завершение и расчёт калибровки")
    print(send_command(ser, "cal done"))

    # === Сохранение калибровки ===
    print("→ Сохранение в слот 0")
    print(send_command(ser, "save 0"))

    print("\n✅ Калибровка успешно выполнена и сохранена (слот 0)")

def main():
    print(f"Подключение к NanoVNA-H4 через {PORT}...")
    with serial.Serial(PORT, BAUDRATE, timeout=0.5) as ser:
        time.sleep(1.0)
        version = send_command(ser, "version")
        print("Версия прошивки:", version or "Нет ответа")

        calibrate(ser)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nОперация прервана пользователем.")
    except serial.SerialException as e:
        print(f"Ошибка доступа к {PORT}: {e}")
