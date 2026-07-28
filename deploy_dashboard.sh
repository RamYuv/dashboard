#!/bin/bash

set -u

ts="$(date +"%Y-%m-%d_%H-%M-%S")"
log_file="deploy_envdashboard_${ts}.log"

CURR_DIR=""
DEP_DIR=""
PREV_LINK=""
NEW_LINK=""
DASHBOARD_HOME=""
LOG_DIR=""

log_info() {
    local message="$1"
    echo "$message"
    if [[ -n "${LOG_DIR}" ]]; then
        echo "$message" >> "${LOG_DIR}/${log_file}"
    fi
}

set_dep_dir() {
    CURR_DIR="$(cd "$(dirname "$0")" && pwd)"
    LOG_DIR="${CURR_DIR}/logs"

    if [[ ! -d "${LOG_DIR}" ]]; then
        mkdir -p "${LOG_DIR}"
    fi

    log_info "Deployment Log file: ${LOG_DIR}/${log_file}"
    DEP_DIR="$(dirname "${CURR_DIR}")"

    if [[ -z "${DEP_DIR}" || ! -d "${DEP_DIR}" ]]; then
        log_info "Failed to set Deployment Directory: ${DEP_DIR}. Cannot proceed."
        exit 1
    fi

    {
        echo "=============================================="
        date
        echo
        echo "Starting DASHBOARD deployment for:"
        echo
        if [[ -f "${CURR_DIR}/version.txt" ]]; then
            cat "${CURR_DIR}/version.txt"
        else
            echo "version.txt not found."
        fi
        echo
        echo "=============================================="
    } >> "${LOG_DIR}/${log_file}"

    update_link
}

update_link() {
    log_info "Updating symlink for DASHBOARD."
    cd "${DEP_DIR}" || exit 1

    if [[ -L dashboard_server || -e dashboard_server ]]; then
        PREV_LINK="$(readlink dashboard_server 2>/dev/null || true)"
        if [[ -n "${PREV_LINK}" ]]; then
            echo "Previous link: ${PREV_LINK}" >> "${LOG_DIR}/${log_file}"
        fi
        rm -f dashboard_server
    fi

    ln -s "${CURR_DIR}" dashboard_server
    NEW_LINK="$(readlink dashboard_server)"
    DASHBOARD_HOME="${DEP_DIR}/dashboard_server"
    export DASHBOARD_HOME

    {
        echo "New Link: ${NEW_LINK}"
        echo "DASHBOARD_HOME set to: ${DASHBOARD_HOME}"
    } >> "${LOG_DIR}/${log_file}"

    cd "${CURR_DIR}" || exit 1
}

db_backup() {
    log_info "Trying to take database backup if it exists."
    if [[ -n "${PREV_LINK}" && -f "${PREV_LINK}/dashboard.db" ]]; then
        cp "${PREV_LINK}/dashboard.db" "${CURR_DIR}/"
        log_info "Copied previous dashboard.db into current release."
    else
        log_info "No previous DASHBOARD db found. Skipping backup."
    fi
}

deploy_db() {
    db_backup
    log_info "Calling dashboard_db.py"
    python3 "${CURR_DIR}/dashboard_db.py"
    if [[ $? -eq 0 ]]; then
        log_info "DASHBOARD DB deployment completed successfully."
    else
        log_info "There is an error in DASHBOARD DB deployment."
        log_info "Cannot progress further."
        exit 1
    fi
}

run_migration() {
    log_info "Running dashboard data migration."
    python3 "${CURR_DIR}/dashboard_migrate.py"
    if [[ $? -eq 0 ]]; then
        log_info "Dashboard data migration completed successfully."
    else
        log_info "Dashboard data migration failed."
        exit 1
    fi
}

update_config() {
    local site_packages_path=""

    log_info "Setting up virtual environment. This may take some time."
    python3 -m venv "${DASHBOARD_HOME}/dashboard_venv" --system-site-packages || exit 1

    if [[ -d "${DASHBOARD_HOME}/dashboard_dist" ]]; then
        site_packages_path="$("${DASHBOARD_HOME}/dashboard_venv/bin/python3" -c 'import site; paths = [p for p in site.getsitepackages() if p.endswith("site-packages")]; print(paths[0] if paths else "")')"
        if [[ -n "${site_packages_path}" && -d "${site_packages_path}" ]]; then
            log_info "Copying dashboard_dist into virtual environment site-packages."
            cp -r "${DASHBOARD_HOME}/dashboard_dist/." "${site_packages_path}/"
        else
            log_info "Unable to resolve site-packages path. Skipping dashboard_dist copy."
        fi
    else
        log_info "dashboard_dist directory not found. Skipping package copy."
    fi
}

update_crontab() {
    log_info "Updating crontab to start DASHBOARD."
    (crontab -l 2>/dev/null | grep -F "${DASHBOARD_HOME}/start_dashboard.sh" >/dev/null)
    if [[ $? -ne 0 ]]; then
        (crontab -l 2>/dev/null; echo "1 1 * * * ${DASHBOARD_HOME}/start_dashboard.sh") | crontab -
    fi

    if [[ $? -ne 0 ]]; then
        log_info "Failed to add crontab entry automatically for DASHBOARD startup. Try manual entry."
    fi

    log_info "Updating crontab for dashboard database backup."
    (crontab -l 2>/dev/null | grep -F "${DASHBOARD_HOME}/backup_dashboard_db.sh" >/dev/null)
    if [[ $? -ne 0 ]]; then
        (crontab -l 2>/dev/null; echo "30 23 * * * ${DASHBOARD_HOME}/backup_dashboard_db.sh") | crontab -
    fi

    if [[ $? -ne 0 ]]; then
        log_info "Failed to add crontab entry automatically for dashboard database backup. Try manual entry."
    fi
}

main() {
    set_dep_dir
    log_info "Stopping DASHBOARD (if already running)."
    if [[ -x "${CURR_DIR}/stop_dashboard.sh" ]]; then
        "${CURR_DIR}/stop_dashboard.sh"
    else
        log_info "stop_dashboard.sh not found or not executable. Skipping stop step."
    fi

    update_config
    deploy_db
    run_migration
    update_crontab

    log_info "DASHBOARD deployment completed."
    log_info "Starting DASHBOARD. This may take some time."
    if [[ -x "${CURR_DIR}/start_dashboard.sh" ]]; then
        "${CURR_DIR}/start_dashboard.sh"
    else
        log_info "start_dashboard.sh not found or not executable."
        exit 1
    fi
    date >> "${LOG_DIR}/${log_file}"
}

main "$@"
exit 0
