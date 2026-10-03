#!/bin/bash

set -u
ts=`date +"%Y-%m-%d_%H-%M-%S"`
log_file="deploy_envdashboard_${ts}.log"
PREV_LINK=""
PREV_LINK_TARGET=""
LINK_SWITCHED=0
DEPLOY_SUCCESS=0
TEMP_LINK=""

set_dep_dir()
{
    CURR_DIR=`dirname "$(realpath "$0")"`
	
	if [ ! -d "$CURR_DIR/logs" ]; then
	    mkdir -p "$CURR_DIR/logs" || exit 1
	fi
	
	echo "Deployment Log file: $CURR_DIR/logs/$log_file"
	export DEP_DIR="$(dirname "$CURR_DIR")"
	
	if [[ -z $DEP_DIR || ! -d $DEP_DIR ]]; then
	    echo "Failed to set Deployment Directory: $DEP_DIR. Cannot proceed."
		echo "Failed to set Deployment Directory: $DEP_DIR. Cannot proceed." >> "$CURR_DIR/logs/$log_file"
		exit 1
	else
	    echo "==============================================" >> "$CURR_DIR/logs/$log_file"
		echo `date` >> "$CURR_DIR/logs/$log_file"
		echo " " >> "$CURR_DIR/logs/$log_file"
		echo "Starting DASHBOARD deployement for: " >> "$CURR_DIR/logs/$log_file"
		echo " " >> "$CURR_DIR/logs/$log_file"
		cat "$CURR_DIR/version.txt" >> "$CURR_DIR/logs/$log_file"
		echo " " >> "$CURR_DIR/logs/$log_file"
		echo "===========================================" >> "$CURR_DIR/logs/$log_file"
		capture_previous_release
	fi
}

capture_previous_release()
{
    if [ -L "$DEP_DIR/dashboard_server" ]; then
        PREV_LINK_TARGET=$(readlink "$DEP_DIR/dashboard_server") || exit 1
        PREV_LINK=$(realpath "$DEP_DIR/dashboard_server") || exit 1
    elif [ -e "$DEP_DIR/dashboard_server" ]; then
        echo "dashboard_server exists and is not a symlink. Cannot proceed." >&2
        exit 1
    fi
    # Prepare and migrate using the candidate release, leaving the live link alone.
    export DASHBOARD_HOME="$CURR_DIR"
    cd "$CURR_DIR" || exit 1
}

update_link()
{
    TEMP_LINK="$DEP_DIR/.dashboard_server.deploy.$$"
    ln -s "$CURR_DIR" "$TEMP_LINK" || exit 1
    mv -Tf "$TEMP_LINK" "$DEP_DIR/dashboard_server" || exit 1
    LINK_SWITCHED=1
    TEMP_LINK=""
    export DASHBOARD_HOME="$DEP_DIR/dashboard_server"
    echo "New Link: $CURR_DIR" >> "$CURR_DIR/logs/$log_file"
}

finish_deployment()
{
    local result=$?
    trap - EXIT
    if [[ "$DEPLOY_SUCCESS" -ne 1 && "$LINK_SWITCHED" -eq 1 ]]; then
        echo "Deployment failed; restoring previous release link." >&2
        if [[ -n "$PREV_LINK_TARGET" ]]; then
            TEMP_LINK="$DEP_DIR/.dashboard_server.rollback.$$"
            if ln -s "$PREV_LINK_TARGET" "$TEMP_LINK"; then
                mv -Tf "$TEMP_LINK" "$DEP_DIR/dashboard_server" || result=1
            else
                result=1
            fi
        else
            unlink "$DEP_DIR/dashboard_server" || result=1
        fi
        # Database migrations are not reversed, and services are not auto-restarted.
    fi
    if [[ -n "$TEMP_LINK" && -L "$TEMP_LINK" ]]; then
        unlink "$TEMP_LINK"
    fi
    exit "$result"
}

db_backup()
{
    echo "Trying to take Database backup if exist" >>  $CURR_DIR/logs/$log_file
	if [[ -n "${DATABASE_URL:-}" ]]; then
	    return
	fi
	if [[ -n "$PREV_LINK" && -f "$PREV_LINK/dashboard.db" ]]; then 
	    "${DASHBOARD_HOME}/dashboard_venv/bin/python3" "$CURR_DIR/dashboard_db.py" --copy-sqlite \
	        "$PREV_LINK/dashboard.db" "$CURR_DIR/dashboard.db" || exit 1
	else
	    echo "No Previous DASHBOARD db found. Skipping back." >> "$CURR_DIR/logs/$log_file"
	fi
}

