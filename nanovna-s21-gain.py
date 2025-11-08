import serial
import matplotlib.pyplot as plt
import numpy as np
import time

def send_command(ser, command, wait_time=0.5):
    print(f"Отправка команды: {command}")
    ser.write((command + '\r\n').encode())
    time.sleep(wait_time)
    
    response = b''
    start_time = time.time()
    while time.time() - start_time < wait_time:
        if ser.in_waiting > 0:
            response += ser.read(ser.in_waiting)
        time.sleep(0.01)
    
    return response.decode('ascii', errors='ignore')

def setup_nanovna(ser, cal_slot=0):
    print("Настройка NanoVNA...")
    commands = [
        f"cal load {cal_slot}",
        "sweep 30000000 1500000000 101",
        "pause",
    ]
    
    for cmd in commands:
        response = send_command(ser, cmd, 0.5)
        if response:
            response_clean = response.replace('ch>', '').strip()
            if response_clean:
                print(f"Ответ на {cmd}: {response_clean}")
    
    # Проверяем статус калибровки
    cal_status = send_command(ser, "cal", 0.5)
    if cal_status:
        print(f"Статус калибровки: {cal_status}")
    
    time.sleep(1)

def get_nanovna_data(ser):
    print("Получение данных S21...")
    
    # Запускаем одно сканирование
    send_command(ser, "resume", 0.5)
    time.sleep(2)  # Ждем завершения сканирования
    
    # Получаем данные частот
    freq_data = send_command(ser, "frequencies", 1)
    print(f"Получено данных частот: {len(freq_data)} байт")
    
    # Получаем данные S21
    s21_data = send_command(ser, "data 1", 1)  # S21 - transmission
    print(f"Получено данных S21: {len(s21_data)} байт")
    
    return freq_data, s21_data

def parse_frequency_data(data):
    frequencies = []
    lines = data.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if line and not line.startswith('ch>'):
            try:
                # Частоты могут быть в одной строке через пробелы
                parts = line.split()
                for part in parts:
                    freq = float(part)
                    frequencies.append(freq)
            except ValueError:
                continue
    
    return frequencies

def parse_s21_data(data):
    s21_points = []
    lines = data.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if line and not line.startswith('ch>'):
            try:
                # Данные S21 в формате: real imag
                parts = line.split()
                if len(parts) >= 2:
                    real = float(parts[0])
                    imag = float(parts[1])
                    s21_points.append((real, imag))
            except ValueError:
                continue
    
    return s21_points

def calculate_s21_db(s21_points):
    s21_db = []
    for real, imag in s21_points:
        magnitude = np.sqrt(real**2 + imag**2)
        if magnitude > 0:
            db = 20 * np.log10(magnitude)
        else:
            db = -120  # Минимальное значение
        s21_db.append(db)
    return s21_db

def plot_filter_response(frequencies, s21_db):
    if not frequencies or not s21_db:
        print("Недостаточно данных для построения графика")
        return
    
    # Обрезаем до минимальной длины
    min_len = min(len(frequencies), len(s21_db))
    frequencies = frequencies[:min_len]
    s21_db = s21_db[:min_len]
    
    # Переводим частоты в МГц
    frequencies_mhz = [f / 1e6 for f in frequencies]
    
    plt.figure(figsize=(12, 8))
    plt.plot(frequencies_mhz, s21_db, 'b-', linewidth=2, label='S21 (Transmission)')
    
    # Настройка графика
    plt.title('АЧХ режекторного FM фильтра\nNanoVNA-H4 (с калибровкой)', fontsize=14, fontweight='bold')
    plt.xlabel('Частота (МГц)', fontsize=12)
    plt.ylabel('S21 (дБ)', fontsize=12)
    plt.grid(True, alpha=0.3)
    
    # Отмечаем FM диапазон
    fm_start, fm_end = 87.5, 108
    plt.axvspan(fm_start, fm_end, alpha=0.2, color='red', label='FM диапазон')
    plt.axvline(fm_start, color='red', linestyle='--', alpha=0.7)
    plt.axvline(fm_end, color='red', linestyle='--', alpha=0.7)
    
    # Находим и отмечаем режекцию
    min_db_index = np.argmin(s21_db)
    min_freq = frequencies_mhz[min_db_index]
    min_db = s21_db[min_db_index]
    
    plt.plot(min_freq, min_db, 'ro', markersize=8, 
             label=f'Режекция: {min_freq:.1f} МГц, {min_db:.1f} дБ')
    
    plt.xlim(min(frequencies_mhz), max(frequencies_mhz))
    plt.ylim(min(s21_db) - 5, max(s21_db) + 5)
    
    # Логарифмическая шкала по частоте
    plt.xscale('log')
    plt.legend(fontsize=10)
    plt.tight_layout()
    plt.show()
    
    # Вывод результатов
    print(f"\n=== РЕЗУЛЬТАТЫ ИЗМЕРЕНИЯ ===")
    print(f"Диапазон: {min(frequencies_mhz):.1f} - {max(frequencies_mhz):.1f} МГц")
    print(f"Точка режекции: {min_freq:.2f} МГц")
    print(f"Глубина режекции: {min_db:.1f} дБ")
    print(f"FM диапазон: {fm_start} - {fm_end} МГц")
    
    # Проверяем эффективность режекции в FM диапазоне
    fm_indices = [i for i, f in enumerate(frequencies_mhz) if fm_start <= f <= fm_end]
    if fm_indices:
        fm_attenuation = [s21_db[i] for i in fm_indices]
        avg_fm_attenuation = np.mean(fm_attenuation)
        print(f"Среднее подавление в FM диапазоне: {avg_fm_attenuation:.1f} дБ")

def main():
    ser = None
    try:
        print("=" * 50)
        print("Подключение к NanoVNA-H4 на COM3...")
        print("=" * 50)
        
        ser = serial.Serial(
            port='COM3',
            baudrate=115200,
            timeout=2,
            write_timeout=2,
        )
        
        # Ждем инициализации
        time.sleep(2)
        
        # Настройка с загрузкой калибровки из слота 0
        setup_nanovna(ser, cal_slot=0)
        
        freq_data, s21_data = get_nanovna_data(ser)
        
        frequencies = parse_frequency_data(freq_data)
        s21_points = parse_s21_data(s21_data)
        s21_db = calculate_s21_db(s21_points)
        
        print(f"\nОбработано {len(frequencies)} частот и {len(s21_points)} точек S21")
        
        if frequencies and s21_db:
            plot_filter_response(frequencies, s21_db)
        else:
            print("Не удалось получить данные для построения графика")
            
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if ser and ser.is_open:
            ser.close()
            print("\nСоединение закрыто")

if __name__ == "__main__":
    main()