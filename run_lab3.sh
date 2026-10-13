#!/usr/bin/env bash
cd /Users/alex/openbmc-qa-labs

# Запуск сервера, если еще не запущен
if ! curl -s "http://127.0.0.1:8080/redfish/v1/" > /dev/null 2>&1; then
    ./venv/bin/python mock_server/mock_openbmc.py --port 8080 > /tmp/mock_openbmc.log 2>&1 &
    sleep 1
fi

./venv/bin/python lab3_test_plan/run_lab3_variant8.py
