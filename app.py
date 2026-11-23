# -*- coding: utf-8 -*-
"""签到管理系统 Web 服务

运行：python app.py
访问：http://127.0.0.1:5000
"""
import logging
import os
import re

from flask import Flask, jsonify, render_template, request, send_file
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import db
import checker
import notify

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("checkin_log.log", encoding="utf-8"), logging.StreamHandler()],
)

app = Flask(__name__)
scheduler = BackgroundScheduler()
TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _job_id(item_id):
    return f"checkin_{item_id}"


def _parse_time(schedule_time):
    """解析 HH:MM，返回 (hour, minute)，非法返回 None"""
    m = TIME_RE.match((schedule_time or "").strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def reload_job(item):
    """根据签到项状态（重新）注册/移除定时任务"""
    job_id = _job_id(item["id"])
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass
    if not item["enabled"]:
        return
    hm = _parse_time(item["schedule_time"])
    if not hm:
        logging.warning(f"签到项[{item['name']}] 定时时间格式非法：{item['schedule_time']}，未注册定时任务")
        return
    scheduler.add_job(
        lambda iid=item["id"]: _auto_checkin(iid),
        CronTrigger(hour=hm[0], minute=hm[1]),
        id=job_id,
        replace_existing=True,
    )
    logging.info(f"签到项[{item['name']}] 已注册每日定时任务：{item['schedule_time']}")


def _auto_checkin(item_id):
    item = db.get_item(item_id)
    if item and item["enabled"]:
        checker.run_checkin(item, trigger_type="auto")


# ---------------- 页面 ----------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/download/openid-helper.mjs")
def download_openid_helper():
    """下载 openid 获取辅助脚本"""
    return send_file(
        os.path.join(BASE_DIR, "openid-helper.mjs"),
        as_attachment=True,
        mimetype="text/javascript",
        download_name="openid-helper.mjs",
    )


# ---------------- 签到项接口 ----------------

def _validate_item_payload(data, partial=False):
    """校验请求体，返回 (cleaned_data, error)"""
    cleaned = {}
    if not partial or "name" in data:
        cleaned["name"] = (data.get("name") or "").strip() or "未命名签到"
    if not partial or "url" in data:
        url = (data.get("url") or "").strip()
        if not url:
            return None, "url 不能为空"
        if not url.startswith(("http://", "https://")):
            return None, "url 必须以 http:// 或 https:// 开头"
        cleaned["url"] = url
    if "method" in data or not partial:
        method = (data.get("method") or "POST").upper()
        if method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            return None, f"不支持的请求方法：{method}"
        cleaned["method"] = method
    for key in ("headers", "cookie", "body"):
        if key in data or not partial:
            cleaned[key] = data.get(key) or ""
    if "headers" in cleaned and cleaned["headers"].strip():
        import json as _json
        try:
            h = _json.loads(cleaned["headers"])
            if not isinstance(h, dict):
                return None, "headers 必须是 JSON 对象，如 {\"Key\": \"Value\"}"
        except _json.JSONDecodeError as e:
            return None, f"headers 不是合法JSON：{e}"
    if not partial or "schedule_time" in data:
        st = (data.get("schedule_time") or "").strip()
        if not TIME_RE.match(st):
            return None, "定时时间格式应为 HH:MM，如 08:30"
        cleaned["schedule_time"] = st
    if "enabled" in data:
        cleaned["enabled"] = bool(data["enabled"])
    elif not partial:
        cleaned["enabled"] = True
    return cleaned, None


@app.route("/api/items", methods=["GET"])
def api_items():
    return jsonify({"items": db.list_items()})


@app.route("/api/items", methods=["POST"])
def api_create_item():
    data, err = _validate_item_payload(request.get_json(force=True) or {})
    if err:
        return jsonify({"error": err}), 400
    item_id = db.create_item(data)
    item = db.get_item(item_id)
    reload_job(item)
    return jsonify({"item": item}), 201


@app.route("/api/items/<int:item_id>", methods=["PUT"])
def api_update_item(item_id):
    if not db.get_item(item_id):
        return jsonify({"error": "签到项不存在"}), 404
    data, err = _validate_item_payload(request.get_json(force=True) or {}, partial=True)
    if err:
        return jsonify({"error": err}), 400
    db.update_item(item_id, data)
    item = db.get_item(item_id)
    reload_job(item)
    return jsonify({"item": item})


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def api_delete_item(item_id):
    if not db.get_item(item_id):
        return jsonify({"error": "签到项不存在"}), 404
    db.delete_item(item_id)
    try:
        scheduler.remove_job(_job_id(item_id))
    except Exception:
        pass
    return jsonify({"ok": True})


# ---------------- 签到触发接口 ----------------

@app.route("/api/items/<int:item_id>/checkin", methods=["POST"])
def api_checkin_one(item_id):
    item = db.get_item(item_id)
    if not item:
        return jsonify({"error": "签到项不存在"}), 404
    result = checker.run_checkin(item, trigger_type="manual")
    return jsonify({"result": result})


@app.route("/api/checkin/all", methods=["POST"])
def api_checkin_all():
    results = checker.run_all(trigger_type="manual")
    return jsonify({"results": results})


# ---------------- 通知配置接口 ----------------

@app.route("/api/notify", methods=["GET"])
def api_get_notify():
    cfg = db.get_notify_config()
    return jsonify({"config": cfg})


@app.route("/api/notify", methods=["PUT"])
def api_save_notify():
    data = request.get_json(force=True) or {}
    cfg = db.get_notify_config()
    merged = {
        "enabled": bool(data.get("enabled", cfg["enabled"])),
        "app_id": data.get("app_id", cfg["app_id"]),
        "app_secret": data.get("app_secret", cfg["app_secret"]),
        "user_openid": data.get("user_openid", cfg["user_openid"]),
    }
    if merged["enabled"] and not (merged["app_id"] and merged["app_secret"] and merged["user_openid"]):
        return jsonify({"error": "启用通知前请填写完整的 appId / appSecret / 用户openid"}), 400
    db.save_notify_config(merged)
    return jsonify({"config": db.get_notify_config()})


@app.route("/api/notify/test", methods=["POST"])
def api_notify_test():
    ok, msg = notify.send_message("🧪 这是一条来自签到管理系统的测试消息")
    return jsonify({"success": ok, "message": msg}), (200 if ok else 400)


# ---------------- 日志接口 ----------------

@app.route("/api/logs", methods=["GET"])
def api_logs():
    return jsonify({"logs": db.list_logs(limit=50)})


if __name__ == "__main__":
    db.init_db()
    for it in db.list_items():
        reload_job(it)
    scheduler.start()
    logging.info("🚀 签到管理系统已启动：http://127.0.0.1:10090")
    app.run(host="0.0.0.0", port=10090, threaded=True)
