import serial
import time
import os
import subprocess
import math

try:
    import RPi.GPIO as GPIO
    RASPBERRY_PI = True
except ImportError:
    RASPBERRY_PI = False
    print("Предупреждение: RPi.GPIO не доступен")

class CableAnalyzer:
    def __init__(self):
        self.ser = None

    def send_command(self, command, wait_time=0.5):
        print(f"Отправка команды: {command}")
        try:
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            
            self.ser.write((command + '\r\n').encode())
            time.sleep(wait_time)
            
            response = b''
            start_time = time.time()
            while time.time() - start_time < wait_time:
                if self.ser.in_waiting > 0:
                    response += self.ser.read(self.ser.in_waiting)
                time.sleep(0.01)
            
            return response.decode('ascii', errors='ignore').strip()
            
        except Exception as e:
            print(f"Ошибка при отправке команды: {e}")
            return ""

    def setup_nanovna(self, start_freq=1e6, stop_freq=300e6, points=201):
        print("Настройка NanoVNA для измерения кабеля...")
        test_response = self.send_command("info", 1)
        if not test_response or "ch>" not in test_response:
            print("Ошибка: NanoVNA не отвечает")
            return False
        commands = [
            f"sweep {int(start_freq)} {int(stop_freq)} {points}",
            "pause",
        ]
        for cmd in commands:
            response = self.send_command(cmd, 0.5)
            if response:
                print(f"Ответ: {response}")
        
        time.sleep(1)
        return True

    def get_s11_data(self):
        print("Получение данных S11...")
        self.send_command("resume", 2)
        freq_data = self.send_command("frequencies", 1)
        s11_data = self.send_command("data 0", 1)
        return freq_data, s11_data

    def parse_frequency_data(self, data):
        frequencies = []
        if not data:
            return frequencies
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

    def parse_s11_data(self, data):
        s11_points = []
        if not data:
            return s11_points
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

    def calculate_vswr(self, s11_points):
        vswr_values = []
        for real, imag in s11_points:
            magnitude = math.sqrt(real**2 + imag**2)
            if magnitude < 1:
                vswr = (1 + magnitude) / (1 - magnitude)
            else:
                vswr = 100
            vswr_values.append(vswr)
        return vswr_values

    def calculate_phase(self, s11_points):
        phases = []
        for real, imag in s11_points:
            phase = math.atan2(imag, real)
            phases.append(phase)
        return phases

    def find_peaks_simple(self, data, min_distance=5):
        peaks = []
        for i in range(min_distance, len(data) - min_distance):
            if (data[i] == max(data[i-min_distance:i+min_distance+1])):
                peaks.append(i)
        return peaks

    def find_cable_length(self, frequencies, phases, vswr_values, vf=0.66):
        if len(frequencies) < 10:
            print("Недостаточно данных для анализа")
            return None, None, None, None, None
        
        try:
            # Ищем минимумы в КСВ (используем обратные значения)
            inverse_vswr = [-v for v in vswr_values]
            peaks = self.find_peaks_simple(inverse_vswr, min_distance=10)
            
            if len(peaks) < 2:
                print("Не удалось найти резонансы, использую фазовый метод")
                # Простой фазовый метод
                phase_diff = phases[-1] - phases[0]
                freq_diff = frequencies[-1] - frequencies[0]
                if freq_diff > 0:
                    phase_slope = phase_diff / freq_diff
                    c = 3e8
                    electrical_length = -phase_slope * c / (4 * math.pi * vf)
                    return electrical_length, electrical_length, freq_diff/10, frequencies[0], frequencies[-1]
                return None, None, None, None, None
            
            # Берем первые два пика
            peak1_idx = peaks[0]
            peak2_idx = peaks[1]
            
            freq1 = frequencies[peak1_idx]
            freq2 = frequencies[peak2_idx]
            
            delta_f = abs(freq2 - freq1)
            
            if delta_f == 0:
                print("Нулевая разность частот")
                return None, None, None, None, None
                
            c = 3e8
            cable_length = c / (2 * delta_f * vf)
            
            # Фазовый метод как проверка
            phase_slope = (phases[-1] - phases[0]) / (frequencies[-1] - frequencies[0])
            electrical_length = -phase_slope * c / (4 * math.pi * vf)
            
            return cable_length, electrical_length, delta_f, freq1, freq2
            
        except Exception as e:
            print(f"Ошибка при расчете длины кабеля: {e}")
            return None, None, None, None, None

    def measure_cable(self):
        if not self.setup_nanovna(start_freq=1e6, stop_freq=500e6, points=101):
            return
        
        freq_data, s11_data = self.get_s11_data()
        if not freq_data or not s11_data:
            print("Не удалось получить данные от NanoVNA")
            return
        
        frequencies = self.parse_frequency_data(freq_data)
        s11_points = self.parse_s11_data(s11_data)
        
        if len(frequencies) < 10 or len(s11_points) < 10:
            print("Недостаточно данных для анализа")
            return
        
        phases = self.calculate_phase(s11_points)
        vswr_values = self.calculate_vswr(s11_points)
        
        cable_types = {
            "RG-58": 0.66,
            "RG-174": 0.66,
            "RG-213": 0.66,
            "LMR-400": 0.85,
            "Коаксиал с полиэтиленом": 0.66,
            "Коаксиал с тефлоном": 0.70,
        }
            
        print("\n" + "="*60)
        print("РЕЗУЛЬТАТЫ ИЗМЕРЕНИЯ КАБЕЛЯ")
        print("="*60)
        
        results = {}
        for cable_type, vf in cable_types.items():
            length, _, delta_f, freq1, freq2 = self.find_cable_length(
                frequencies, phases, vswr_values, vf)
            if length:
                results[cable_type] = length
                print(f"{cable_type:30} (VF={vf}): {length:.2f} м")
        
        # Основной результат
        vf = 0.66
        cable_length, electrical_length, delta_f, freq1, freq2 = self.find_cable_length(
            frequencies, phases, vswr_values, vf)
        
        if cable_length:
            self.print_detailed_results(cable_length, delta_f, frequencies, vswr_values)
            self.save_results(frequencies, s11_points, cable_length, results)
        else:
            print("Не удалось определить длину кабеля")

    def print_detailed_results(self, cable_length, delta_f, frequencies, vswr_values):
        print(f"\nОСНОВНЫЕ РЕЗУЛЬТАТЫ:")
        print(f"Разность частот между резонансами: {delta_f/1e6:.2f} МГц")
        print(f"Расчетная длина кабеля: {cable_length:.3f} метров")
        print(f"В сантиметрах: {cable_length * 100:.1f} см")
        
        print(f"\nДИАПАЗОН ИЗМЕРЕНИЙ:")
        print(f"Начальная частота: {frequencies[0]/1e6:.1f} МГц")
        print(f"Конечная частота: {frequencies[-1]/1e6:.1f} МГц")
        print(f"Количество точек: {len(frequencies)}")
        
        print(f"\nКАЧЕСТВО КАБЕЛЯ:")
        avg_vswr = sum(vswr_values) / len(vswr_values)
        min_vswr = min(vswr_values)
        max_vswr = max(vswr_values)
        print(f"Средний КСВ: {avg_vswr:.2f}")
        print(f"Минимальный КСВ: {min_vswr:.2f}")
        print(f"Максимальный КСВ: {max_vswr:.2f}")
        
        if avg_vswr < 1.5:
            print("Оценка: Отличное качество кабеля")
        elif avg_vswr < 2.0:
            print("Оценка: Хорошее качество кабеля")
        else:
            print("Оценка: Проверьте соединения и кабель")

    def save_results(self, frequencies, s11_points, cable_length, results):
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"cable_results_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("Результаты измерения кабеля NanoVNA\n")
                f.write(f"Время: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Длина кабеля: {cable_length:.3f} м\n\n")
                
                f.write("Результаты для разных кабелей:\n")
                for cable_type, length in results.items():
                    f.write(f"{cable_type}: {length:.3f} м\n")
                
                f.write("\nИзмеренные данные:\n")
                f.write("Частота(МГц)\tReal\tImag\n")
                for i, (freq, point) in enumerate(zip(frequencies, s11_points)):
                    if i < len(s11_points):
                        f.write(f"{freq/1e6:.1f}\t{point[0]:.6f}\t{point[1]:.6f}\n")
            
            print(f"\nРезультаты сохранены в: {filename}")
            
        except Exception as e:
            print(f"Ошибка сохранения: {e}")

    def run(self):
        try:
            self.ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
            time.sleep(2)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            print("Подключение к NanoVNA установлено")
            self.measure_cable()
            
        except serial.SerialException as e:
            print(f"Ошибка порта: {e}")
        except KeyboardInterrupt:
            print("\nИзмерение прервано")
        except Exception as e:
            print(f"Ошибка: {e}")
        finally:
            if self.ser and self.ser.is_open:
                self.ser.close()
                print("Порт закрыт")

if __name__ == "__main__":
    analyzer = CableAnalyzer()
    analyzer.run()
