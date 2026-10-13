"""
Лабораторная работа 5: Разработка автотестов для API Redfish с использованием PyTest.
Файл: test_redfish.py

Сценарии:
1. Тест аутентификации в OpenBMC через Redfish API
2. Тест получения информации о системе (Status, PowerState)
3. Тест управления питанием (включение/выключение, ResetType: On, 202 Accepted)
4. Тест на соответствие температуры CPU норме в Redfish
5. Тест на соответствие датчиков CPU в Redfish и IPMI
"""

import subprocess
import logging
import pytest
import requests

logger = logging.getLogger("RedfishTests")


def test_01_redfish_authentication(bmc_config):
    """
    Тест 1: Аутентификация в OpenBMC через Redfish API.
    - Отправка POST-запроса на /redfish/v1/SessionService/Sessions
    - Проверка кода ответа (200 OK или 201 Created по стандарту Redfish)
    - Проверка присутствия токена сессии в заголовках (X-Auth-Token) или теле ответа
    """
    logger.info("=== Запуск Теста 1: Аутентификация в Redfish API ===")
    url = f"{bmc_config['url']}/redfish/v1/SessionService/Sessions"
    payload = {
        "UserName": bmc_config["user"],
        "Password": bmc_config["password"]
    }

    try:
        response = requests.post(url, json=payload, verify=False, timeout=10)
        logger.info(f"Запрос: POST {url} | Код ответа: {response.status_code}")
    except requests.RequestException as e:
        logger.error(f"Сетевая ошибка при обращении к BMC: {e}")
        pytest.fail(f"Ошибка соединения с OpenBMC: {e}")

    # Стандарт DMTF допускает 200 OK или 201 Created
    assert response.status_code in [200, 201], (
        f"Ожидался код 200 или 201, получен {response.status_code}. Тело ответа: {response.text}"
    )

    token = response.headers.get("X-Auth-Token")
    if not token and response.headers.get("content-type") == "application/json":
        data = response.json()
        token = data.get("SessionToken") or data.get("Token")

    assert token is not None and len(token) > 0, (
        "Токен авторизации X-Auth-Token отсутствует в ответе сервера!"
    )
    logger.info(f"✓ Токен сессии успешно получен: {token[:8]}... (длина {len(token)})")


def test_02_system_information(redfish_session):
    """
    Тест 2: Получение информации о системе.
    - Отправка GET-запроса на /redfish/v1/Systems/system
    - Проверка статус-кода (200 OK)
    - Валидация наличия критических ключей 'Status' и 'PowerState'
    """
    logger.info("=== Запуск Теста 2: Получение информации о системе ===")
    session = redfish_session["session"]
    url = f"{redfish_session['base_url']}/redfish/v1/Systems/system"

    try:
        response = session.get(url, timeout=10)
        logger.info(f"Запрос: GET {url} | Код ответа: {response.status_code}")
    except requests.RequestException as e:
        logger.error(f"Ошибка запроса информации о системе: {e}")
        pytest.fail(f"Не удалось получить данные о системе: {e}")

    assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}"

    data = response.json()
    assert "Status" in data, "В ответе отсутствует секция 'Status'"
    assert "PowerState" in data, "В ответе отсутствует атрибут 'PowerState'"

    power_state = data["PowerState"]
    health = data["Status"].get("Health", "Unknown")
    state = data["Status"].get("State", "Unknown")

    logger.info(f"✓ Статус системы получен: PowerState='{power_state}', State='{state}', Health='{health}'")
    assert power_state in ["On", "Off", "PoweringOn", "PoweringOff"], f"Недопустимое значение PowerState: {power_state}"


