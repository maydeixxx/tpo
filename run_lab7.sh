#!/bin/bash
# ==============================================================================
# Лабораторная работа 7: Настройка CI/CD с использованием GitHub и Jenkins в Docker
# Студенты: Карев А.А., Ребрик Д.С. (СибГУТИ, Вариант 8)
# ==============================================================================

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=================================================================="
echo "  🚀 Лабораторная работа №7: CI/CD Pipeline (Jenkins & Docker)"
echo "  СибГУТИ, Студенты: Карев А.А., Ребрик Д.С. (Вариант 8)"
echo "=================================================================="
echo "Выберите действие:"
echo "  1) Запустить симуляцию Jenkins Pipeline (все 4 шага + сбор артефактов)"
echo "  2) Развернуть Jenkins в Docker контейнере (порт 8085)"
echo "  3) Показать статус и логи Docker Jenkins"
echo "  4) Остановить Jenkins в Docker"
echo "=================================================================="
read -p "Введите номер опции [1-4] (по умолчанию: 1): " OPTION
OPTION=${OPTION:-1}

case "$OPTION" in
    1)
        chmod +x "$BASE_DIR/lab7_ci_cd/simulate_pipeline.sh"
        "$BASE_DIR/lab7_ci_cd/simulate_pipeline.sh"
        ;;

    2)
        echo "⚡ Запуск Jenkins через Docker Compose..."
        cd "$BASE_DIR/lab7_ci_cd"
        docker compose up -d
        echo ""
        echo "✅ Jenkins успешно запущен в фоновом режиме!"
        echo "   Веб-интерфейс доступен по адресу: http://localhost:8085"
        if command -v open >/dev/null 2>&1; then
            echo "   Открываем веб-интерфейс Jenkins..."
            open "http://localhost:8085"
        fi
        ;;

    3)
        cd "$BASE_DIR/lab7_ci_cd"
        docker compose ps
        echo ""
        echo "Последние логи Jenkins:"
        docker compose logs --tail=30
        ;;

    4)
        echo "⚡ Остановка контейнера Jenkins..."
        cd "$BASE_DIR/lab7_ci_cd"
        docker compose down
        echo "✓ Jenkins остановлен."
        ;;

    *)
        echo "Неверный выбор."
        exit 1
        ;;
esac
