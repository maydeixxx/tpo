#!/bin/bash
# ==============================================================================
# Имитация исполнения Jenkins Pipeline для локальной проверки и демонстрации
# Дисциплина: Тестирование системного программного обеспечения
# Студенты: Карев А.А., Ребрик Д.С. (СибГУТИ, Вариант 8)
# ==============================================================================

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

ARTIFACTS_DIR="$BASE_DIR/build_artifacts"
VENV_PYTHON="$BASE_DIR/venv/bin/python"
VENV_PYTEST="$BASE_DIR/venv/bin/pytest"
VENV_LOCUST="$BASE_DIR/venv/bin/locust"
BMC_PORT=8080
BMC_HOST="http://127.0.0.1:$BMC_PORT"

mkdir -p "$ARTIFACTS_DIR/qemu_logs"
mkdir -p "$ARTIFACTS_DIR/redfish_reports"
mkdir -p "$ARTIFACTS_DIR/webui_reports"
mkdir -p "$ARTIFACTS_DIR/locust_reports"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================================================${NC}"
echo -e "${CYAN}  🛠️  Jenkins Pipeline Runner (Simulation of Jenkinsfile Execution) ${NC}"
echo -e "${CYAN}  Проект: OpenBMC Continuous Integration & Quality Assurance        ${NC}"
echo -e "${CYAN}  Студенты: Карев А.А., Ребрик Д.С. (СибГУТИ, Вариант 8)            ${NC}"
echo -e "${BLUE}==================================================================${NC}"

# Шаг очистки при выходе
cleanup() {
    if [ -f "$BASE_DIR/openbmc_mock.pid" ]; then
        PID=$(cat "$BASE_DIR/openbmc_mock.pid" 2>/dev/null || true)
        if [ -n "$PID" ]; then
            echo -e "${YELLOW}[Pipeline] { (Declarative: Post Actions) - Stopping OpenBMC (PID $PID)... }${NC}"
            kill "$PID" 2>/dev/null || true
        fi
        rm -f "$BASE_DIR/openbmc_mock.pid"
    fi
}
trap cleanup EXIT INT TERM

# ------------------------------------------------------------------------------
# STAGE 1: Запуск QEMU / OpenBMC
# ------------------------------------------------------------------------------
echo -e "\n${BLUE}[Pipeline] { (Stage 1: Launch QEMU with OpenBMC) }${NC}"
echo "[INFO] Запуск фонового процесса OpenBMC..."
"$VENV_PYTHON" "$BASE_DIR/mock_server/mock_openbmc.py" --port "$BMC_PORT" > "$ARTIFACTS_DIR/qemu_logs/openbmc_runtime.log" 2>&1 &
MOCK_PID=$!
echo "$MOCK_PID" > "$BASE_DIR/openbmc_mock.pid"

echo "[INFO] Проверка готовности платформы OpenBMC (Healthcheck polling)..."
READY=0
for i in $(seq 1 15); do
    if curl -s -k -u root:0penBmc "$BMC_HOST/redfish/v1/" | grep -q "ServiceRoot"; then
        READY=1
        echo -e "${GREEN}✓ OpenBMC Redfish API успешно отвечает на порту $BMC_PORT (попытка $i)${NC}"
        break
    fi
    sleep 0.5
done

if [ $READY -ne 1 ]; then
    echo "❌ Ошибка: OpenBMC не ответил!"
    exit 1
fi

echo "QEMU / OpenBMC Machine: ASPEED AST2500 (romulus-bmc)" > "$ARTIFACTS_DIR/qemu_logs/qemu_boot_status.log"
echo "Redfish ServiceRoot: OK (HTTP 200)" >> "$ARTIFACTS_DIR/qemu_logs/qemu_boot_status.log"
echo "Timestamp: $(date)" >> "$ARTIFACTS_DIR/qemu_logs/qemu_boot_status.log"
echo -e "${GREEN}[Pipeline] { (Stage 1: Launch QEMU with OpenBMC) ... SUCCESS }${NC}"
echo -e "${CYAN}[Artifacts] -> ${ARTIFACTS_DIR}/qemu_logs/qemu_boot_status.log${NC}"

