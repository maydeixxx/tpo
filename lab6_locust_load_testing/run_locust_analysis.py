#!/usr/bin/env python3
"""
Скрипт автоматизированного запуска и анализа результатов нагрузочного тестирования (Locust)
по Лабораторной работе №6 для студентов Карева А.А. и Ребрика Д.С. (СибГУТИ, Вариант 8).

Выполняет:
1. Проверку и запуск Mock-сервера OpenBMC (если он не запущен).
2. Запуск Locust в автономном (headless) режиме с параметрами:
   - Количество пользователей: 10
   - Скорость спавна: 2 пользователя/сек
   - Время теста: 25 секунд
3. Сбор и парсинг CSV метрик Locust.
4. Построение графиков нагрузки и времени отклика через matplotlib.
5. Вывод сводного отчета по метрикам и точкам отказа.
"""

import os
import sys
import time
import subprocess
import urllib.request
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LAB6_DIR = os.path.join(BASE_DIR, "lab6_locust_load_testing")
ASSETS_DIR = os.path.join(BASE_DIR, "report_assets")
os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(os.path.join(LAB6_DIR, "results"), exist_ok=True)

BMC_URL = "http://127.0.0.1:8080"
LOCUST_FILE = os.path.join(LAB6_DIR, "locustfile.py")
CSV_PREFIX = os.path.join(LAB6_DIR, "results", "locust_stats")
HTML_REPORT = os.path.join(LAB6_DIR, "results", "locust_report.html")


