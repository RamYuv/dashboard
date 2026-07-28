#!/bin/bash

set -u

COUNT=10
ts="$(date +"%Y-%m-%d_%H-%M-%S")"
log_file="start_dashboard_${ts}.log"

set_home() {
    export DASHBOARD_HOME="$(cd "$(dirname "$0")" && pwd)"
    if [[ -z "${DASHBOARD_HOME}" ]]; then
        echo "DASHBOARD_HOME is not defined."
        exit 1
    fi

    mkdir -p "${DASHBOARD_HOME}/logs"
    cd "${DASHBOARD_HOME}" || exit 1
}

get_pid() {
    ps -ef | grep -i dashboard | grep run.py | grep -v grep | awk '{print $2}'
}

start_dashboard() {
    local pid=""
    # APP_HOST is the network bind address for Flask. 0.0.0.0 means
    # the app listens on all server interfaces so users can reach it remotely.
    local app_host="${APP_HOST:-0.0.0.0}"
    local app_port="${APP_PORT:-5000}"
    # public_host is only the hostname shown to users in logs/messages.
    # It is not the address Flask binds to.
    local public_host="${APP_PUBLIC_HOST:-$(hostname)}"

    export APP_HOST="${app_host}"
    export APP_PORT="${app_port}"
    export LOG_DIR="${DASHBOARD_HOME}/logs"

    pid="$(get_pid)"

    if [[ -n "${pid}" ]]; then
        echo "DASHBOARD is already running"
        exit 0
    fi

    echo "LOG file: ${DASHBOARD_HOME}/logs/${log_file}"
    echo "${ts}" >> "${DASHBOARD_HOME}/logs/${log_file}"
    echo "Starting dashboard on ${APP_HOST}:${APP_PORT}" | tee -a "${DASHBOARD_HOME}/logs/${log_file}"
    echo "Dashboard URL: http://${public_host}:${APP_PORT}" | tee -a "${DASHBOARD_HOME}/logs/${log_file}"

    while [[ ${COUNT} -ge 1 ]]; do
        if [[ -f "${DASHBOARD_HOME}/dashboard_venv/bin/activate" ]]; then
            # shellcheck disable=SC1091
            source "${DASHBOARD_HOME}/dashboard_venv/bin/activate"
        fi

        "${DASHBOARD_HOME}/dashboard_venv/bin/python3" "${DASHBOARD_HOME}/run.py" >> "${DASHBOARD_HOME}/logs/dashboard_console.log" 2>&1 &
        echo -n "."
        echo -n "." >> "${DASHBOARD_HOME}/logs/${log_file}"
        sleep 20

        pid="$(get_pid)"
        if [[ -n "${pid}" ]]; then
            echo
            echo "DASHBOARD started..."
            {
                date
                echo "DASHBOARD started."
            } >> "${DASHBOARD_HOME}/logs/${log_file}"
            exit 0
        fi

        COUNT=$((COUNT - 1))
    done

    pid="$(get_pid)"
    if [[ ${COUNT} -le 0 && -z "${pid}" ]]; then
        echo
        echo "Failed to start DASHBOARD"
        {
            date
            echo "Failed to start DASHBOARD."
        } >> "${DASHBOARD_HOME}/logs/${log_file}"
        exit 1
    fi
}

main() {
    set_home
    start_dashboard
}

main "$@"