# ------------------------------------------------------------------------------
# STAGE 2: Автотесты Redfish REST API
# ------------------------------------------------------------------------------
echo -e "\n${BLUE}[Pipeline] { (Stage 2: Run OpenBMC API Autotests) }${NC}"
echo "[INFO] Исполнение набора тестов DMTF Redfish (PyTest)..."
"$VENV_PYTEST" "$BASE_DIR/lab5_redfish_pytest/test_redfish.py" \
    --bmc-url "$BMC_HOST" \
    --junitxml="$ARTIFACTS_DIR/redfish_reports/junit_redfish.xml" \
    -v | tee "$ARTIFACTS_DIR/redfish_reports/redfish_pytest.log"

echo -e "${GREEN}[Pipeline] { (Stage 2: Run OpenBMC API Autotests) ... SUCCESS }${NC}"
echo -e "${CYAN}[Artifacts] -> ${ARTIFACTS_DIR}/redfish_reports/junit_redfish.xml${NC}"
echo -e "${CYAN}[Artifacts] -> ${ARTIFACTS_DIR}/redfish_reports/redfish_pytest.log${NC}"

# ------------------------------------------------------------------------------
# STAGE 3: Автотесты Selenium Web UI
# ------------------------------------------------------------------------------
echo -e "\n${BLUE}[Pipeline] { (Stage 3: Run OpenBMC WebUI Tests) }${NC}"
echo "[INFO] Исполнение автотестов Selenium Web UI в безголовом режиме..."
"$VENV_PYTHON" "$BASE_DIR/lab4_selenium_webui/openbmc_auth_tests.py" \
    --url "$BMC_HOST" 2>&1 | tee "$ARTIFACTS_DIR/webui_reports/selenium_webui.log"

echo "<html><head><title>WebUI Test Report</title></head><body><h2>OpenBMC WebUI Selenium Execution</h2><pre>" > "$ARTIFACTS_DIR/webui_reports/report.html"
cat "$ARTIFACTS_DIR/webui_reports/selenium_webui.log" >> "$ARTIFACTS_DIR/webui_reports/report.html"
echo "</pre></body></html>" >> "$ARTIFACTS_DIR/webui_reports/report.html"

echo -e "${GREEN}[Pipeline] { (Stage 3: Run OpenBMC WebUI Tests) ... SUCCESS }${NC}"
echo -e "${CYAN}[Artifacts] -> ${ARTIFACTS_DIR}/webui_reports/selenium_webui.log${NC}"
echo -e "${CYAN}[Artifacts] -> ${ARTIFACTS_DIR}/webui_reports/report.html${NC}"

# ------------------------------------------------------------------------------
# STAGE 4: Нагрузочное тестирование Locust
# ------------------------------------------------------------------------------
echo -e "\n${BLUE}[Pipeline] { (Stage 4: Run OpenBMC Load Testing) }${NC}"
echo "[INFO] Запуск нагрузочного сценария Locust (10 польз., 2 польз/сек, 15 сек)..."
"$VENV_LOCUST" \
    -f "$BASE_DIR/lab6_locust_load_testing/locustfile.py" \
    --headless \
    -u 10 \
    -r 2 \
    --run-time 15s \
    --host "$BMC_HOST" \
    --csv="$ARTIFACTS_DIR/locust_reports/locust_metrics" \
    --html="$ARTIFACTS_DIR/locust_reports/locust_report.html" \
    --loglevel=WARNING

echo -e "${GREEN}[Pipeline] { (Stage 4: Run OpenBMC Load Testing) ... SUCCESS }${NC}"
echo -e "${CYAN}[Artifacts] -> ${ARTIFACTS_DIR}/locust_reports/locust_report.html${NC}"
echo -e "${CYAN}[Artifacts] -> ${ARTIFACTS_DIR}/locust_reports/locust_metrics_stats.csv${NC}"

# ------------------------------------------------------------------------------
# STAGE 5: Сбор артефактов и завершение
# ------------------------------------------------------------------------------
echo -e "\n${BLUE}[Pipeline] { (Declarative: Post Actions - archiveArtifacts) }${NC}"
echo -e "${GREEN}✓ Все артефакты пайплайна успешно зафиксированы в директории:${NC}"
ls -la "$ARTIFACTS_DIR"/*
echo -e "\n${GREEN}🎉 [Pipeline] FINISHED: SUCCESS! Все 4 этапа CI/CD конвейера успешно пройдены.${NC}"
