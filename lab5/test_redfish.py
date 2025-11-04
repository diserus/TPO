import requests
from requests.auth import HTTPBasicAuth
import time
import subprocess
import re
import pytest
import logging


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def redfish_session():
    session = requests.Session()
    session.auth = ('root', '0penBmc')
    session.verify = False
    session.headers.update({'Content-Type': 'application/json'})
    
    logger.info("Создана сессия Redfish")
    return session

@pytest.fixture(scope="session")
def base_url():
    return 'https://127.0.0.1:2443/redfish/v1/'


def red_auth(redfish_session, base_url):
    try:
        logger.info("Проверка аутентификации Redfish")
        response = redfish_session.get(base_url)
        logger.info(f"Статус аутентификации: {response.status_code}")
        return response.status_code
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка аутентификации: {e}")
        return None

def test_auth(redfish_session, base_url):
    assert red_auth(redfish_session, base_url) == 200

def info(redfish_session, base_url):
    try:
        logger.info("Получение информации о системе")
        response = redfish_session.get(base_url + 'Systems/system')
        
        if response.status_code != 200:
            logger.warning(f"Ошибка получения информации: {response.status_code}")
            return False
            
        data = response.json()
        has_status = 'Status' in data
        has_power_state = 'PowerState' in data
        
        logger.info(f"Информация о системе - Status: {has_status}, PowerState: {has_power_state}")
        return has_status and has_power_state
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка получения информации о системе: {e}")
        return False
    except ValueError as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
        return False

def test_info(redfish_session, base_url):
    assert info(redfish_session, base_url) == True


def power(redfish_session, base_url):
    try:
        logger.info("Проверка управления питанием")
        payload = {"ResetType": "On"}
        
        a_response = redfish_session.post(base_url + 'Systems/system/Actions/ComputerSystem.Reset', json=payload)
        logger.info(f"Статус POST запроса питания: {a_response.status_code}")
        
        time.sleep(3)
        
        if a_response.status_code not in [200, 202,203,204]:
            logger.warning(f"Ошибка post запроса: {a_response.status_code}")
            return False


        b_response = redfish_session.get(base_url + 'Systems/system')
        if b_response.status_code not in [200, 202,203,204]:
            logger.warning(f"Ошибка получения состояния питания: {b_response.status_code}")
            return False
            
        power_state = b_response.json().get('PowerState', 'Unknown')
        logger.info(f"Текущее состояние питания: {power_state}")
        
        return (a_response.status_code == 202) and (power_state == "On")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка управления питанием: {e}")
        return False
    except ValueError as e:
        logger.error(f"Ошибка парсинга JSON состояния питания: {e}")
        return False

def test_power(redfish_session, base_url):
    assert power(redfish_session, base_url) == True

def cpu_temperature(redfish_session, base_url):
    try:
        logger.info("Проверка температуры CPU")
        thermal_url = base_url + 'Chassis/chassis/ThermalSubsystem'
        response = redfish_session.get(thermal_url)
        
        if response.status_code not in [200, 202,203,204]:
            logger.warning(f"Ошибка получения температур: {response.status_code}")
            return False
        
        thermal_data = response.json()
        
        cpu_temperatures = []
        temperatures = thermal_data.get('Temperatures', [])
        
        for temp_sensor in temperatures:
            name = temp_sensor.get('Name', '')
            reading = temp_sensor.get('ReadingCelsius')
            thresholds = temp_sensor.get('Thresholds', {})
            
            if any(cpu_keyword in name for cpu_keyword in ['CPU', 'Processor', 'Core']):
                cpu_temperatures.append({
                    'name': name,
                    'temperature': reading,
                    'warning': thresholds.get('UpperCritical', {}).get('ReadingCelsius'),
                    'critical': thresholds.get('UpperCritical', {}).get('ReadingCelsius')
                })
        
        if not cpu_temperatures:
            logger.warning("Не найдено сенсоров температуры CPU")
            return False
        
        all_within_limits = True
        
        for cpu_temp in cpu_temperatures:
            temp = cpu_temp['temperature']
            warning = cpu_temp['warning']
            critical = cpu_temp['critical']
            
            logger.info(f"Сенсор {cpu_temp['name']}: {temp}°C")
            
            if temp is None:
                logger.warning(f"Нет данных температуры для {cpu_temp['name']}")
                all_within_limits = False
            elif critical and temp >= critical:
                logger.error(f"КРИТИЧЕСКАЯ температура {cpu_temp['name']}: {temp}°C превышает {critical}°C")
                all_within_limits = False
            elif warning and temp >= warning:
                logger.warning(f"Высокая температура {cpu_temp['name']}: {temp}°C превышает {warning}°C")
            else:
                logger.info(f"Температура {cpu_temp['name']} в пределах нормы")
        
        return all_within_limits
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка получения температуры CPU: {e}")
        return False
    except ValueError as e:
        logger.error(f"Ошибка парсинга JSON температур: {e}")
        return False

def test_cpu_temperature(redfish_session, base_url):
    assert cpu_temperature(redfish_session, base_url) == True

