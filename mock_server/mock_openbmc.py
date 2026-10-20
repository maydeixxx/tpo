#!/usr/bin/env python3
"""
Mock OpenBMC Server
Implements:
1. OpenBMC Web UI (Phosphor / Vue-like Interface)
   - Login / Authentication with lock-out on 3 failed attempts
   - Dashboard with Server Power Control
   - Event Logs
   - Sensors / Thermal Monitoring
   - Hardware Inventory (CPU, RAM)
2. Redfish REST API
   - POST /redfish/v1/SessionService/Sessions (Session Creation)
   - GET /redfish/v1/Systems/system (System Info & PowerState)
   - POST /redfish/v1/Systems/system/Actions/ComputerSystem.Reset (Power Control)
   - GET /redfish/v1/Chassis/chassis/Thermal (CPU & System Temperatures)
3. IPMI Sensor Simulation endpoint
"""

import uuid
import datetime
import logging
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, make_response

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MockOpenBMC")

app = Flask(__name__)
app.secret_key = "openbmc-test-secret-key"

# State storage
DEFAULT_STATE = {
    "power_state": "On",
    "failed_logins": {},
    "locked_users": set(),
    "sessions": {},
    "logs": [
        {"timestamp": "2026-10-13 08:00:15", "severity": "Informational", "message": "BMC kernel booted successfully."},
        {"timestamp": "2026-10-13 08:00:20", "severity": "Informational", "message": "Host power status detected: On."},
        {"timestamp": "2026-10-13 08:05:00", "severity": "Informational", "message": "Thermal monitor service initialized."},
    ],
    "sensors": {
        "CPU0_Temp": {"reading": 42.0, "unit": "C", "warn": 75.0, "crit": 85.0, "status": "OK"},
        "CPU1_Temp": {"reading": 43.5, "unit": "C", "warn": 75.0, "crit": 85.0, "status": "OK"},
        "Mobo_12V":  {"reading": 12.08, "unit": "V", "warn": 12.6, "crit": 13.2, "status": "OK"},
        "Fan1_Speed": {"reading": 3600, "unit": "RPM", "warn": 1500, "crit": 1000, "status": "OK"},
    },
    "inventory": {
        "cpu": "Intel(R) Xeon(R) Silver 4214 CPU @ 2.20GHz (12 Cores, 24 Threads)",
        "ram": "64 GB DDR4-2933 ECC Registered (4 x 16GB)",
        "motherboard": "ASRock Rack E3C246D4I (BMC Firmware: 2.14.0-openbmc)"
    }
}

server_state = dict(DEFAULT_STATE)

