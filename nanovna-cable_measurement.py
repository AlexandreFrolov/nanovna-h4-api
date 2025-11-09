import serial
import matplotlib.pyplot as plt
import numpy as np
import time
from scipy.signal import find_peaks
import math

def send_command(ser, command, wait_time=0.5):
    """Отправка команды и получение ответа"""
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

def setup_nanovna_for_cable_measurement(ser, start_freq=1e6, stop_freq=300e6, points=201):
    """Настройка NanoVNA для измерения кабеля"""
    print("Настройка NanoVNA для измерения кабеля...")
    
    commands = [
        f"sweep {int(start_freq)} {int(stop_freq)} {points}",
        "pause",
    ]
    
    for cmd in commands:
        response = send_command(ser, cmd, 0.5)
        if response:
            print(f"Ответ на {cmd}: {response.strip()}")
    
    time.sleep(1)

def get_s11_data(ser):
    """Получение данных S11 (коэффициент отражения)"""
    print("Получение данных S11...")
    
    # Запускаем сканирование
    send_command(ser, "resume", 0.5)
    time.sleep(2)
    
    # Получаем данные частот
    freq_data = send_command(ser, "frequencies", 1)
    
    # Получаем данные S11
    s11_data = send_command(ser, "data 0", 1)  # S11 - reflection
    
    return freq_data, s11_data

def parse_frequency_data(data):
    """Парсинг данных частот"""
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

def parse_s11_data(data):
    """Парсинг данных S11 (комплексные числа)"""
    s11_points = []
    lines = data.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if line and not line.startswith('ch>'):
            try:
                parts = line.split()
                if len(parts) >= 2:
                    real = float(parts[0])
                    imag = float(parts[1])
                    s11_points.append((real, imag))
            except ValueError:
                continue
    
    return s11_points

def calculate_phase(s11_points):
    """Вычисление фазы S11 в радианах"""
    phases = []
    for real, imag in s11_points:
        phase = np.arctan2(imag, real)  # Фаза в радианах
        phases.append(phase)
    return phases

def calculate_vswr(s11_points):
    """Вычисление КСВ из S11"""
    vswr_values = []
    for real, imag in s11_points:
        magnitude = np.sqrt(real**2 + imag**2)
        if magnitude < 1:
            vswr = (1 + magnitude) / (1 - magnitude)
        else:
            vswr = 100  # Большое значение для плохого КСВ
        vswr_values.append(vswr)
    return vswr_values

def find_cable_length(frequencies, phases, vswr_values, vf=0.66):
    """
    Определение длины кабеля по фазовому сдвигу
    vf - коэффициент укорочения (velocity factor)
    """
    # Находим пики в КСВ (минимумы отражения)
    peaks, _ = find_peaks(-np.array(vswr_values), prominence=0.1)
    
    if len(peaks) < 2:
        print("Не удалось найти достаточное количество резонансов")
        return None, None
    
    # Берем первые два резонансных пика
    peak1_idx = peaks[0]
    peak2_idx = peaks[1]
    
    freq1 = frequencies[peak1_idx]
    freq2 = frequencies[peak2_idx]
    
    # Разность частот между соседними резонансами
    delta_f = abs(freq2 - freq1)
    
    # Длина кабеля: L = c / (2 * delta_f * vf)
    c = 3e8  # Скорость света м/с
    cable_length = c / (2 * delta_f * vf)
    
    # Альтернативный метод: по фазовому сдвигу
    phase_slope = np.polyfit(frequencies, phases, 1)[0]  # Наклон фазы
    electrical_length = -phase_slope * c / (4 * np.pi * vf)
    
    return cable_length, electrical_length, delta_f, freq1, freq2

def plot_cable_measurement(frequencies, phases, vswr_values, cable_length, delta_f):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    
    print(f"\n=== РЕЗУЛЬТАТЫ ИЗМЕРЕНИЯ КАБЕЛЯ ===")
    print(f"Разность частот между резонансами: {delta_f/1e6:.2f} МГц")
    print(f"Расчетная длина кабеля: {cable_length:.2f} метров")
    print(f"Длина кабеля в сантиметрах: {cable_length * 100:.1f} см")

    # График 1: КСВ
    frequencies_mhz = [f / 1e6 for f in frequencies]
    ax1.plot(frequencies_mhz, vswr_values, 'b-', linewidth=2, label='КСВ')
    ax1.set_title('КСВ кабеля', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Частота (МГц)', fontsize=12)
    ax1.set_ylabel('КСВ', fontsize=12)
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # График 2: Фаза
    phases_deg = [p * 180 / np.pi for p in phases]
    ax2.plot(frequencies_mhz, phases_deg, 'r-', linewidth=2, label='Фаза S11')
    ax2.set_title('Фаза коэффициента отражения', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Частота (МГц)', fontsize=12)
    ax2.set_ylabel('Фаза (градусы)', fontsize=12)
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    plt.tight_layout()
    plt.show()
    
def measure_cable_with_different_vf(ser):
    setup_nanovna_for_cable_measurement(ser, start_freq=1e6, stop_freq=500e6, points=501)
    
    # Получение данных
    freq_data, s11_data = get_s11_data(ser)
    frequencies = parse_frequency_data(freq_data)
    s11_points = parse_s11_data(s11_data)
    
    if not frequencies or not s11_points:
        print("Не удалось получить данные")
        return
    
    # Расчет параметров
    phases = calculate_phase(s11_points)
    vswr_values = calculate_vswr(s11_points)
    
    # Стандартные коэффициенты укорочения для разных кабелей
    cable_types = {
        "RG-58": 0.66,
        "RG-174": 0.66,
        "RG-213": 0.66,
        "LMR-400": 0.85,
        "Коаксиал с полиэтиленом": 0.66,
        "Коаксиал с тефлоном": 0.70,
        "Воздушный коаксиал": 0.80
    }
        
    print("\n=== РЕЗУЛЬТАТЫ ДЛЯ РАЗНЫХ ТИПОВ КАБЕЛЕЙ ===")
    for cable_type, vf in cable_types.items():
        length, _, delta_f, freq1, freq2 = find_cable_length(frequencies, phases, vswr_values, vf)
        if length:
            print(f"{cable_type} (VF={vf}): {length:.2f} м")
        

    # Используем средний коэффициент для построения графика
    vf = 0.66
    
    # Расчет длины с выбранным коэффициентом
    cable_length, electrical_length, delta_f, freq1, freq2 = find_cable_length(
        frequencies, phases, vswr_values, vf)
    
    if cable_length:
        plot_cable_measurement(frequencies, phases, vswr_values, cable_length, delta_f)
    else:
        print("Не удалось определить длину кабеля")

def main():
    ser = None
    try:
        print("Измерение длины кабеля с помощью NanoVNA")
        ser = serial.Serial(
            port='COM3',
            baudrate=115200,
            timeout=2,
            write_timeout=2,
        )
        time.sleep(2)
        measure_cable_with_different_vf(ser)
        
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if ser and ser.is_open:
            ser.close()

if __name__ == "__main__":
    main()