#!/usr/bin/env python3
"""
Лабораторная работа 4: Разработка автотестов для Web UI с использованием Selenium.
Файл: openbmc_auth_tests.py

Сценарии:
1. Часть 2: Основные сценарии авторизации OpenBMC:
   - Успешная авторизация (root / 0penBmc)
   - Авторизация с неверными данными (проверка сообщения об ошибке)
   - Блокировка учетной записи (lockout после серии неудачных попыток)
2. Дополнительные тесты из Лабораторной работы 3 (Web UI):
   - Управление питанием сервера через Web UI (включение/выключение)
   - Проверка фиксации событий в журнале логов (Event Log)
   - Проверка температурных датчиков компонентов в допустимых пределах
   - Проверка отображения аппаратной инвенторики (CPU, RAM)
"""

import os
import sys
import time
import unittest
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from pages import LoginPage, DashboardPage, ServerControlPage, LogsPage, SensorsPage, InventoryPage


class OpenBMCWebUITestCase(unittest.TestCase):
    BASE_URL = os.environ.get("BMC_URL", "http://127.0.0.1:8080")
    HEADLESS = os.environ.get("HEADLESS", "true").lower() in ("true", "1", "yes")

    @classmethod
    def setUpClass(cls):
        print(f"\n============================================================")
        print(f"🔧 Настройка окружения Selenium WebDriver")
        print(f"   - BMC Web UI URL: {cls.BASE_URL}")
        print(f"   - Headless Mode:  {cls.HEADLESS}")
        print(f"============================================================")

    def setUp(self):
        # Reset mock server state if running against mock server
        try:
            requests.post(f"{self.BASE_URL}/api/mock/reset", timeout=1)
        except Exception:
            pass

        chrome_options = Options()
        if self.HEADLESS:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1400,900")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--allow-insecure-localhost")

        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(5)

        self.login_page = LoginPage(self.driver, self.BASE_URL)
        self.dashboard_page = DashboardPage(self.driver, self.BASE_URL)
        self.server_page = ServerControlPage(self.driver, self.BASE_URL)
        self.logs_page = LogsPage(self.driver, self.BASE_URL)
        self.sensors_page = SensorsPage(self.driver, self.BASE_URL)
        self.inventory_page = InventoryPage(self.driver, self.BASE_URL)

    def tearDown(self):
        if hasattr(self, "driver") and self.driver:
            self.driver.quit()

    # =========================================================================
    # Часть 2: Тесты авторизации (Аутентификация)
    # =========================================================================

    def test_01_successful_login(self):
        """Тест 1: Успешная авторизация в OpenBMC Web UI с валидными учетными данными."""
        print("\n[RUN] Тест 1: Проверка успешной авторизации (root / 0penBmc)...")
        self.login_page.open()
        self.assertTrue(self.login_page.is_login_page_displayed(), "Страница логина не отобразилась")

        self.login_page.login("root", "0penBmc")

        self.assertTrue(self.dashboard_page.is_loaded(), "Панель управления не загрузилась после логина")
        self.assertEqual(self.dashboard_page.get_current_user(), "root", "Имя пользователя не соответствует ожидаемому")
        print("  ✓ Успешный вход выполнен, дашборд отображен, пользователь: root")

        # Проверка выхода
        self.dashboard_page.logout()
        self.assertTrue(self.login_page.is_login_page_displayed(), "После выхода не вернулась страница логина")
        print("  ✓ Выход из системы (Logout) прошел успешно")

    def test_02_invalid_credentials(self):
        """Тест 2: Авторизация с неверными учетными данными (проверка сообщения об ошибке)."""
        print("\n[RUN] Тест 2: Проверка ошибки авторизации при неверном пароле...")
        self.login_page.open()
        self.login_page.login("root", "WrongPassword123")

        error_msg = self.login_page.get_error_message()
        self.assertIsNotNone(error_msg, "Сообщение об ошибке не появилось")
        self.assertIn("invalid", error_msg.lower(), "Текст ошибки не содержит указания на неверные данные")
        print(f"  ✓ Корректно получено сообщение об ошибке: '{error_msg}'")

    def test_03_account_lockout(self):
        """Тест 3: Блокировка учетной записи после серии неудачных попыток ввода пароля."""
        print("\n[RUN] Тест 3: Проверка защитной блокировки аккаунта после 3 неудачных попыток...")
        self.login_page.open()

        # Выполняем 3 неудачные попытки входа
        for attempt in range(1, 4):
            print(f"  -> Неудачная попытка #{attempt}...")
            self.login_page.login("root", f"BadPass_{attempt}")
            time.sleep(0.3)

        lockout_msg = self.login_page.get_lockout_message()
        self.assertIsNotNone(lockout_msg, "Сообщение о блокировке учетной записи не отобразилось")
        self.assertIn("locked", lockout_msg.lower(), "Текст не содержит предупреждения о блокировке аккаунта")
        print(f"  ✓ Аккаунт успешно заблокирован! Текст оповещения: '{lockout_msg}'")

    # =========================================================================
    # Часть 2 (продолжение): Тесты функционала из Лабораторной работы 3 в Web UI
    # =========================================================================

    def _login_as_admin(self):
        self.login_page.open()
        self.login_page.login("root", "0penBmc")
        self.assertTrue(self.dashboard_page.is_loaded(), "Не удалось войти перед тестом")

    def test_04_power_control_via_webui(self):
        """Тест 4 (из ЛР3): Включение / выключение сервера через Web UI."""
        print("\n[RUN] Тест 4: Управление питанием сервера через Web UI...")
        self._login_as_admin()

        self.server_page.open()
        initial_status = self.server_page.get_power_status()
        print(f"  -> Начальный статус питания хоста: {initial_status}")

        # Выключаем хост
        print("  -> Нажимаем кнопку 'Power Off Server'...")
        self.server_page.power_off()
        status_after_off = self.server_page.get_power_status()
        self.assertEqual(status_after_off, "Off", "Статус питания после выключения не равен 'Off'")
        print("  ✓ Статус питания успешно изменен на 'Off'")

        # Включаем хост обратно
        print("  -> Нажимаем кнопку 'Power On Server'...")
        self.server_page.power_on()
        status_after_on = self.server_page.get_power_status()
        self.assertEqual(status_after_on, "On", "Статус питания после включения не равен 'On'")
        print("  ✓ Статус питания успешно восстановлен в 'On'")

    def test_05_event_log_after_action(self):
        """Тест 5 (из ЛР3): Выполнение действия и проверка фиксации события в системных логах."""
        print("\n[RUN] Тест 5: Проверка логирования событий в журнале Event Logs...")
        self._login_as_admin()

        # Выполняем перезагрузку питания
        self.server_page.open()
        print("  -> Инициируем перезагрузку через Web UI...")
        self.server_page.reboot()

        # Переходим в системные логи и проверяем наличие записи
        print("  -> Переходим на страницу Event Logs...")
        self.logs_page.open()
        has_reboot_log = self.logs_page.has_log_containing("reset") or self.logs_page.has_log_containing("power")
        self.assertTrue(has_reboot_log, "Событие изменения питания не обнаружено в журнале логов")
        print("  ✓ Событие успешно зафиксировано в журнале логов (SEL)!")

    def test_06_component_temperature_limits(self):
        """Тест 6 (из ЛР3): Проверка температуры CPU на нахождение в допустимых пределах."""
        print("\n[RUN] Тест 6: Проверка датчика температуры CPU0 через Web UI...")
        self._login_as_admin()

        self.sensors_page.open()
        cpu_temp = self.sensors_page.get_cpu0_temperature_value()
        print(f"  -> Текущая температура CPU0: {cpu_temp} °C")

        # Допустимый рабочий диапазон температур серверного CPU
        MIN_TEMP = 10.0
        MAX_TEMP = 85.0
        self.assertGreaterEqual(cpu_temp, MIN_TEMP, f"Температура CPU ниже нормы ({MIN_TEMP}°C)")
        self.assertLessEqual(cpu_temp, MAX_TEMP, f"Температура CPU превышает критический порог ({MAX_TEMP}°C)")
        print(f"  ✓ Температура CPU ({cpu_temp}°C) находится в допустимых пределах [{MIN_TEMP}..{MAX_TEMP}°C]")

    def test_07_hardware_inventory_display(self):
        """Тест 7 (из ЛР3): Проверка отображения аппаратной инвенторики (CPU, RAM)."""
        print("\n[RUN] Тест 7: Проверка отображения инвенторики оборудования (CPU, RAM)...")
        self._login_as_admin()

        self.inventory_page.open()
        cpu_info = self.inventory_page.get_cpu_info()
        ram_info = self.inventory_page.get_ram_info()

        print(f"  -> Процессор в инвенторике: {cpu_info}")
        print(f"  -> Память в инвенторике:    {ram_info}")

        self.assertTrue(len(cpu_info) > 0 and ("intel" in cpu_info.lower() or "amd" in cpu_info.lower() or "cpu" in cpu_info.lower()),
                        "Информация о процессоре отсутствует или некорректна")
        self.assertTrue(len(ram_info) > 0 and ("gb" in ram_info.lower() or "ddr" in ram_info.lower()),
                        "Информация об оперативной памяти отсутствует или некорректна")
        print("  ✓ Инвенторика оборудования успешно отображается в интерфейсе")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Запуск автотестов OpenBMC Web UI на Selenium")
    parser.add_argument("--url", default="http://127.0.0.1:8080", help="URL веб-интерфейса OpenBMC")
    parser.add_argument("--no-headless", action="store_true", help="Запустить браузер в видимом окне (GUI)")
    args, unknown = parser.parse_known_args()

    OpenBMCWebUITestCase.BASE_URL = args.url
    if args.no_headless:
        OpenBMCWebUITestCase.HEADLESS = False

    # Pass remaining args to unittest
    unittest.main(argv=[sys.argv[0]] + unknown)
