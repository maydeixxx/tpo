import pytest
import os

def pytest_addoption(parser):
    parser.addoption(
        "--bmc-url",
        action="store",
        default=os.environ.get("BMC_URL", "http://127.0.0.1:8080"),
        help="Базовый URL к OpenBMC стенду / mock серверу"
    )
    parser.addoption(
        "--show-browser",
        action="store_true",
        default=False,
        help="Запустить браузер в обычном (не headless) графическом режиме"
    )

@pytest.fixture(scope="session")
def bmc_url(request):
    return request.config.getoption("--bmc-url")

@pytest.fixture(scope="session")
def show_browser(request):
    return request.config.getoption("--show-browser")
