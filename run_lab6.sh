#!/bin/bash
# ==============================================================================
# Лабораторная работа 6: Нагрузочное тестирование с использованием Locust
# Студенты: Карев А.А., Ребрик Д.С. (СибГУТИ, Вариант 8)
# ==============================================================================

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$BASE_DIR/venv/bin/python"
VENV_LOCUST="$BASE_DIR/venv/bin/locust"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ Ошибка: Виртуальное окружение не найдено в $BASE_DIR/venv"
    exit 1
fi

echo "=================================================================="
echo "  🚀 Лабораторная работа №6: Нагрузочное тестирование (Locust)"
echo "  СибГУТИ, Студенты: Карев А.А., Ребрик Д.С. (Вариант 8)"
echo "=================================================================="
echo "Выберите режим запуска:"
echo "  1) Веб-интерфейс Locust (Web UI: http://localhost:8089) [Рекомендуется для защиты]"
echo "  2) Автоматический тест (Headless) + генерация графиков и HTML/PDF отчетов"
echo "  3) Запуск только Mock-сервера OpenBMC (порт 8080)"
echo "=================================================================="
read -p "Введите номер опции [1-3] (по умолчанию: 1): " OPTION
OPTION=${OPTION:-1}

# Проверка, работает ли Mock-сервер
is_mock_running() {
    curl -s http://127.0.0.1:8080/redfish/v1/ > /dev/null 2>&1
}

case "$OPTION" in
    1)
        echo ""
        echo "⚡ Запуск режима Web UI..."
        if ! is_mock_running; then
            echo "-> Запуск автономного OpenBMC Mock Server в фоне..."
            "$VENV_PYTHON" "$BASE_DIR/mock_server/mock_openbmc.py" --port 8080 > /dev/null 2>&1 &
            MOCK_PID=$!
            trap "kill $MOCK_PID 2>/dev/null || true" EXIT
            sleep 1
        else
            echo "-> Mock Server уже активен на http://127.0.0.1:8080"
        fi

        echo "-> Открываем Web UI: http://localhost:8089"
        echo "   В интерфейсе укажите:"
        echo "     Number of users: 10"
        echo "     Ramp up: 2"
        echo "     Host: http://127.0.0.1:8080"
        echo ""
        
        # Автоматическое открытие в браузере
        if command -v open >/dev/null 2>&1; then
            (sleep 2 && open "http://localhost:8089") &
        fi

        "$VENV_LOCUST" -f "$BASE_DIR/lab6_locust_load_testing/locustfile.py" --host http://127.0.0.1:8080
        ;;

    2)
        echo ""
        echo "⚡ Запуск автоматического нагрузочного теста (Headless mode)..."
        "$VENV_PYTHON" "$BASE_DIR/lab6_locust_load_testing/run_locust_analysis.py"
        echo ""
        echo "✅ Готово! Результаты сохранены в:"
        echo "   - Графики: $BASE_DIR/report_assets/"
        echo "   - HTML-отчет: $BASE_DIR/lab6_locust_load_testing/results/locust_report.html"
        ;;

    3)
        echo "⚡ Запуск автономного OpenBMC Mock Server..."
        "$VENV_PYTHON" "$BASE_DIR/mock_server/mock_openbmc.py" --port 8080
        ;;

    *)
        echo "Неверный выбор."
        exit 1
        ;;
esac
