# -*- coding: utf-8 -*-
"""签到执行器：发起签到请求、记录日志、触发通知"""
import json
import logging
import requests

import db
import notify

# 默认请求头（与浏览器请求一致，可被签到项自定义 headers 覆盖）
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Content-Type": "application/json",
}


def run_checkin(item, trigger_type="manual"):
    """执行单个签到项，返回结果字典。trigger_type: manual / auto"""
    name = item["name"]
    logging.info(f"[{trigger_type}] 开始签到：{name} ({item['url']})")

    headers = dict(DEFAULT_HEADERS)
    if item.get("headers"):
        try:
            custom = json.loads(item["headers"])
            if isinstance(custom, dict):
                headers.update({str(k): str(v) for k, v in custom.items()})
        except json.JSONDecodeError:
            logging.warning(f"签到项[{name}] headers 不是合法JSON，已忽略自定义headers")
    if item.get("cookie"):
        headers["Cookie"] = item["cookie"]

    method = (item.get("method") or "POST").upper()
    body = item.get("body") or None

    status = "fail"
    http_code = None
    response_text = ""
    try:
        resp = requests.request(method, item["url"], headers=headers, data=body, timeout=15)
        http_code = resp.status_code
        response_text = resp.text[:1000]
        logging.info(f"签到项[{name}] 状态码：{http_code} 响应：{response_text}")
        if resp.status_code == 200:
            status = "success"
    except Exception as e:
        response_text = f"请求异常：{e}"
        logging.error(f"签到项[{name}] {response_text}")

    # 回写签到项状态 + 写日志
    db.update_item_result(item["id"], status, response_text)
    db.add_log(item["id"], name, status, http_code, response_text, trigger_type)

    # 通知
    notify_status = ""
    cfg = db.get_notify_config()
    if cfg["enabled"]:
        icon = "✅" if status == "success" else "❌"
        content = (
            f"{icon} 签到{'成功' if status == 'success' else '失败'}\n"
            f"任务：{name}\n"
            f"触发：{'定时自动' if trigger_type == 'auto' else '手动'}\n"
            f"状态码：{http_code}\n"
            f"响应：{response_text[:300]}"
        )
        ok, msg = notify.send_message(content)
        notify_status = "ok" if ok else msg
        # 更新该条日志的通知状态
        if notify_status:
            _update_latest_log_notify(item["id"], notify_status)

    return {
        "item_id": item["id"],
        "name": name,
        "status": status,
        "http_code": http_code,
        "response": response_text,
        "notify": notify_status,
    }


def _update_latest_log_notify(item_id, notify_status):
    import sqlite3
    try:
        with db._lock, db.get_conn() as conn:
            conn.execute(
                "UPDATE logs SET notify_status = ? WHERE item_id = ? AND id = (SELECT MAX(id) FROM logs WHERE item_id = ?)",
                (notify_status, item_id, item_id),
            )
            conn.commit()
    except Exception as e:
        logging.warning(f"更新日志通知状态失败：{e}")


def run_all(trigger_type="manual"):
    """执行所有启用的签到项"""
    results = []
    for item in db.list_items():
        if not item["enabled"]:
            continue
        results.append(run_checkin(item, trigger_type))
    return results