deploy_db()
{
    db_backup
	echo "Calling deploy_db" >> "$CURR_DIR/logs/$log_file"
	"${DASHBOARD_HOME}/dashboard_venv/bin/python3" "$CURR_DIR/dashboard_db.py"
	if [[ $? == 0 ]];then
	    echo "DASHBOARD DB  Deployment Successfully. " >> "$CURR_DIR/logs/$log_file"
	else
	    echo "There is an error in DASHBOARD DB Deployment." >> "$CURR_DIR/logs/$log_file"
		echo "Cannot progress futher..." >> "$CURR_DIR/logs/$log_file"
		exit 1
	fi
}

update_config()
{
	echo "Setting up Virtual environment. This may take some time" >> "$CURR_DIR/logs/$log_file"
	echo "Setting update environment. This may take some time..."
	python3 -m venv "${DASHBOARD_HOME}/dashboard_venv" --system-site-packages || exit 1
    echo "Copying dashboard_dist to dashboard_env." >> "$CURR_DIR/logs/$log_file"
	cp -r "${DASHBOARD_HOME}/dashboard_dist/"* "${DASHBOARD_HOME}/dashboard_venv/lib/python3.6/site-packages/" || exit 1
}

update_crontab()
{
    local cron_status=0
    # Cron has no deployment shell environment. Only schedule the default local DB.
    if [[ -z "${DATABASE_URL:-}" ]]; then
        local checkpoint_job="*/30 * * * * \"${DASHBOARD_HOME}/dashboard_venv/bin/python3\" \"${DASHBOARD_HOME}/checkpoint_dashboard_db.py\" >> \"${DASHBOARD_HOME}/logs/checkpoint_dashboard_db.log\" 2>&1"
        if ! (crontab -l 2>/dev/null | grep -Fqx "$checkpoint_job"); then
            (crontab -l 2>/dev/null; echo "$checkpoint_job") | crontab - || {
                echo "Failed to install dashboard checkpoint cron job." >&2
                exit 1
            }
        fi
    else
        echo "Custom DATABASE_URL: configure its checkpoint schedule separately." >> "$CURR_DIR/logs/$log_file"
    fi
    echo "Updating crontab to start DASHBOARD" >> "$CURR_DIR/logs/$log_file"
	(crontab -l 2>/dev/null | grep -Fqx "1 1 * * * ${DASHBOARD_HOME}/start_dashboard.sh")
	if [ $? -ne 0 ];then
    	(crontab -l 2>/dev/null; echo "1 1 * * * ${DASHBOARD_HOME}/start_dashboard.sh") | crontab - || cron_status=$?
	fi
	
	if [ "$cron_status" -ne 0 ]; then
	    echo "Failed to do crontab entry automatically for  DASHBOARD startup: " >> "$CURR_DIR/logs/$log_file"
		echo "Try manual entry." >> "$CURR_DIR/logs/$log_file"
		echo "Failed to do crontab entry automatically for DASHBOARD startup:"
		echo "try manual entry"
	fi
	
	cron_status=0
	echo "Updating crontab to dashboard database backup" >> "$CURR_DIR/logs/$log_file"
	(crontab -l 2>/dev/null | grep -Fqx "30 23 * * * ${DASHBOARD_HOME}/backup_dashboard_db.sh")
	
	if [ $? -ne 0 ];then
	    (crontab -l 2>/dev/null; echo "30 23 * * * ${DASHBOARD_HOME}/backup_dashboard_db.sh") | crontab - || cron_status=$?
    fi
   
    if [ "$cron_status" -ne 0 ]; then
	    echo "Failed to do crontab entry automatically for  DASHBOARD startup: " >> "$CURR_DIR/logs/$log_file"
		echo "Try manual entry." >> "$CURR_DIR/logs/$log_file"
		echo "Failed to do crontab entry automatically for DASHBOARD startup:"
		echo "try manual entry"	
	fi
}


main()
{
    trap finish_deployment EXIT
    set_dep_dir
	update_config
	echo "Stopping DASHBOARD (If alreay running):"
	echo "Stopping DASHBOARD:" >> "$CURR_DIR/logs/$log_file"
	"$CURR_DIR/stop_dashboard.sh" || exit 1
	deploy_db
	update_link
	update_crontab
	echo "Starting DASHBOARD This may take some time..." >> "$CURR_DIR/logs/$log_file"
	echo "Starting DASHBOARD This may take some time"
	"$CURR_DIR/start_dashboard.sh" || exit 1
	DEPLOY_SUCCESS=1
	echo "DASHBOARD deployment completed." | tee -a "$CURR_DIR/logs/$log_file"
	echo `date` >> "$CURR_DIR/logs/$log_file"
}

main "$@"
exit 0