def is_mock_server_running():
    try:
        with urllib.request.urlopen(f"{BMC_URL}/redfish/v1/", timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_mock_server_if_needed():
    if is_mock_server_running():
        print("✓ Mock-сервер OpenBMC уже запущен на http://127.0.0.1:8080")
        return None

    print("⚡ Запуск автономного Mock-сервера OpenBMC (mock_openbmc.py)...")
    mock_script = os.path.join(BASE_DIR, "mock_server", "mock_openbmc.py")
    proc = subprocess.Popen(
        [sys.executable, mock_script, "--port", "8080"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    # Ожидание старта
    for _ in range(10):
        time.sleep(0.5)
        if is_mock_server_running():
            print("✓ Mock-сервер успешно запущен.")
            return proc
    print("⚠ Не удалось подтвердить запуск Mock-сервера. Продолжаем...")
    return proc


def run_locust_headless(users=10, spawn_rate=2, run_time="25s"):
    print(f"\n============================================================")
    print(f"🚀 Запуск нагрузочного тестирования Locust (Headless)")
    print(f"   Пользователей (Users):      {users}")
    print(f"   Скорость спавна (Rate):     {spawn_rate} польз/сек")
    print(f"   Длительность теста (Time):  {run_time}")
    print(f"   Целевой хост (Host):        {BMC_URL}")
    print(f"============================================================")

    # Очистка старых CSV
    for suffix in ["_stats.csv", "_stats_history.csv", "_failures.csv", "_exceptions.csv"]:
        fpath = CSV_PREFIX + suffix
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
            except Exception:
                pass

    locust_bin = os.path.join(BASE_DIR, "venv", "bin", "locust")
    if not os.path.exists(locust_bin):
        locust_bin = "locust"

    cmd = [
        locust_bin,
        "-f", LOCUST_FILE,
        "--headless",
        "-u", str(users),
        "-r", str(spawn_rate),
        "--run-time", run_time,
        "--host", BMC_URL,
        f"--csv={CSV_PREFIX}",
        f"--html={HTML_REPORT}",
        "--loglevel=WARNING"
    ]

    start_time = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    duration = time.time() - start_time
    print(f"✓ Тестирование завершено за {duration:.1f} сек.")
    return res.returncode


def parse_and_visualize_results():
    stats_file = CSV_PREFIX + "_stats.csv"
    history_file = CSV_PREFIX + "_stats_history.csv"

    if not os.path.exists(stats_file):
        print(f"⚠ Файл статистики {stats_file} не найден!")
        return

    print("\n📊 === Сводные результаты нагрузочного тестирования (Locust) ===")
    print("-" * 105)
    print(f"{'Endpoint':<45} | {'Запросов':<8} | {'Ошибок':<7} | {'% Сбоев':<8} | {'Ср. время':<10} | {'95-й %':<8} | {'RPS':<6}")
    print("-" * 105)

    endpoints = []
    avg_times = []
    p95_times = []
    rps_values = []

    with open(stats_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Name", "")
            req_count = int(row.get("Request Count", 0) or 0)
            fail_count = int(row.get("Failure Count", 0) or 0)
            avg_resp = float(row.get("Average Response Time", 0.0) or 0.0)
            p95 = float(row.get("95%", 0.0) or 0.0)
            rps = float(row.get("Requests/s", 0.0) or 0.0)

            fail_pct = (fail_count / req_count * 100.0) if req_count > 0 else 0.0

            print(f"{name:<45} | {req_count:<8} | {fail_count:<7} | {fail_pct:6.2f}% | {avg_resp:7.2f} ms | {p95:6.1f} ms | {rps:5.1f}")

            if name != "Aggregated":
                short_name = name.replace("[OpenBMC] ", "").replace("[Public API] ", "")
                endpoints.append(short_name)
                avg_times.append(avg_resp)
                p95_times.append(p95)
                rps_values.append(rps)

    print("-" * 105)

    # 1. Построение графика времени отклика по эндпоинтам
    if endpoints:
        plt.figure(figsize=(10, 5))
        bar_width = 0.35
        x = range(len(endpoints))

        plt.bar([i - bar_width/2 for i in x], avg_times, width=bar_width, label="Среднее время (Average ms)", color="#0284c7")
        plt.bar([i + bar_width/2 for i in x], p95_times, width=bar_width, label="95-й перцентиль (p95 ms)", color="#f59e0b")

        plt.xlabel("Тестируемый эндпоинт", fontsize=11, fontweight="bold")
        plt.ylabel("Время отклика, миллисекунды (мс)", fontsize=11, fontweight="bold")
        plt.title("ЛР 6: Время отклика API OpenBMC и Public API при 10 пользователях", fontsize=12, fontweight="bold")
        plt.xticks(x, [e[:25] for e in endpoints], rotation=15, ha="right", fontsize=9)
        plt.grid(axis="y", linestyle="--", alpha=0.6)
        plt.legend(frameon=True)
        plt.tight_layout()

        chart_resp_path = os.path.join(ASSETS_DIR, "lab6_locust_response_times.png")
        plt.savefig(chart_resp_path, dpi=200)
        plt.close()
        print(f"✓ Сохранен график времени отклика: {chart_resp_path}")

    # 2. Построение графика динамики RPS и пользователей во времени из stats_history.csv
    if os.path.exists(history_file):
        timestamps = []
        user_counts = []
        total_rps = []

        with open(history_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            idx = 0
            for row in reader:
                try:
                    u = int(row.get("User Count", 0) or 0)
                    r = float(row.get("Requests/s", 0.0) or 0.0)
                    timestamps.append(idx)
                    user_counts.append(u)
                    total_rps.append(r)
                    idx += 1
                except Exception:
                    pass

        if timestamps:
            fig, ax1 = plt.subplots(figsize=(10, 5))

            color = "#0b4f8a"
            ax1.set_xlabel("Время выполнения теста (секунды)", fontsize=11, fontweight="bold")
            ax1.set_ylabel("Интенсивность запросов (RPS)", color=color, fontsize=11, fontweight="bold")
            line1 = ax1.plot(timestamps, total_rps, color=color, linewidth=2.2, label="Requests per Second (RPS)")
            ax1.tick_params(axis="y", labelcolor=color)
            ax1.grid(True, linestyle="--", alpha=0.5)

            ax2 = ax1.twinx()
            color = "#10b981"
            ax2.set_ylabel("Количество активных пользователей", color=color, fontsize=11, fontweight="bold")
            line2 = ax2.plot(timestamps, user_counts, color=color, linewidth=2.0, linestyle="--", label="Active Users")
            ax2.tick_params(axis="y", labelcolor=color)

            lines = line1 + line2
            labels = [l.get_label() for l in lines]
            ax1.legend(lines, labels, loc="upper left")

            plt.title("ЛР 6: Динамика нагрузки и числа виртуальных пользователей Locust", fontsize=12, fontweight="bold")
            plt.tight_layout()

            chart_rps_path = os.path.join(ASSETS_DIR, "lab6_locust_rps_history.png")
            plt.savefig(chart_rps_path, dpi=200)
            plt.close()
            print(f"✓ Сохранен график динамики нагрузки: {chart_rps_path}")

    print(f"✓ Сформирован интерактивный HTML-отчет: {HTML_REPORT}")


def main():
    mock_proc = start_mock_server_if_needed()
    try:
        run_locust_headless(users=10, spawn_rate=2, run_time="20s")
        parse_and_visualize_results()
    finally:
        if mock_proc:
            print("Остановка временного процесса Mock-сервера...")
            mock_proc.terminate()
            mock_proc.wait()


if __name__ == "__main__":
    main()
