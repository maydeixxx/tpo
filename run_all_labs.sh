#!/usr/bin/env bash
# ==============================================================================
# OpenBMC QA Labs - Главный скрипт запуска и демонстрации
# ==============================================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

VENV_PYTHON="$DIR/venv/bin/python"
VENV_PYTEST="$DIR/venv/bin/pytest"
MOCK_SERVER="$DIR/mock_server/mock_openbmc.py"
PORT=8080
BMC_URL="http://127.0.0.1:$PORT"

# Цвета для красивого вывода
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

ensure_server() {
    if ! curl -s "$BMC_URL/redfish/v1/" > /dev/null 2>&1; then
        echo -e "${YELLOW}⚡ Сервер OpenBMC Mock не обнаружен на порту $PORT. Запускаем в фоне...${NC}"
        "$VENV_PYTHON" "$MOCK_SERVER" --port "$PORT" > /tmp/mock_openbmc.log 2>&1 &
        SERVER_PID=$!
        sleep 1.5
        echo -e "${GREEN}✓ Сервер OpenBMC запущен (PID $SERVER_PID) на $BMC_URL${NC}"
    else
        echo -e "${GREEN}✓ Сервер OpenBMC активен на $BMC_URL${NC}"
    fi
}

echo -e "${CYAN}====================================================================${NC}"
echo -e "${CYAN}  ЛАБОРАТОРНЫЕ РАБОТЫ 3, 4, 5: ТЕСТИРОВАНИЕ OpenBMC (QA Automation) ${NC}"
echo -e "${CYAN}====================================================================${NC}"
echo "Выберите действие:"
echo "1) Запустить ВСЕ тесты (Лаба 4 Selenium + Лаба 5 Redfish)"
echo "2) Лабораторная 4: Автотесты Web UI (Selenium) в фоновом режиме (Headless)"
echo "3) Лабораторная 4: Автотесты Web UI (Selenium) В ЖИВОМ БРАУЗЕРЕ (GUI для показа преподу)"
echo "4) Лабораторная 5: Автотесты Redfish REST API (PyTest -v -s)"
echo "5) Запустить автономный OpenBMC Mock Server в терминале"
echo "6) Выход"
echo ""

read -p "Введите номер [1-6]: " choice

case $choice in
    1)
        ensure_server
        echo -e "\n${BLUE}▶ Запуск Лабораторной работы 4 (Selenium Web UI)...${NC}"
        "$VENV_PYTHON" "$DIR/lab4_selenium_webui/openbmc_auth_tests.py" --url "$BMC_URL"

        echo -e "\n${BLUE}▶ Запуск Лабораторной работы 5 (Redfish API PyTest)...${NC}"
        "$VENV_PYTEST" "$DIR/lab5_redfish_pytest/test_redfish.py" --bmc-url "$BMC_URL" -v
        echo -e "\n${GREEN}🎉 ВСЕ ЛАБОРАТОРНЫЕ РАБОТЫ УСПЕШНО ПРОЙДЕНЫ!${NC}"
        ;;
    2)
        ensure_server
        echo -e "\n${BLUE}▶ Запуск автотестов Selenium Web UI (Headless)...${NC}"
        "$VENV_PYTHON" "$DIR/lab4_selenium_webui/openbmc_auth_tests.py" --url "$BMC_URL"
        ;;
    3)
        ensure_server
        echo -e "\n${BLUE}▶ Запуск автотестов Selenium Web UI в видимом браузере Chrome...${NC}"
        "$VENV_PYTHON" "$DIR/lab4_selenium_webui/openbmc_auth_tests.py" --url "$BMC_URL" --no-headless
        ;;
    4)
        ensure_server
        echo -e "\n${BLUE}▶ Запуск автотестов Redfish API (PyTest)...${NC}"
        "$VENV_PYTEST" "$DIR/lab5_redfish_pytest/test_redfish.py" --bmc-url "$BMC_URL" -v -s
        ;;
    5)
        echo -e "\n${BLUE}▶ Запуск OpenBMC Mock Server... (Нажмите Ctrl+C для остановки)${NC}"
        "$VENV_PYTHON" "$MOCK_SERVER" --port "$PORT"
        ;;
    6)
        echo "Выход."
        exit 0
        ;;
    *)
        echo "Неверный выбор."
        exit 1
        ;;
esac
