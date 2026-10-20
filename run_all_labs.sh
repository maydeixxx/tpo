#!/usr/bin/env bash
# ==============================================================================
# OpenBMC QA Labs - Главный скрипт запуска и демонстрации всех лабораторных работ
# Дисциплина: Тестирование системного программного обеспечения
# Студенты: Карев А.А., Ребрик Д.С. (СибГУТИ, Вариант 8)
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
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

ensure_server() {
    if ! curl -s "$BMC_URL/redfish/v1/" > /dev/null 2>&1; then
        echo -e "${YELLOW}⚡ Сервер OpenBMC Mock не обнаружен на порту $PORT. Запускаем в фоне...${NC}"
        "$VENV_PYTHON" "$MOCK_SERVER" --port "$PORT" > /dev/null 2>&1 &
        SERVER_PID=$!
        sleep 1.2
        echo -e "${GREEN}✓ Сервер OpenBMC запущен (PID $SERVER_PID) на $BMC_URL${NC}"
    else
        echo -e "${GREEN}✓ Сервер OpenBMC активен на $BMC_URL${NC}"
    fi
}

echo -e "${CYAN}====================================================================${NC}"
echo -e "${CYAN}  КОМПЛЕКС ЛАБОРАТОРНЫХ РАБОТ ПО OpenBMC: ЛР 3, 4, 5, 6, 7, 8       ${NC}"
echo -e "${CYAN}  СибГУТИ (г. Новосибирск), Студенты: Карев А.А., Ребрик Д.С.      ${NC}"
echo -e "${CYAN}====================================================================${NC}"
echo "Выберите действие:"
echo -e "${GREEN}1) Запустить ВСЕ лабораторные работы разом (ЛР 3, 4, 5, 6, 7, 8)${NC}"
echo "2) ЛАБОРАТОРНАЯ 3: Выполнить тест-кейсы Варианта 8 (Питание, Вентиляторы, IPMI, SEL)"
echo "3) ЛАБОРАТОРНАЯ 4: Автотесты Web UI (Selenium) В ЖИВОМ ОКНЕ CHROME (для показа)"
echo "4) ЛАБОРАТОРНАЯ 4: Автотесты Web UI (Selenium) в фоне (Headless)"
echo "5) ЛАБОРАТОРНАЯ 5: Автотесты Redfish REST API (PyTest -v -s)"
echo -e "${MAGENTA}6) ЛАБОРАТОРНАЯ 6: Нагрузочное тестирование Locust (Web UI / Headless / Графики)${NC}"
echo -e "${MAGENTA}7) ЛАБОРАТОРНАЯ 7: Настройка CI/CD Pipeline (Jenkinsfile / Docker / Симуляция)${NC}"
echo -e "${MAGENTA}8) ЛАБОРАТОРНАЯ 8: Профилирование ПО QEMU (CPU до/во время, Память MB, графики)${NC}"
echo "9) Запустить OpenBMC Mock Server в терминале"
echo "10) Выход"
echo ""

read -p "Введите номер [1-10]: " choice
choice=${choice:-1}

case $choice in
    1)
        ensure_server
        echo -e "\n${BLUE}▶ [Лабораторная 3] Выполнение тест-кейсов Варианта 8...${NC}"
        "$VENV_PYTHON" "$DIR/lab3_test_plan/run_lab3_variant8.py"

        echo -e "\n${BLUE}▶ [Лабораторная 4] Запуск автотестов Web UI (Selenium Headless)...${NC}"
        "$VENV_PYTHON" "$DIR/lab4_selenium_webui/openbmc_auth_tests.py" --url "$BMC_URL"

        echo -e "\n${BLUE}▶ [Лабораторная 5] Запуск автотестов Redfish API (PyTest)...${NC}"
        "$VENV_PYTEST" "$DIR/lab5_redfish_pytest/test_redfish.py" --bmc-url "$BMC_URL" -v

        echo -e "\n${BLUE}▶ [Лабораторная 6] Запуск нагрузочного тестирования (Locust)...${NC}"
        "$VENV_PYTHON" "$DIR/lab6_locust_load_testing/run_locust_analysis.py"

        echo -e "\n${BLUE}▶ [Лабораторная 7] Запуск симуляции Jenkins Pipeline...${NC}"
        bash "$DIR/lab7_ci_cd/simulate_pipeline.sh"

        echo -e "\n${BLUE}▶ [Лабораторная 8] Запуск профилирования QEMU...${NC}"
        "$VENV_PYTHON" "$DIR/lab8_profiling/qemu_profiler.py"

        echo -e "\n${GREEN}🎉 ВСЕ ЛАБОРАТОРНЫЕ РАБОТЫ (3, 4, 5, 6, 7, 8) УСПЕШНО ВЫПОЛНЕНЫ!${NC}"
        ;;
    2)
        ensure_server
        "$VENV_PYTHON" "$DIR/lab3_test_plan/run_lab3_variant8.py"
        ;;
    3)
        ensure_server
        "$VENV_PYTHON" "$DIR/lab4_selenium_webui/openbmc_auth_tests.py" --url "$BMC_URL" --no-headless
        ;;
    4)
        ensure_server
        "$VENV_PYTHON" "$DIR/lab4_selenium_webui/openbmc_auth_tests.py" --url "$BMC_URL"
        ;;
    5)
        ensure_server
        "$VENV_PYTEST" "$DIR/lab5_redfish_pytest/test_redfish.py" --bmc-url "$BMC_URL" -v -s
        ;;
    6)
        bash "$DIR/run_lab6.sh"
        ;;
    7)
        bash "$DIR/run_lab7.sh"
        ;;
    8)
        bash "$DIR/run_lab8.sh"
        ;;
    9)
        echo -e "${BLUE}▶ Запуск OpenBMC Mock Server... (Нажмите Ctrl+C для остановки)${NC}"
        "$VENV_PYTHON" "$MOCK_SERVER" --port "$PORT"
        ;;
    10)
        echo "Выход."
        exit 0
        ;;
    *)
        echo "Неверный выбор."
        exit 1
        ;;
esac
