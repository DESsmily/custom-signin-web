#!/bin/bash

# 签到管理系统 Web 服务 启动/停止/重启 脚本
# 用法： bash task.sh {start|stop|restart}

SCRIPT_NAME="app.py"
PID_FILE="checkin.pid"
LOG_FILE="checkin_log.log"

# 优先使用 python，找不到则尝试 python3
if command -v python >/dev/null 2>&1; then
    PY=python
else
    PY=python3
fi

is_running() {
    [ -f "$PID_FILE" ] || return 1
    PID=$(cat "$PID_FILE")
    ps -p "$PID" > /dev/null 2>&1
}

start() {
    if is_running; then
        echo "✅ 服务已在运行中，PID：$(cat $PID_FILE)"
        return
    fi
    rm -f "$PID_FILE"
    echo "🔧 正在启动签到管理系统..."
    nohup "$PY" "$SCRIPT_NAME" > /dev/null 2>&1 &
    echo $! > "$PID_FILE"
    sleep 2
    if is_running; then
        echo "✅ 启动成功，PID：$(cat $PID_FILE)"
        echo "🌐 访问地址：http://127.0.0.1:10090"
    else
        rm -f "$PID_FILE"
        echo "❌ 启动失败，请查看 $LOG_FILE"
        exit 1
    fi
}

stop() {
    if ! is_running; then
        echo "⚠️ 服务未运行"
        rm -f "$PID_FILE"
        return
    fi
    PID=$(cat "$PID_FILE")
    kill "$PID"
    for i in $(seq 1 10); do
        ps -p "$PID" > /dev/null 2>&1 || break
        sleep 1
    done
    if ps -p "$PID" > /dev/null 2>&1; then
        kill -9 "$PID" 2>/dev/null
    fi
    rm -f "$PID_FILE"
    echo "✅ 已停止服务（PID：$PID）"
}

restart() {
    stop
    sleep 1
    start
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    *)
        echo "用法：$0 {start|stop|restart}"
        exit 1
        ;;
esac
