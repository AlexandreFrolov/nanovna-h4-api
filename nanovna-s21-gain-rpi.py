import serial
import matplotlib
matplotlib.use('Agg')  # Используем бэкенд без GUI
import matplotlib.pyplot as plt
import numpy as np
import time
import os
from datetime import datetime

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
        "sweep 30000000 250000000 101",
        "pause",
    ]
    
    for cmd in commands:
        response = send_command(ser, cmd, 0.5)
        if response:
            response_clean = response.replace('ch>', '').strip()
            if response_clean:
                print(f"Ответ на {cmd}: {response_clean}")
    
    cal_status = send_command(ser, "cal", 0.5)
    if cal_status:
        print(f"Статус калибровки: {cal_status}")
    
    time.sleep(1)

def get_nanovna_data(ser):
    print("Получение данных S21...")
    send_command(ser, "resume", 2)
    freq_data = send_command(ser, "frequencies", 1)
    print(f"Получено данных частот: {len(freq_data)} байт")
    s21_data = send_command(ser, "data 1", 1) 
    print(f"Получено данных S21: {len(s21_data)} байт")
    return freq_data, s21_data

def parse_frequency_data(data):
    frequencies = []
    lines = data.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if line and not line.startswith('ch>'):
            try:
                parts = line.split()
                for part in parts:
                    freq = float(part)
                    frequencies.append(freq)
            except ValueError:
                continue
    
    return frequencies

def parse_s21_data(data):
    """Парсинг данных S21 (комплексные числа)"""
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

def save_filter_response(frequencies, s21_db, filename=None):
    if not frequencies or not s21_db:
        print("Недостаточно данных для построения графика")
        return None
    
    min_len = min(len(frequencies), len(s21_db))
    frequencies = frequencies[:min_len]
    s21_db = s21_db[:min_len]
    
    frequencies_mhz = [f / 1e6 for f in frequencies]
    
    # Создаем папку для результатов если её нет
    results_dir = "/home/pi/nanovna_results"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    
    # Генерируем имя файла с временной меткой
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"filter_response_{timestamp}.png"
    
    filepath = os.path.join(results_dir, filename)
    
    plt.figure(figsize=(12, 8))
    plt.plot(frequencies_mhz, s21_db, 'b-', linewidth=2, label='S21 (Transmission)')
    
    plt.title('АЧХ режекторного FM фильтра\nNanoVNA-H4 (с калибровкой)', fontsize=14, fontweight='bold')
    plt.xlabel('Частота (МГц)', fontsize=12)
    plt.ylabel('S21 (дБ)', fontsize=12)
    plt.grid(True, alpha=0.3)
    
    fm_start, fm_end = 87.5, 108
    plt.axvspan(fm_start, fm_end, alpha=0.2, color='red', label='FM диапазон')
    plt.axvline(fm_start, color='red', linestyle='--', alpha=0.7)
    plt.axvline(fm_end, color='red', linestyle='--', alpha=0.7)
    
    min_db_index = np.argmin(s21_db)
    min_freq = frequencies_mhz[min_db_index]
    min_db = s21_db[min_db_index]
    
    plt.plot(min_freq, min_db, 'ro', markersize=8, 
             label=f'Подавление: {min_freq:.1f} МГц, {min_db:.1f} дБ')
    
    plt.xlim(min(frequencies_mhz), max(frequencies_mhz))
    plt.ylim(min(s21_db) - 5, max(s21_db) + 5)
    
    plt.xticks(rotation=45)
    
    from matplotlib.ticker import FuncFormatter
    def format_freq(x, pos):
        if x >= 1000:
            return f'{x/1000:.0f}00'
        else:
            return f'{x:.0f}'
    
    plt.gca().xaxis.set_major_formatter(FuncFormatter(format_freq))
    
    plt.legend(fontsize=10)
    plt.tight_layout()
    
    # Сохраняем график
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"График сохранен как: {filepath}")
    
    # Сохраняем данные в текстовый файл
    data_filename = filename.replace('.png', '.txt')
    data_filepath = os.path.join(results_dir, data_filename)
    
    with open(data_filepath, 'w') as f:
        f.write("Частота (МГц)\tS21 (дБ)\n")
        for freq, db in zip(frequencies_mhz, s21_db):
            f.write(f"{freq:.3f}\t{db:.3f}\n")
    
    print(f"Данные сохранены как: {data_filepath}")
    
    print(f"\n=== РЕЗУЛЬТАТЫ ИЗМЕРЕНИЯ ===")
    print(f"Диапазон: {min(frequencies_mhz):.1f} - {max(frequencies_mhz):.1f} МГц")
    print(f"Точка подавления: {min_freq:.2f} МГц")
    print(f"Глубина подавления: {min_db:.1f} дБ")
    print(f"FM диапазон: {fm_start} - {fm_end} МГц")
    
    # Проверяем эффективность подавления в FM диапазоне
    fm_indices = [i for i, f in enumerate(frequencies_mhz) if fm_start <= f <= fm_end]
    if fm_indices:
        fm_attenuation = [s21_db[i] for i in fm_indices]
        avg_fm_attenuation = np.mean(fm_attenuation)
        print(f"Среднее подавление в FM диапазоне: {avg_fm_attenuation:.1f} дБ")
    
    return filepath

def find_nanovna_port():
    """Автоматический поиск порта NanoVNA"""
    possible_ports = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyACM0', '/dev/ttyACM1']
    
    for port in possible_ports:
        if os.path.exists(port):
            try:
                print(f"Проверка порта {port}...")
                ser = serial.Serial(port, 115200, timeout=1)
                time.sleep(2)
                # Отправляем тестовую команду
                response = send_command(ser, "info", 0.5)
                if response and "NanoVNA" in response:
                    print(f"Найден NanoVNA на порту {port}")
                    return ser
                else:
                    ser.close()
            except Exception as e:
                print(f"Ошибка при проверке порта {port}: {e}")
                continue
    
    return None

def main():
    ser = None
    try:
        print("Поиск NanoVNA-H4...")
        
        # Автоматический поиск порта
        ser = find_nanovna_port()
        
        if ser is None:
            # Ручной ввод порта
            port = input("Введите порт вручную (например /dev/ttyUSB0): ")
            ser = serial.Serial(
                port=port,
                baudrate=115200,
                timeout=2,
                write_timeout=2,
            )
            time.sleep(2)
        
        print("Подключение установлено")
        
        setup_nanovna(ser, cal_slot=0)
        freq_data, s21_data = get_nanovna_data(ser)
        
        frequencies = parse_frequency_data(freq_data)
        s21_points = parse_s21_data(s21_data)
        s21_db = calculate_s21_db(s21_points)
        
        print(f"\nОбработано {len(frequencies)} частот и {len(s21_points)} точек S21")
        
        if frequencies and s21_db:
            plot_filename = save_filter_response(frequencies, s21_db)
            print(f"\nИзмерение завершено. Результаты сохранены в: {plot_filename}")
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
