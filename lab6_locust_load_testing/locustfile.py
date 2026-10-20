"""
Лабораторная работа 6. Разработка сценария нагрузочного тестирования с использованием Locust.
Студенты: Карев А.А., Ребрик Д.С. (СибГУТИ, Вариант 8)

Содержит два класса виртуальных пользователей:
1. OpenBmcUser - нагрузочное тестирование DMTF Redfish API платформы OpenBMC:
   - Запрос общей информации о вычислительной системе (/redfish/v1/Systems/system)
   - Запрос текущего состояния электропитания сервера (PowerState)
   - Запрос корневого сервиса Redfish (/redfish/v1/) с Basic-аутентификацией (root:0penBmc)
2. PublicApiUser - нагрузочное тестирование открытых публичных веб-сервисов:
   - Запрос списка постов на JSONPlaceholder (/posts)
   - Запрос прогноза погоды на wttr.in (Novosibirsk?format=j1)
"""

import json
from locust import HttpUser, task, between, events
from requests.auth import HTTPBasicAuth


class OpenBmcUser(HttpUser):
    """
    Класс пользователя для нагрузочного тестирования OpenBMC Redfish API.
    Моделирует работу администратора и систем мониторинга серверов.
    """
    weight = 3
    wait_time = between(1.0, 2.5)

    def on_start(self):
        """Инициализация учетных данных перед началом генерации нагрузки"""
        self.auth = HTTPBasicAuth("root", "0penBmc")
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    @task(3)
    def test_get_system_info(self):
        """
        Тест 1.1: Запрос информации о сервере (/redfish/v1/Systems/system)
        Валидирует код 200, статус хоста и базовые поля конфигурации.
        """
        with self.client.get(
            "/redfish/v1/Systems/system",
            auth=self.auth,
            headers=self.headers,
            catch_response=True,
            name="[OpenBMC] GET /redfish/v1/Systems/system"
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "Status" in data and "PowerState" in data:
                        response.success()
                    else:
                        response.failure("Missing required keys ('Status', 'PowerState') in response")
                except Exception as e:
                    response.failure(f"JSON decode error: {e}")
            else:
                response.failure(f"Failed with status code: {response.status_code}")

    @task(2)
    def test_get_power_state(self):
        """
        Тест 1.2: Запрос состояния питания (PowerState)
        Валидирует получение актуального состояния электропитания (On / Off).
        """
        with self.client.get(
            "/redfish/v1/Systems/system/PowerState",
            auth=self.auth,
            headers=self.headers,
            catch_response=True,
            name="[OpenBMC] GET /redfish/v1/Systems/system/PowerState"
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "PowerState" in data and data["PowerState"] in ["On", "Off", "PoweringOn", "PoweringOff"]:
                        response.success()
                    else:
                        response.failure(f"Unexpected PowerState: {data.get('PowerState')}")
                except Exception as e:
                    response.failure(f"JSON decode error: {e}")
            elif response.status_code == 404:
                # Если отдельный эндпоинт недоступен на физическом BMC, делаем fallback на /Systems/system
                with self.client.get(
                    "/redfish/v1/Systems/system",
                    auth=self.auth,
                    headers=self.headers,
                    catch_response=True,
                    name="[OpenBMC] GET /redfish/v1/Systems/system (PowerState fallback)"
                ) as fallback_resp:
                    if fallback_resp.status_code == 200 and "PowerState" in fallback_resp.json():
                        response.success()
                    else:
                        response.failure(f"PowerState unavailable: status {fallback_resp.status_code}")
            else:
                response.failure(f"Failed with status code: {response.status_code}")

    @task(1)
    def test_get_root_service(self):
        """
        Тест 1.3: Запрос корневого сервиса Redfish (/redfish/v1/)
        Проверка доступности и версии стандарта Redfish.
        """
        with self.client.get(
            "/redfish/v1/",
            auth=self.auth,
            headers=self.headers,
            catch_response=True,
            name="[OpenBMC] GET /redfish/v1/ (Root Service)"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Redfish root unavailable: status {response.status_code}")


class PublicApiUser(HttpUser):
    """
    Класс пользователя для нагрузочного тестирования открытых публичных API:
    JSONPlaceholder (REST API) и wttr.in (погодный сервис г. Новосибирск).
    """
    weight = 2
    wait_time = between(1.5, 3.0)

    @task(2)
    def test_jsonplaceholder_posts(self):
        """
        Тест 2.1: Запрос списка постов с открытого сервиса JSONPlaceholder
        URL: https://jsonplaceholder.typicode.com/posts
        """
        with self.client.get(
            "https://jsonplaceholder.typicode.com/posts",
            catch_response=True,
            name="[Public API] GET JSONPlaceholder /posts",
            timeout=10
        ) as response:
            if response.status_code == 200:
                try:
                    posts = response.json()
                    if isinstance(posts, list) and len(posts) > 0:
                        response.success()
                    else:
                        response.failure("Response is not a non-empty list of posts")
                except Exception as e:
                    response.failure(f"JSON decode error: {e}")
            else:
                response.failure(f"JSONPlaceholder returned status: {response.status_code}")

    @task(1)
    def test_wttr_in_weather(self):
        """
        Тест 2.2: Запрос сводки погоды для г. Новосибирск с wttr.in в формате JSON
        URL: https://wttr.in/Novosibirsk?format=j1
        """
        headers = {"User-Agent": "curl/8.7.1"}
        with self.client.get(
            "https://wttr.in/Novosibirsk?format=j1",
            headers=headers,
            catch_response=True,
            name="[Public API] GET wttr.in /Novosibirsk?format=j1",
            timeout=10
        ) as response:
            if response.status_code == 200:
                try:
                    weather_data = response.json()
                    if "current_condition" in weather_data:
                        response.success()
                    else:
                        response.failure("Missing 'current_condition' in weather response")
                except Exception as e:
                    response.failure(f"Weather JSON parsing error: {e}")
            elif response.status_code == 429:
                # Внешний сервис wttr.in может отдавать rate-limit (429 Too Many Requests)
                # Фиксируем это как корректную диагностику точки отказа публичного API
                response.failure("wttr.in Rate-Limit (HTTP 429: Too Many Requests) - Public API failure point detected")
            else:
                response.failure(f"wttr.in returned status: {response.status_code}")