VALID_USERNAME = "root"
VALID_PASSWORD = "0penBmc"
MAX_FAILED_ATTEMPTS = 3

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ title }} - OpenBMC Web UI</title>
    <style>
        :root {
            --primary: #007bff;
            --success: #28a745;
            --danger: #dc3545;
            --dark: #1e2229;
            --light: #f8f9fa;
            --card-bg: #ffffff;
            --border: #dee2e6;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f1f3f6;
            margin: 0;
            padding: 0;
            color: #333;
        }
        .header {
            background-color: var(--dark);
            color: white;
            padding: 12px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header .logo {
            font-size: 20px;
            font-weight: bold;
            color: #4fc3f7;
            text-decoration: none;
        }
        .header .user-info {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .nav-bar {
            background: #2d333b;
            display: flex;
            padding: 0 20px;
        }
        .nav-bar a {
            color: #c9d1d9;
            text-decoration: none;
            padding: 12px 18px;
            font-size: 14px;
            font-weight: 500;
        }
        .nav-bar a:hover, .nav-bar a.active {
            background-color: #404754;
            color: #ffffff;
            border-bottom: 3px solid #4fc3f7;
        }
        .container {
            max-width: 1100px;
            margin: 30px auto;
            padding: 0 20px;
        }
        .card {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            padding: 24px;
            margin-bottom: 24px;
        }
        .card h2 {
            margin-top: 0;
            border-bottom: 2px solid var(--border);
            padding-bottom: 12px;
            color: #2c3e50;
        }
        .alert {
            padding: 14px 20px;
            border-radius: 6px;
            margin-bottom: 20px;
            font-size: 14px;
        }
        .alert-danger { background: #ffebee; color: #c62828; border: 1px solid #ef9a9a; }
        .alert-success { background: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }
        .alert-warning { background: #fff8e1; color: #f57f17; border: 1px solid #ffe082; }
        
        .btn {
            padding: 10px 20px;
            border-radius: 5px;
            border: none;
            cursor: pointer;
            font-weight: 600;
            font-size: 14px;
            transition: 0.2s;
        }
        .btn-primary { background: var(--primary); color: white; }
        .btn-success { background: var(--success); color: white; }
        .btn-danger { background: var(--danger); color: white; }
        .btn-secondary { background: #6c757d; color: white; }
        .btn:hover { opacity: 0.9; }

        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; margin-bottom: 6px; font-weight: 600; }
        .form-control {
            width: 100%;
            max-width: 400px;
            padding: 10px 12px;
            border: 1px solid #ccc;
            border-radius: 4px;
            font-size: 14px;
            box-sizing: border-box;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        th, td {
            text-align: left;
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
        }
        th { background: #f8f9fa; color: #495057; font-weight: 600; }
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        }
        .badge-success { background: #d4edda; color: #155724; }
        .badge-danger { background: #f8d7da; color: #721c24; }
        .badge-info { background: #d1ecf1; color: #0c5460; }
    </style>
</head>
<body>
    <header class="header">
        <a href="/" class="logo">⚡ OpenBMC Control Dashboard</a>
        <div class="user-info">
            {% if logged_in %}
                <span>User: <strong id="current-user">root</strong></span>
                <a href="/logout" id="btn-logout" class="btn btn-secondary" style="padding: 6px 12px; font-size: 12px; text-decoration: none;">Sign Out</a>
            {% else %}
                <span>Baseboard Management Controller (Mock)</span>
            {% endif %}
        </div>
    </header>

    {% if logged_in %}
    <nav class="nav-bar">
        <a href="/dashboard" id="nav-overview" class="{% if page == 'dashboard' %}active{% endif %}">Overview</a>
        <a href="/server-control" id="nav-server-control" class="{% if page == 'server-control' %}active{% endif %}">Server Power Operations</a>
        <a href="/logs" id="nav-logs" class="{% if page == 'logs' %}active{% endif %}">Event Log</a>
        <a href="/sensors" id="nav-sensors" class="{% if page == 'sensors' %}active{% endif %}">Sensors & Thermal</a>
        <a href="/inventory" id="nav-inventory" class="{% if page == 'inventory' %}active{% endif %}">Hardware Inventory</a>
    </nav>
    {% endif %}

    <div class="container">
        {% if alert_error %}
            <div id="error-alert" class="alert alert-danger">{{ alert_error }}</div>
        {% endif %}
        {% if alert_lockout %}
            <div id="lockout-alert" class="alert alert-danger">{{ alert_lockout }}</div>
        {% endif %}
        {% if alert_success %}
            <div id="success-alert" class="alert alert-success">{{ alert_success }}</div>
        {% endif %}

        {% if page == 'login' %}
            <div class="card" style="max-width: 440px; margin: 60px auto;">
                <h2>OpenBMC Login</h2>
                <form method="POST" action="/login" id="login-form">
                    <div class="form-group">
                        <label for="username">Username</label>
                        <input type="text" id="username" name="username" class="form-control" placeholder="Enter username (root)" required autocomplete="username">
                    </div>
                    <div class="form-group">
                        <label for="password">Password</label>
                        <input type="password" id="password" name="password" class="form-control" placeholder="Enter password (0penBmc)" required autocomplete="current-password">
                    </div>
                    <div style="margin-top: 20px;">
                        <button type="submit" id="login-button" class="btn btn-primary" style="width: 100%;">Sign in</button>
                    </div>
                </form>
                <div style="margin-top: 15px; font-size: 12px; color: #666; text-align: center;">
                    Default credentials: <code>root</code> / <code>0penBmc</code>
                </div>
            </div>

        {% elif page == 'dashboard' or page == 'server-control' %}
            <div class="card">
                <h2>Server Power Operations</h2>
                <p>Manage physical host power state through OpenBMC chassis controller.</p>
                <div style="margin: 20px 0; font-size: 16px;">
                    Current Host State: 
                    <span id="host-status" class="badge {% if state.power_state == 'On' %}badge-success{% else %}badge-danger{% endif %}">
                        {{ state.power_state }}
                    </span>
                </div>
                <div style="display: flex; gap: 15px;">
                    <form method="POST" action="/api/power/on">
                        <button type="submit" id="btn-power-on" class="btn btn-success" {% if state.power_state == 'On' %}disabled{% endif %}>Power On Server</button>
                    </form>
                    <form method="POST" action="/api/power/off">
                        <button type="submit" id="btn-power-off" class="btn btn-danger" {% if state.power_state == 'Off' %}disabled{% endif %}>Power Off Server</button>
                    </form>
                    <form method="POST" action="/api/power/reboot">
                        <button type="submit" id="btn-reboot" class="btn btn-secondary">Reboot Server</button>
                    </form>
                </div>
            </div>

            {% if page == 'dashboard' %}
            <div class="card">
                <h2>System Health Summary</h2>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;">
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 6px;">
                        <div style="font-size: 13px; color: #666;">BMC Status</div>
                        <div style="font-size: 20px; font-weight: bold; color: #28a745;">Online</div>
                    </div>
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 6px;">
                        <div style="font-size: 13px; color: #666;">CPU0 Temp</div>
                        <div style="font-size: 20px; font-weight: bold;">{{ state.sensors.CPU0_Temp.reading }} °C</div>
                    </div>
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 6px;">
                        <div style="font-size: 13px; color: #666;">Active Alerts</div>
                        <div style="font-size: 20px; font-weight: bold; color: #28a745;">0 Critical</div>
                    </div>
                </div>
            </div>
            {% endif %}

        {% elif page == 'logs' %}
            <div class="card">
                <h2>System Event Logs (SEL)</h2>
                <p>History of system, BMC power events, and security access logs.</p>
                <table id="logs-table">
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Severity</th>
                            <th>Event Description</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for log in state.logs | reverse %}
                        <tr class="log-entry">
                            <td class="log-timestamp">{{ log.timestamp }}</td>
                            <td><span class="badge badge-info">{{ log.severity }}</span></td>
                            <td class="log-message">{{ log.message }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>

        {% elif page == 'sensors' %}
            <div class="card">
                <h2>Sensors & Thermal Monitoring</h2>
                <p>Real-time readings from hardware thermal and voltage sensors.</p>
                <table id="sensors-table">
                    <thead>
                        <tr>
                            <th>Sensor Name</th>
                            <th>Current Reading</th>
                            <th>Warning Threshold</th>
                            <th>Critical Threshold</th>
                            <th>Health Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for name, s in state.sensors.items() %}
                        <tr id="sensor-row-{{ name }}">
                            <td><strong>{{ name }}</strong></td>
                            <td id="sensor-{{ name|lower }}-temp" class="sensor-reading">{{ s.reading }} {{ s.unit }}</td>
                            <td>{{ s.warn }} {{ s.unit }}</td>
                            <td>{{ s.crit }} {{ s.unit }}</td>
                            <td><span class="badge badge-success">{{ s.status }}</span></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>

        {% elif page == 'inventory' %}
            <div class="card">
                <h2>Hardware Inventory</h2>
                <p>Field Replaceable Units (FRU) and detected system hardware.</p>
                <table id="inventory-table">
                    <tbody>
                        <tr>
                            <th style="width: 250px;">Processor (CPU)</th>
                            <td id="cpu-model">{{ state.inventory.cpu }}</td>
                        </tr>
                        <tr>
                            <th>System Memory (RAM)</th>
                            <td id="ram-total">{{ state.inventory.ram }}</td>
                        </tr>
                        <tr>
                            <th>Mainboard / Chassis</th>
                            <td id="mb-model">{{ state.inventory.motherboard }}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        {% endif %}
    </div>
</body>
</html>
"""

def add_log_event(message, severity="Informational"):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    server_state["logs"].append({
        "timestamp": ts,
        "severity": severity,
        "message": message
    })
    logger.info(f"LOG EVENT [{severity}]: {message}")

# --- WEB UI ROUTES ---

@app.route("/")
def index():
    auth_cookie = request.cookies.get("openbmc_session")
    if auth_cookie in server_state["sessions"]:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    alert_error = None
    alert_lockout = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # Check if user is already locked
        if username in server_state["locked_users"]:
            alert_lockout = "Account is locked due to too many failed login attempts. Please try again later."
            add_log_event(f"Rejected login attempt for locked account '{username}'.", severity="Warning")
            return render_template_string(HTML_TEMPLATE, title="Login", page="login", logged_in=False, alert_lockout=alert_lockout), 403

        # Validate credentials
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            # Reset failed count
            server_state["failed_logins"][username] = 0
            session_id = str(uuid.uuid4())
            server_state["sessions"][session_id] = username
            add_log_event(f"User '{username}' successfully authenticated via Web UI.")
            resp = make_response(redirect(url_for("dashboard")))
            resp.set_cookie("openbmc_session", session_id)
            return resp
        else:
            # Increment failed attempts
            fails = server_state["failed_logins"].get(username, 0) + 1
            server_state["failed_logins"][username] = fails
            add_log_event(f"Failed login attempt for user '{username}' (Attempt {fails}/{MAX_FAILED_ATTEMPTS}).", severity="Warning")

            if fails >= MAX_FAILED_ATTEMPTS:
                server_state["locked_users"].add(username)
                alert_lockout = "Account is locked due to too many failed login attempts. Please try again later."
                add_log_event(f"Security Lockout: Account '{username}' has been locked out after {fails} failed attempts.", severity="Critical")
                return render_template_string(HTML_TEMPLATE, title="Login", page="login", logged_in=False, alert_lockout=alert_lockout), 403
            else:
                alert_error = "Invalid username or password. Please try again."
                return render_template_string(HTML_TEMPLATE, title="Login", page="login", logged_in=False, alert_error=alert_error), 401

    return render_template_string(HTML_TEMPLATE, title="Login", page="login", logged_in=False)

@app.route("/logout")
def logout():
    session_id = request.cookies.get("openbmc_session")
    if session_id in server_state["sessions"]:
        username = server_state["sessions"].pop(session_id, "root")
        add_log_event(f"User '{username}' logged out.")
    resp = make_response(redirect(url_for("login")))
    resp.delete_cookie("openbmc_session")
    return resp

def require_auth(page_func):
    def wrapper(*args, **kwargs):
        session_id = request.cookies.get("openbmc_session")
        if session_id not in server_state["sessions"]:
            return redirect(url_for("login"))
        return page_func(*args, **kwargs)
    wrapper.__name__ = page_func.__name__
    return wrapper

@app.route("/dashboard")
@require_auth
def dashboard():
    return render_template_string(HTML_TEMPLATE, title="Dashboard", page="dashboard", logged_in=True, state=server_state)

@app.route("/server-control")
@require_auth
def server_control():
    return render_template_string(HTML_TEMPLATE, title="Server Control", page="server-control", logged_in=True, state=server_state)

@app.route("/logs")
@require_auth
def logs():
    return render_template_string(HTML_TEMPLATE, title="Event Logs", page="logs", logged_in=True, state=server_state)

@app.route("/sensors")
@require_auth
def sensors():
    return render_template_string(HTML_TEMPLATE, title="Sensors", page="sensors", logged_in=True, state=server_state)

@app.route("/inventory")
@require_auth
def inventory():
    return render_template_string(HTML_TEMPLATE, title="Inventory", page="inventory", logged_in=True, state=server_state)

@app.route("/api/power/on", methods=["POST"])
@require_auth
def ui_power_on():
    server_state["power_state"] = "On"
    add_log_event("Host power on requested via Web UI. Host PowerState is now On.")
    return redirect(request.referrer or url_for("dashboard"))

@app.route("/api/power/off", methods=["POST"])
@require_auth
def ui_power_off():
    server_state["power_state"] = "Off"
    add_log_event("Host power off requested via Web UI. Host PowerState is now Off.")
    return redirect(request.referrer or url_for("dashboard"))

@app.route("/api/power/reboot", methods=["POST"])
@require_auth
def ui_power_reboot():
    server_state["power_state"] = "On"
    add_log_event("Host power reset/cycle requested via Web UI. Host PowerState is now On.")
    return redirect(request.referrer or url_for("dashboard"))

# --- REDFISH REST API ROUTES ---

@app.route("/redfish/v1/", methods=["GET"])
def redfish_root():
    return jsonify({
        "@odata.type": "#ServiceRoot.v1_5_0.ServiceRoot",
        "Id": "RootService",
        "Name": "Root Service",
        "RedfishVersion": "1.8.0",
        "SessionService": {"@odata.id": "/redfish/v1/SessionService"},
        "Systems": {"@odata.id": "/redfish/v1/Systems"},
        "Chassis": {"@odata.id": "/redfish/v1/Chassis"}
    }), 200

@app.route("/redfish/v1/SessionService/Sessions", methods=["POST"])
def redfish_create_session():
    data = request.get_json(force=True, silent=True) or {}
    username = data.get("UserName")
    password = data.get("Password")

    if username == VALID_USERNAME and password == VALID_PASSWORD:
        token = "token-" + uuid.uuid4().hex
        session_id = str(len(server_state["sessions"]) + 1)
        server_state["sessions"][token] = username
        add_log_event(f"Redfish API session created for user '{username}'.")

        response = make_response(jsonify({
            "@odata.id": f"/redfish/v1/SessionService/Sessions/{session_id}",
            "@odata.type": "#Session.v1_3_0.Session",
            "Id": session_id,
            "Name": "User Session",
            "UserName": username,
            "SessionToken": token
        }), 200)
        response.headers["X-Auth-Token"] = token
        response.headers["Location"] = f"/redfish/v1/SessionService/Sessions/{session_id}"
        return response
    else:
        add_log_event(f"Redfish API failed authentication attempt for user '{username}'.", severity="Warning")
        return jsonify({
            "error": {
                "code": "Base.1.8.0.GeneralError",
                "message": "Invalid credentials provided."
            }
        }), 401

@app.route("/redfish/v1/Systems/system", methods=["GET"])
def redfish_get_system():
    # Verify auth token if provided, or allow basic auth
    auth_header = request.headers.get("X-Auth-Token")
    auth_basic = request.authorization
    if not auth_header and not (auth_basic and auth_basic.username == VALID_USERNAME and auth_basic.password == VALID_PASSWORD):
        # Even without token, check if token in session
        if auth_header not in server_state["sessions"] and request.headers.get("Authorization") is None:
            # Let's check token validity
            pass

    return jsonify({
        "@odata.id": "/redfish/v1/Systems/system",
        "@odata.type": "#ComputerSystem.v1_13_0.ComputerSystem",
        "Id": "system",
        "Name": "OpenBMC Computer System",
        "SystemType": "Physical",
        "Manufacturer": "OpenBMC",
        "Model": "Reference Server Platform",
        "PowerState": server_state["power_state"],
        "Status": {
            "State": "Enabled",
            "Health": "OK"
        },
        "ProcessorSummary": {
            "Count": 2,
            "Model": server_state["inventory"]["cpu"],
            "Status": {"Health": "OK"}
        },
        "MemorySummary": {
            "TotalSystemMemoryGiB": 64,
            "Status": {"Health": "OK"}
        },
        "Actions": {
            "#ComputerSystem.Reset": {
                "target": "/redfish/v1/Systems/system/Actions/ComputerSystem.Reset",
                "ResetType@Redfish.AllowableValues": ["On", "ForceOff", "GracefulShutdown", "GracefulRestart", "ForceRestart"]
            }
        }
    }), 200

@app.route("/redfish/v1/Systems/system/PowerState", methods=["GET"])
@app.route("/redfish/v1/Systems/system/Power", methods=["GET"])
def redfish_get_power_state():
    return jsonify({
        "@odata.id": "/redfish/v1/Systems/system/PowerState",
        "PowerState": server_state["power_state"],
        "Status": {"State": "Enabled", "Health": "OK"}
    }), 200

@app.route("/redfish/v1/Systems/system/Actions/ComputerSystem.Reset", methods=["POST"])
def redfish_system_reset():
    data = request.get_json(force=True, silent=True) or {}
    reset_type = data.get("ResetType", "On")

    if reset_type in ["On"]:
        server_state["power_state"] = "On"
    elif reset_type in ["ForceOff", "GracefulShutdown"]:
        server_state["power_state"] = "Off"
    elif reset_type in ["GracefulRestart", "ForceRestart"]:
        server_state["power_state"] = "On"

    add_log_event(f"Redfish Reset action executed: '{reset_type}'. System PowerState is now '{server_state['power_state']}'.")
    return jsonify({
        "@odata.type": "#Task.v1_4_3.Task",
        "Id": "task-reset-1",
        "TaskState": "Completed",
        "TaskStatus": "OK"
    }), 202

@app.route("/redfish/v1/Chassis/chassis/Thermal", methods=["GET"])
@app.route("/redfish/v1/Chassis/system/Thermal", methods=["GET"])
def redfish_get_thermal():
    temperatures = []
    for idx, (sensor_id, s) in enumerate(server_state["sensors"].items()):
        temperatures.append({
            "@odata.id": f"/redfish/v1/Chassis/chassis/Thermal#/Temperatures/{idx}",
            "MemberId": sensor_id,
            "Name": f"{sensor_id} Sensor",
            "SensorNumber": idx + 1,
            "ReadingCelsius": s["reading"],
            "UpperThresholdNonCritical": s["warn"],
            "UpperThresholdCritical": s["crit"],
            "Status": {
                "State": "Enabled",
                "Health": s["status"]
            }
        })

    return jsonify({
        "@odata.id": "/redfish/v1/Chassis/chassis/Thermal",
        "@odata.type": "#Thermal.v1_7_0.Thermal",
        "Id": "Thermal",
        "Name": "Thermal",
        "Temperatures": temperatures
    }), 200

# Endpoint to simulate IPMI reading for CPU temperature comparison
@app.route("/api/mock/ipmi/cpu_temp", methods=["GET"])
def mock_ipmi_cpu_temp():
    return jsonify({
        "sensor_name": "CPU0_Temp",
        "reading_celsius": server_state["sensors"]["CPU0_Temp"]["reading"],
        "unit": "degrees C",
        "status": "ok"
    }), 200

# Utility endpoint to reset mock server state between tests
@app.route("/api/mock/reset", methods=["POST"])
def mock_reset():
    server_state["power_state"] = "On"
    server_state["failed_logins"].clear()
    server_state["locked_users"].clear()
    server_state["sessions"].clear()
    add_log_event("Mock server state reset to defaults.")
    return jsonify({"status": "reset_successful"}), 200

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Mock OpenBMC Server for QA Testing")
    parser.add_argument("--port", type=int, default=8080, help="HTTP Port to listen on (default: 8080)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    args = parser.parse_args()

    print(f"============================================================")
    print(f"🚀 Starting OpenBMC Mock Server at http://{args.host}:{args.port}")
    print(f"   - Web UI Login:     http://{args.host}:{args.port}/login")
    print(f"   - Redfish Root:     http://{args.host}:{args.port}/redfish/v1/")
    print(f"   - Default Login:    root / 0penBmc")
    print(f"============================================================")
    app.run(host=args.host, port=args.port, debug=False)
