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

main() {
    local pid=""
    set_home
    pid="$(get_pid)"

    if [[ -z "${pid}" ]]; then
        echo "DASHBOARD is down"
        exit 1
    else
        echo "DASHBOARD is up and running"
        exit 0
    fi
}

main "$@"