def test_03_power_control_reset(redfish_session):
    """
    Тест 3: Управление питанием (включение/выключение/сброс сервера).
    - Отправка POST-запроса на /redfish/v1/Systems/system/Actions/ComputerSystem.Reset с 'ResetType': 'On'
    - Проверка статус-кода ответа (202 Accepted или 200/204)
    - Повторный GET на /redfish/v1/Systems/system и валидация 'PowerState': 'On'
    """
    logger.info("=== Запуск Теста 3: Управление питанием сервера через Redfish ===")
    session = redfish_session["session"]
    reset_url = f"{redfish_session['base_url']}/redfish/v1/Systems/system/Actions/ComputerSystem.Reset"
    payload = {"ResetType": "On"}

    try:
        response = session.post(reset_url, json=payload, timeout=10)
        logger.info(f"Запрос: POST {reset_url} (ResetType: On) | Код ответа: {response.status_code}")
    except requests.RequestException as e:
        logger.error(f"Ошибка отправки команды сброса питания: {e}")
        pytest.fail(f"Команда управления питанием завершилась с ошибкой: {e}")

    # Согласно спецификации Redfish операция Reset возвращает 202 Accepted (асинхронное действие) либо 200/204
    assert response.status_code in [200, 202, 204], (
        f"Ожидался статус 202/200/204, получен {response.status_code}. Ответ: {response.text}"
    )

    # Проверяем обновленный статус системы
    system_url = f"{redfish_session['base_url']}/redfish/v1/Systems/system"
    system_resp = session.get(system_url, timeout=10)
    assert system_resp.status_code == 200
    current_power = system_resp.json().get("PowerState")

    logger.info(f"✓ Текущий PowerState после команды ResetType='On': '{current_power}'")
    assert current_power == "On", f"Ожидался PowerState == 'On', получен '{current_power}'"


def test_04_cpu_temperature_within_limits(redfish_session):
    """
    Тест 4: Проверка соответствия температуры CPU норме в Redfish API.
    - Отправка GET-запроса на /redfish/v1/Chassis/chassis/Thermal
    - Поиск температурного датчика процессора в списке Temperatures
    - Проверка, что температура не превышает порог non-critical и критический
    - Проверка здоровья датчика Status.Health == 'OK'
    """
    logger.info("=== Запуск Теста 4: Проверка температуры CPU в Redfish ===")
    session = redfish_session["session"]
    thermal_url = f"{redfish_session['base_url']}/redfish/v1/Chassis/chassis/Thermal"

    try:
        response = session.get(thermal_url, timeout=10)
        logger.info(f"Запрос: GET {thermal_url} | Код ответа: {response.status_code}")
    except requests.RequestException as e:
        logger.error(f"Ошибка запроса термических датчиков: {e}")
        pytest.fail(f"Не удалось получить данные термодатчиков: {e}")

    assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}"

    thermal_data = response.json()
    temperatures = thermal_data.get("Temperatures", [])
    assert len(temperatures) > 0, "Массив датчиков 'Temperatures' пуст"

    # Находим датчик CPU
    cpu_sensor = None
    for temp in temperatures:
        name = temp.get("Name", "") + temp.get("MemberId", "")
        if "cpu" in name.lower():
            cpu_sensor = temp
            break

    assert cpu_sensor is not None, "Сенсор температуры CPU не найден в списке датчиков"

    reading = cpu_sensor.get("ReadingCelsius")
    upper_warn = cpu_sensor.get("UpperThresholdNonCritical", 75.0)
    upper_crit = cpu_sensor.get("UpperThresholdCritical", 85.0)
    health = cpu_sensor.get("Status", {}).get("Health", "OK")

    logger.info(
        f"Датчик: '{cpu_sensor.get('Name')}' | Текущее значение: {reading}°C | "
        f"Предупреждение: {upper_warn}°C | Критический: {upper_crit}°C | Статус: {health}"
    )

    assert reading is not None and isinstance(reading, (int, float)), f"Некорректное значение температуры: {reading}"
    assert reading <= upper_warn, f"Температура CPU ({reading}°C) превышает порог предупреждения ({upper_warn}°C)!"
    assert reading <= upper_crit, f"Температура CPU ({reading}°C) превышает критический порог ({upper_crit}°C)!"
    assert health == "OK", f"Статус здоровья термодатчика не в норме: {health}"
    logger.info(f"✓ Температура процессора в норме ({reading}°C <= {upper_warn}°C)")


