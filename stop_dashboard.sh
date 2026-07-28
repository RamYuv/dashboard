#!/bin/bash

set -u

set_home() {
    export DASHBOARD_HOME="$(cd "$(dirname "$0")" && pwd)"
    if [[ -z "${DASHBOARD_HOME}" ]]; then
        echo "DASHBOARD_HOME is not defined."
        exit 1
    fi
    cd "${DASHBOARD_HOME}" || exit 1
}

get_pid() {
    ps -ef | grep -i dashboard | grep run.py | grep -v grep | awk '{print $2}'
}

stop_dashboard() {
    local pid_list=""
    pid_list="$(get_pid)"

    if [[ -n "${pid_list}" ]]; then
        echo "Stopping DASHBOARD"
        for pid in ${pid_list}; do
            kill "${pid}"
        done
        sleep 2
        "${DASHBOARD_HOME}/status_dashboard.sh"
    else
        echo "DASHBOARD is already down"
    fi
    exit 0
}

main() {
    set_home
    stop_dashboard
}

main "$@"
