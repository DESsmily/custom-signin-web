#!/bin/bash

# 签到管理系统 Web 服务 启动/停止/重启 脚本
# 用法： bash task.sh {start|stop|restart}

SCRIPT_NAME="app.py"
PID_FILE="checkin.pid"
LOG_FILE="checkin_log.log"

# 统一在脚本所在目录执行，避免从其他目录启动时日志/PID 文件落到别处
cd "$(dirname "$0")" || exit 1

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
    # 确保日志文件存在，并记录启动输出，启动失败时便于排查
    touch "$LOG_FILE" 2>/dev/null || {
        echo "❌ 无法创建日志文件 $LOG_FILE"
        exit 1
    }
    echo "🔧 正在启动签到管理系统..."
    echo "===== $(date '+%Y-%m-%d %H:%M:%S') 启动 =====" >> "$LOG_FILE"
    nohup "$PY" "$SCRIPT_NAME" >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    sleep 2
    if is_running; then
        echo "✅ 启动成功，PID：$(cat $PID_FILE)"
        echo "🌐 访问地址：http://127.0.0.1:10090"
    else
        rm -f "$PID_FILE"
        echo "❌ 启动失败，请查看 $LOG_FILE"
        echo "----- 最近日志 -----"
        tail -n 20 "$LOG_FILE" 2>/dev/null
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
