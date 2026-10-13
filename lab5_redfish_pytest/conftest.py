import pytest
import os
import requests
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (%(filename)s:%(lineno)d): %(message)s")
logger = logging.getLogger("RedfishTests")

def pytest_addoption(parser):
    parser.addoption(
        "--bmc-url",
        action="store",
        default=os.environ.get("BMC_URL", "http://127.0.0.1:8080"),
        help="Base URL for OpenBMC Redfish API (default: http://127.0.0.1:8080)"
    )
    parser.addoption(
        "--bmc-user",
        action="store",
        default=os.environ.get("BMC_USER", "root"),
        help="BMC username (default: root)"
    )
    parser.addoption(
        "--bmc-password",
        action="store",
        default=os.environ.get("BMC_PASSWORD", "0penBmc"),
        help="BMC password (default: 0penBmc)"
    )
    parser.addoption(
        "--ipmi-host",
        action="store",
        default=os.environ.get("IPMI_HOST", None),
        help="Optional remote IPMI host for real ipmitool LAN queries"
    )

@pytest.fixture(scope="session")
def bmc_config(request):
    return {
        "url": request.config.getoption("--bmc-url").rstrip("/"),
        "user": request.config.getoption("--bmc-user"),
        "password": request.config.getoption("--bmc-password"),
        "ipmi_host": request.config.getoption("--ipmi-host")
    }

@pytest.fixture(scope="function")
def redfish_session(bmc_config):
    """
    pytest.fixture для создания и повторного использования Redfish HTTP-сессии.
    Выполняет автоматическую аутентификацию (POST SessionService) и очистку (DELETE).
    """
    logger.info("Initializing Redfish HTTP Session...")
    session = requests.Session()
    # Suppress SSL certificate verification warnings for BMC self-signed certificates
    session.verify = False

    auth_url = f"{bmc_config['url']}/redfish/v1/SessionService/Sessions"
    payload = {
        "UserName": bmc_config["user"],
        "Password": bmc_config["password"]
    }

    session_location = None
    token = None

    try:
        response = session.post(auth_url, json=payload, timeout=10)
        logger.info(f"POST {auth_url} -> Status Code: {response.status_code}")

        if response.status_code in [200, 201]:
            # Extract token from headers or json body
            token = response.headers.get("X-Auth-Token")
            if not token and response.headers.get("content-type") == "application/json":
                token = response.json().get("SessionToken")
            if token:
                session.headers.update({"X-Auth-Token": token})
            session_location = response.headers.get("Location")

        yield {
            "session": session,
            "base_url": bmc_config["url"],
            "token": token,
            "session_location": session_location,
            "initial_response": response
        }

    finally:
        # Teardown: terminate session
        if session_location:
            try:
                del_url = session_location if session_location.startswith("http") else f"{bmc_config['url']}{session_location}"
                logger.info(f"Teardown: Deleting Redfish session at {del_url}")
                session.delete(del_url, timeout=5)
            except Exception as e:
                logger.warning(f"Session teardown notice: {e}")
        session.close()
