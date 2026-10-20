#!/bin/bash
# ==============================================================================
# Скрипт запуска точных команд профилирования по заданию Лабораторной работы №8:
# 1) perf stat -e cycles,instructions,cache-misses qemu-system-arm ...
# 2) vmstat 1
# 3) nmon
# ==============================================================================

set -e

RESULTS_DIR="/workspace/lab8_profiling/results"
mkdir -p "$RESULTS_DIR"

echo "=================================================================="
echo "  [Linux Profiler] Старт сбора метрик QEMU, vmstat и nmon"
echo "=================================================================="

# 1. Запуск сбора метрик хоста через vmstat 1 в фоне
echo "-> [1/3] Запуск мониторинга хоста: vmstat 1..."
vmstat 1 20 > "$RESULTS_DIR/vmstat_host_metrics.log" 2>&1 &
VMSTAT_PID=$!

# 2. Запуск сбора сетевых метрик через nmon в фоне
echo "-> [2/3] Запуск мониторинга сетевых метрик: nmon..."
if command -v nmon >/dev/null 2>&1; then
    nmon -f -s 1 -c 20 -m "$RESULTS_DIR" >/dev/null 2>&1 || true
fi

# 3. Запуск perf stat для QEMU
echo "-> [3/3] Запуск профилирования аппаратных счетчиков perf stat для QEMU..."
echo "Команда: perf stat -e cycles,instructions,cache-misses qemu-system-arm -M romulus-bmc -monitor telnet:127.0.0.1:5555,server,nowait -serial mon:stdio -nographic"

perf stat -e cycles,instructions,cache-misses \
    qemu-system-arm -M romulus-bmc -monitor telnet:127.0.0.1:5555,server,nowait -serial mon:stdio -nographic \
    > "$RESULTS_DIR/qemu_stdout.log" 2> "$RESULTS_DIR/perf_qemu_metrics.log" &
QEMU_PID=$!

# Даем поработать 15 секунд
sleep 15
kill $QEMU_PID 2>/dev/null || true
kill $VMSTAT_PID 2>/dev/null || true

echo "✓ Сбор метрик завершен! Результаты сохранены в $RESULTS_DIR:"
ls -la "$RESULTS_DIR"