def test_05_cpu_temperature_redfish_vs_ipmi_consistency(redfish_session, bmc_config):
    """
    Тест 5: Проверка соответствия показаний датчиков CPU между Redfish и IPMI.
    - Запрос температуры через Redfish API
    - Запрос температуры через IPMI (ipmitool LAN либо эмулятор IPMI)
    - Сравнение значений: дельта не должна превышать допустимую погрешность (<= 1.0°C)
    """
    logger.info("=== Запуск Теста 5: Сравнение показаний датчиков между Redfish и IPMI ===")
    session = redfish_session["session"]

    # 1. Получаем температуру из Redfish
    thermal_url = f"{redfish_session['base_url']}/redfish/v1/Chassis/chassis/Thermal"
    response = session.get(thermal_url, timeout=10)
    assert response.status_code == 200
    temperatures = response.json().get("Temperatures", [])

    redfish_cpu_temp = None
    for temp in temperatures:
        name = temp.get("Name", "") + temp.get("MemberId", "")
        if "cpu0" in name.lower() or "cpu" in name.lower():
            redfish_cpu_temp = float(temp["ReadingCelsius"])
            break

    assert redfish_cpu_temp is not None, "Датчик CPU не найден в Redfish"
    logger.info(f"Показание Redfish API CPU Temp: {redfish_cpu_temp} °C")

    # 2. Получаем температуру через IPMI
    ipmi_cpu_temp = None
    ipmi_host = bmc_config.get("ipmi_host")

    if ipmi_host:
        # Реальный вызов утилиты ipmitool по сети (IPMI over LAN)
        cmd = [
            "ipmitool", "-I", "lanplus",
            "-H", ipmi_host,
            "-U", bmc_config["user"],
            "-P", bmc_config["password"],
            "sensor", "reading", "CPU0_Temp"
        ]
        logger.info(f"Вызов ipmitool: {' '.join(cmd)}")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                # Пример вывода: "CPU0_Temp | 42.000 | degrees C | ok"
                parts = res.stdout.split("|")
                if len(parts) >= 2:
                    ipmi_cpu_temp = float(parts[1].strip())
        except Exception as e:
            logger.warning(f"Не удалось выполнить ipmitool: {e}")

    # Если реальный хост не задан или недоступен, опрашиваем IPMI эмулятор
    if ipmi_cpu_temp is None:
        try:
            mock_ipmi_url = f"{redfish_session['base_url']}/api/mock/ipmi/cpu_temp"
            resp = requests.get(mock_ipmi_url, timeout=5)
            if resp.status_code == 200:
                ipmi_cpu_temp = float(resp.json()["reading_celsius"])
                logger.info(f"Получено значение от IPMI-интерфейса: {ipmi_cpu_temp} °C")
        except Exception as e:
            logger.warning(f"Не удалось опросить mock IPMI endpoint: {e}")

    assert ipmi_cpu_temp is not None, "Не удалось получить показания датчика через IPMI"

    # 3. Сравнение
    delta = abs(redfish_cpu_temp - ipmi_cpu_temp)
    MAX_ALLOWED_DELTA = 1.0  # Допустимая погрешность 1 градус Цельсия
    logger.info(
        f"Сравнение: Redfish = {redfish_cpu_temp}°C, IPMI = {ipmi_cpu_temp}°C, "
        f"Разница = {delta:.2f}°C (порог <= {MAX_ALLOWED_DELTA}°C)"
    )

    assert delta <= MAX_ALLOWED_DELTA, (
        f"Показания Redfish ({redfish_cpu_temp}°C) и IPMI ({ipmi_cpu_temp}°C) расходятся на {delta}°C > {MAX_ALLOWED_DELTA}°C!"
    )
    logger.info("✓ Показания датчиков CPU в Redfish и IPMI полностью согласованы!")
