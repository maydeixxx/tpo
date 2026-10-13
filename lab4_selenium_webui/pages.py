"""
Page Object Model (POM) implementation for OpenBMC Web UI.
Enables clean separation between page elements/interactions and test logic.
"""

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


class BasePage:
    def __init__(self, driver, base_url="http://127.0.0.1:8080"):
        self.driver = driver
        self.base_url = base_url.rstrip("/")
        self.timeout = 10

    def wait(self):
        return WebDriverWait(self.driver, self.timeout)

    def find(self, locator):
        return self.wait().until(EC.presence_of_element_located(locator))

    def find_visible(self, locator):
        return self.wait().until(EC.visibility_of_element_located(locator))

    def click(self, locator):
        el = self.wait().until(EC.element_to_be_clickable(locator))
        el.click()
        return el

    def type_text(self, locator, text):
        el = self.find_visible(locator)
        el.clear()
        el.send_keys(text)
        return el

    def get_text(self, locator):
        return self.find_visible(locator).text


class LoginPage(BasePage):
    USERNAME_INPUT = (By.ID, "username")
    PASSWORD_INPUT = (By.ID, "password")
    LOGIN_BUTTON = (By.ID, "login-button")
    ERROR_ALERT = (By.ID, "error-alert")
    LOCKOUT_ALERT = (By.ID, "lockout-alert")

    def open(self):
        self.driver.get(f"{self.base_url}/login")
        return self

    def login(self, username, password):
        self.type_text(self.USERNAME_INPUT, username)
        self.type_text(self.PASSWORD_INPUT, password)
        self.click(self.LOGIN_BUTTON)

    def get_error_message(self):
        try:
            return self.get_text(self.ERROR_ALERT)
        except TimeoutException:
            return None

    def get_lockout_message(self):
        try:
            return self.get_text(self.LOCKOUT_ALERT)
        except TimeoutException:
            return None

    def is_login_page_displayed(self):
        try:
            return self.find_visible(self.USERNAME_INPUT).is_displayed()
        except TimeoutException:
            return False


class DashboardPage(BasePage):
    HOST_STATUS = (By.ID, "host-status")
    USER_BADGE = (By.ID, "current-user")
    LOGOUT_BUTTON = (By.ID, "btn-logout")
    NAV_OVERVIEW = (By.ID, "nav-overview")
    NAV_SERVER_CONTROL = (By.ID, "nav-server-control")
    NAV_LOGS = (By.ID, "nav-logs")
    NAV_SENSORS = (By.ID, "nav-sensors")
    NAV_INVENTORY = (By.ID, "nav-inventory")

    def is_loaded(self):
        try:
            return self.find_visible(self.USER_BADGE).is_displayed()
        except TimeoutException:
            return False

    def get_current_user(self):
        return self.get_text(self.USER_BADGE)

    def get_host_status(self):
        return self.get_text(self.HOST_STATUS)

    def logout(self):
        self.click(self.LOGOUT_BUTTON)


class ServerControlPage(BasePage):
    BTN_POWER_ON = (By.ID, "btn-power-on")
    BTN_POWER_OFF = (By.ID, "btn-power-off")
    BTN_REBOOT = (By.ID, "btn-reboot")
    HOST_STATUS = (By.ID, "host-status")

    def open(self):
        self.driver.get(f"{self.base_url}/server-control")
        return self

    def power_on(self):
        self.click(self.BTN_POWER_ON)
        time.sleep(0.5)

    def power_off(self):
        self.click(self.BTN_POWER_OFF)
        time.sleep(0.5)

    def reboot(self):
        self.click(self.BTN_REBOOT)
        time.sleep(0.5)

    def get_power_status(self):
        return self.get_text(self.HOST_STATUS)


class LogsPage(BasePage):
    LOGS_TABLE = (By.ID, "logs-table")
    LOG_MESSAGES = (By.CLASS_NAME, "log-message")

    def open(self):
        self.driver.get(f"{self.base_url}/logs")
        return self

    def get_all_log_messages(self):
        self.find_visible(self.LOGS_TABLE)
        elements = self.driver.find_elements(*self.LOG_MESSAGES)
        return [el.text for el in elements]

    def has_log_containing(self, substring):
        messages = self.get_all_log_messages()
        return any(substring.lower() in msg.lower() for msg in messages)


class SensorsPage(BasePage):
    SENSORS_TABLE = (By.ID, "sensors-table")
    CPU0_TEMP = (By.ID, "sensor-cpu0_temp-temp")

    def open(self):
        self.driver.get(f"{self.base_url}/sensors")
        return self

    def get_cpu0_temperature_value(self):
        text = self.get_text(self.CPU0_TEMP)
        # Parses "42.0 C" -> 42.0
        val = text.replace("°C", "").replace("C", "").strip()
        return float(val)


class InventoryPage(BasePage):
    INVENTORY_TABLE = (By.ID, "inventory-table")
    CPU_MODEL = (By.ID, "cpu-model")
    RAM_TOTAL = (By.ID, "ram-total")
    MB_MODEL = (By.ID, "mb-model")

    def open(self):
        self.driver.get(f"{self.base_url}/inventory")
        return self

    def get_cpu_info(self):
        return self.get_text(self.CPU_MODEL)

    def get_ram_info(self):
        return self.get_text(self.RAM_TOTAL)
