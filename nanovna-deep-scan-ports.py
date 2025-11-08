import serial.tools.list_ports
import serial
import time
import threading
from datetime import datetime

class NanoVNAPortFinder:
    def __init__(self):
        self.found_devices = []
        self.test_results = {}
        
    def get_all_com_ports(self):
        """Получить список всех COM портов"""
        ports = serial.tools.list_ports.comports()
        port_info = []
        
        print("=" * 60)
        print("НАЙДЕННЫЕ COM ПОРТЫ:")
        print("=" * 60)
        
        for port in ports:
            info = {
                'device': port.device,
                'name': port.name,
                'description': port.description,
                'hwid': port.hwid,
                'vid': None,
                'pid': None,
                'manufacturer': getattr(port, 'manufacturer', 'N/A'),
                'product': getattr(port, 'product', 'N/A')
            }
            
            # Парсим VID и PID из HWID
            if 'VID' in port.hwid and 'PID' in port.hwid:
                try:
                    vid_start = port.hwid.index('VID_') + 4
                    pid_start = port.hwid.index('PID_') + 4
                    vid = port.hwid[vid_start:vid_start+4]
                    pid = port.hwid[pid_start:pid_start+4]
                    info['vid'] = vid
                    info['pid'] = pid
                except (ValueError, IndexError):
                    pass
            
            port_info.append(info)
            
            # Вывод информации о порте
            print(f"Порт: {port.device}")
            print(f"  Описание: {port.description}")
            print(f"  Производитель: {info['manufacturer']}")
            print(f"  Продукт: {info['product']}")
            if info['vid'] and info['pid']:
                print(f"  VID:PID: {info['vid']}:{info['pid']}")
            print(f"  HWID: {port.hwid}")
            print("-" * 40)
        
        return port_info
    
    def test_nanovna_connection(self, port_info, baudrate=115200, timeout=2):
        """Тестирование подключения к порту для идентификации NanoVNA"""
        device = port_info['device']
        print(f"Тестирование порта {device}...")
        
        try:
            # Пробуем подключиться
            with serial.Serial(
                port=device,
                baudrate=baudrate,
                timeout=timeout,
                write_timeout=timeout
            ) as ser:
                
                # Даем время на инициализацию
                time.sleep(2)
                
                # Очищаем буфер
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                
                # Отправляем тестовые команды
                test_commands = [
                    b'\r\n',           # Пустая команда
                    b'help\r\n',       # Справка
                    b'version\r\n',    # Версия
                    b'info\r\n',       # Информация
                ]
                
                responses = []
                nanovna_indicators = []
                
                for cmd in test_commands:
                    ser.write(cmd)
                    time.sleep(0.5)
                    
                    response = b''
                    while ser.in_waiting > 0:
                        response += ser.read(ser.in_waiting)
                        time.sleep(0.1)
                    
                    if response:
                        response_text = response.decode('ascii', errors='ignore')
                        responses.append(response_text)
                        
                        # Проверяем признаки NanoVNA в ответе
                        nanovna_keywords = [
                            'nanovna', 'ch>', 'sweep', 'frequencies',
                            'version', 'NanoVNA', 'VNA'
                        ]
                        
                        for keyword in nanovna_keywords:
                            if keyword.lower() in response_text.lower():
                                nanovna_indicators.append(keyword)
                
                # Анализируем результаты
                result = {
                    'port': device,
                    'success': bool(responses),
                    'responses': responses,
                    'indicators': nanovna_indicators,
                    'is_nanovna': len(nanovna_indicators) >= 2,  # Минимум 2 признака
                    'confidence': len(nanovna_indicators),
                    'timestamp': datetime.now().strftime("%H:%M:%S")
                }
                
                return result
                
        except Exception as e:
            print(f"  Ошибка: {e}")
            return {
                'port': device,
                'success': False,
                'error': str(e),
                'is_nanovna': False,
                'confidence': 0,
                'timestamp': datetime.now().strftime("%H:%M:%S")
            }
    
    def check_vid_pid_nanovna(self, port_info):
        """Проверка по VID/PID - характерные для NanoVNA"""
        # Известные VID:PID для NanoVNA и CH340 (USB-UART чип)
        nanovna_vid_pid = [
            ('1a86', '7523'),  # CH340 - самый распространенный
            ('0403', '6001'),  # FT232 - иногда используется
            ('10c4', 'ea60'),  # CP210x - реже
        ]
        
        if port_info['vid'] and port_info['pid']:
            for vid, pid in nanovna_vid_pid:
                if (port_info['vid'].lower() == vid and 
                    port_info['pid'].lower() == pid):
                    return True
        return False
    
    def scan_for_nanovna(self, baudrates=[115200, 9600, 57600]):
        """Основная функция сканирования"""
        print("ЗАПУСК СКАНИРОВАНИЯ NANOVNA...")
        print("=" * 60)
        
        # Получаем все порты
        ports = self.get_all_com_ports()
        
        if not ports:
            print("COM порты не найдены!")
            return []
        
        print(f"\nТЕСТИРОВАНИЕ {len(ports)} ПОРТОВ...")
        print("=" * 60)
        
        candidate_ports = []
        
        for port_info in ports:
            # Сначала проверяем по VID/PID
            is_likely_nanovna = self.check_vid_pid_nanovna(port_info)
            
            if is_likely_nanovna:
                print(f"🔍 {port_info['device']} - возможный NanoVNA (по VID/PID)")
            
            # Тестируем подключение на разных скоростях
            for baudrate in baudrates:
                print(f"  Скорость {baudrate}...")
                result = self.test_nanovna_connection(port_info, baudrate)
                
                if result['success']:
                    port_info['test_result'] = result
                    port_info['baudrate'] = baudrate
                    
                    if result['is_nanovna'] or is_likely_nanovna:
                        candidate_ports.append(port_info)
                    
                    # Вывод результатов теста
                    status = "✅ NanoVNA обнаружен!" if result['is_nanovna'] else "❌ Не NanoVNA"
                    print(f"  Результат: {status}")
                    
                    if result['indicators']:
                        print(f"  Признаки: {', '.join(result['indicators'])}")
                    
                    break  # Переходим к следующему порту
                else:
                    print(f"  Результат: Ошибка подключения")
        
        return candidate_ports
    
    def print_results(self, candidate_ports):
        """Вывод результатов сканирования"""
        print("\n" + "=" * 60)
        print("РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
        print("=" * 60)
        
        if not candidate_ports:
            print("❌ NanoVNA не найден!")
            print("\nВозможные причины:")
            print("1. Устройство не подключено")
            print("2. Драйверы CH340 не установлены")
            print("3. Устройство занято другой программой")
            print("4. Проблемы с кабелем USB")
            return
        
        print(f"✅ Найдено {len(candidate_ports)} возможных NanoVNA:")
        
        for i, port_info in enumerate(candidate_ports, 1):
            print(f"\n{i}. {port_info['device']}")
            print(f"   Описание: {port_info['description']}")
            if port_info['vid'] and port_info['pid']:
                print(f"   VID:PID: {port_info['vid']}:{port_info['pid']}")
            if 'baudrate' in port_info:
                print(f"   Скорость: {port_info['baudrate']}")
            if 'test_result' in port_info:
                result = port_info['test_result']
                print(f"   Уверенность: {result['confidence']}/5")
                if result['indicators']:
                    print(f"   Обнаружены признаки: {', '.join(result['indicators'])}")
        
        print(f"\n🎯 РЕКОМЕНДУЕМЫЙ ПОРТ: {candidate_ports[0]['device']}")
    
    def continuous_monitoring(self, interval=5):
        """Непрерывный мониторинг портов"""
        print("🚀 ЗАПУСК НЕПРЕРЫВНОГО МОНИТОРИНГА")
        print("Нажмите Ctrl+C для остановки")
        
        known_ports = set()
        
        try:
            while True:
                current_ports = {port.device for port in serial.tools.list_ports.comports()}
                
                # Новые порты
                new_ports = current_ports - known_ports
                # Исчезнувшие порты
                removed_ports = known_ports - current_ports
                
                if new_ports:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Новые порты: {', '.join(new_ports)}")
                    # Проверяем новые порты на наличие NanoVNA
                    for port_device in new_ports:
                        port_info = {'device': port_device, 'description': 'Новое устройство'}
                        result = self.test_nanovna_connection(port_info)
                        if result['is_nanovna']:
                            print(f"🎉 ОБНАРУЖЕН NANOVNA НА {port_device}!")
                
                if removed_ports:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Удаленные порты: {', '.join(removed_ports)}")
                
                known_ports = current_ports
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\nМониторинг остановлен")

def main():
    """Основная функция"""
    finder = NanoVNAPortFinder()
    
    print("NANOVNA PORT FINDER FOR WINDOWS")
    print("Версия 1.0")
    print("=" * 60)
    
    while True:
        print("\nВыберите действие:")
        print("1 - Быстрое сканирование")
        print("2 - Подробное сканирование")
        print("3 - Непрерывный мониторинг")
        print("4 - Список всех COM портов")
        print("5 - Выход")
        
        choice = input("\nВаш выбор (1-5): ").strip()
        
        if choice == '1':
            # Быстрое сканирование на стандартной скорости
            candidates = finder.scan_for_nanovna(baudrates=[115200])
            finder.print_results(candidates)
            
        elif choice == '2':
            # Подробное сканирование на всех скоростях
            candidates = finder.scan_for_nanovna(baudrates=[115200, 9600, 57600, 38400])
            finder.print_results(candidates)
            
        elif choice == '3':
            # Непрерывный мониторинг
            finder.continuous_monitoring()
            
        elif choice == '4':
            # Просто список портов
            finder.get_all_com_ports()
            
        elif choice == '5':
            print("Выход...")
            break
            
        else:
            print("Неверный выбор!")

if __name__ == "__main__":
    main()