def get_ipmi_sensors():
    try:
        logger.info("Получение сенсоров через IPMI")
        result = subprocess.run([
            'ipmitool','-I','lanplus','-H','127.0.0.1','-p','2623','-U','root','-P','0penBmc', 'sensor', 'list'
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logger.error(f"Ошибка IPMI: {result.stderr}")
            return {}
        
        sensors = {}
        lines = result.stdout.split('\n')
        
        for line in lines:
            if '|' in line:
                parts = [part.strip() for part in line.split('|')]
                if len(parts) >= 6:
                    sensor_name = parts[0]
                    reading = parts[1]
                    status = parts[3]
                    
                    reading_match = re.search(r'(\d+\.?\d*)', reading)
                    if reading_match:
                        sensors[sensor_name] = {
                            'value': float(reading_match.group(1)),
                            'status': status,
                            'raw_line': line
                        }
        
        logger.info(f"Получено {len(sensors)} сенсоров IPMI")
        return sensors
        
    except subprocess.TimeoutExpired:
        logger.error("Таймаут команды IPMI")
        return {}
    except Exception as e:
        logger.error(f"Ошибка получения сенсоров IPMI: {e}")
        return {}

def get_redfish_sensors(redfish_session, base_url):
    try:
        logger.info("Получение сенсоров через Redfish")
        sensors = {}
        
        thermal_url = base_url + 'Chassis/chassis/ThermalSubsystem'
        thermal_response = redfish_session.get(thermal_url)
        
        if thermal_response.status_code in [200, 202,203,204]:
            thermal_data = thermal_response.json()
            
            for temp in thermal_data.get('Temperatures', []):
                name = temp.get('Name', '')
                reading = temp.get('ReadingCelsius')
                if reading is not None:
                    sensors[name] = {
                        'value': reading,
                        'type': 'temperature',
                        'unit': 'Celsius'
                    }
        
        power_url = base_url + 'Chassis/chassis/Power'
        power_response = redfish_session.get(power_url)
        
        if power_response.status_code in [200, 202,203,204]:
            power_data = power_response.json()
            for voltage in power_data.get('Voltages', []):
                name = voltage.get('Name', '')
                reading = voltage.get('ReadingVolts')
                if reading is not None:
                    sensors[name] = {
                        'value': reading,
                        'type': 'voltage',
                        'unit': 'Volts'
                    }
        
        logger.info(f"Получено {len(sensors)} сенсоров Redfish")
        return sensors
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка получения сенсоров Redfish: {e}")
        return {}
    except ValueError as e:
        logger.error(f"Ошибка парсинга JSON сенсоров Redfish: {e}")
        return {}

def compare_sensors_redfish_ipmi(redfish_session, base_url):
    try:
        logger.info("Сравнение сенсоров Redfish и IPMI...")
        
        redfish_sensors = get_redfish_sensors(redfish_session, base_url)
        ipmi_sensors = get_ipmi_sensors()
        
        if not redfish_sensors:
            logger.error("Нет данных сенсоров Redfish")
            return False
        
        if not ipmi_sensors:
            logger.error("Нет данных сенсоров IPMI")
            return False
        
        logger.info(f"Redfish сенсоров: {len(redfish_sensors)}, IPMI сенсоров: {len(ipmi_sensors)}")
        
        common_sensors = set()
        redfish_only = set(redfish_sensors.keys())
        ipmi_only = set(ipmi_sensors.keys())
        
        for rf_name in redfish_sensors:
            for ipmi_name in ipmi_sensors:
                rf_lower = rf_name.lower()
                ipmi_lower = ipmi_name.lower()
                
                common_keywords = ['cpu', 'temp', 'core', 'processor', 'system', 'ambient']
                
                if any(keyword in rf_lower and keyword in ipmi_lower for keyword in common_keywords):
                    common_sensors.add((rf_name, ipmi_name))
                    if rf_name in redfish_only:
                        redfish_only.remove(rf_name)
                    if ipmi_name in ipmi_only:
                        ipmi_only.remove(ipmi_name)
        
        logger.info(f"Общих сенсоров: {len(common_sensors)}")
        
        comparison_results = []
        tolerance = 5.0 
        
        for rf_name, ipmi_name in common_sensors:
            rf_value = redfish_sensors[rf_name]['value']
            ipmi_value = ipmi_sensors[ipmi_name]['value']
            difference = abs(rf_value - ipmi_value)
            status = "Совпадает" if difference <= tolerance else "Не совпадает"
            
            logger.info(f"{status}: {rf_name} (Redfish): {rf_value} vs {ipmi_name} (IPMI): {ipmi_value} | Разница: {difference:.2f}")
            
            comparison_results.append(difference <= tolerance)
        
        if redfish_only:
            logger.info(f"Только в Redfish: {list(redfish_only)[:3]}...")
        
        if ipmi_only:
            logger.info(f"Только в IPMI: {list(ipmi_only)[:3]}...")
        
        if common_sensors and comparison_results:
            matching_count = sum(comparison_results)
            total_count = len(comparison_results)
            match_percentage = matching_count / total_count * 100
            logger.info(f"Совпадения: {matching_count}/{total_count} ({match_percentage:.1f}%)")
            return match_percentage >= 50.0
        else:
            logger.warning("Нет общих сенсоров для сравнения")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка сравнения сенсоров: {e}")
        return False

def test_sensor_comparison(redfish_session, base_url):
    assert compare_sensors_redfish_ipmi(redfish_session, base_url) == True