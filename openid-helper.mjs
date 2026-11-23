#!/usr/bin/env node
/**
 * 取 QQ 机器人给你的 user_openid
 *
 * 用法： node openid-helper.mjs <AppID> <AppSecret>
 *
 * 原理：WebSocket 是客户端主动往外连，不需要域名、不需要备案。
 * 连上后用 intents(1<<25) 订阅「私聊 / 群里 @」事件，你给机器人发一条消息，
 * 脚本从事件里取出 author.user_openid 打印出来，然后自己退出。
 *
 * 只依赖 Node 18+（内置 fetch 和 WebSocket）。
 */
const [appId, secret] = process.argv.slice(2);

if (!appId || !secret) {
  console.error('用法: node openid-helper.mjs <AppID> <AppSecret>');
  process.exit(1);
}

const TOKEN_URL = 'https://bots.qq.com/app/getAppAccessToken';
const API = 'https://api.sgroup.qq.com';
const INTENTS_GROUP_AND_C2C = 1 << 25;

async function main() {
  console.log('1/3 换取 access_token…');
  const tr = await fetch(TOKEN_URL, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ appId, clientSecret: secret }),
  });
  const tj = await tr.json().catch(() => ({}));
  if (!tj.access_token) {
    console.error('✗ 换取 token 失败：' + JSON.stringify(tj));
    console.error('  检查 AppID / AppSecret 是否正确。');
    process.exit(1);
  }

  console.log('2/3 获取 WebSocket 网关…');
  const gr = await fetch(API + '/gateway', {
    headers: { authorization: 'QQBot ' + tj.access_token },
  });
  const gj = await gr.json().catch(() => ({}));
  if (!gj.url) {
    console.error('✗ 获取网关失败：' + JSON.stringify(gj));
    process.exit(1);
  }

  console.log('3/3 已连接，请现在用手机 QQ 给机器人发一条私聊消息…');
  console.log('    （60 秒内有效，收到后脚本会自己退出）');
  console.log('');

  const ws = new WebSocket(gj.url);
  let seq = null;
  let heartbeat = null;
  const timer = setTimeout(() => {
    console.error('✗ 超时：60 秒内没收到消息。');
    console.error('  确认机器人已开通「私聊消息」权限，并且是直接私聊它。');
    cleanup(1);
  }, 60000);

  function cleanup(code) {
    clearTimeout(timer);
    if (heartbeat) clearInterval(heartbeat);
    try { ws.close(); } catch (e) {}
    setTimeout(() => process.exit(code), 80);
  }

  ws.onopen = () => console.log('   连接已建立，等待鉴权…');

  ws.onmessage = (ev) => {
    let p2;
    try { p2 = JSON.parse(ev.data); } catch (e) { return; }
    if (p2.s) seq = p2.s;

    if (p2.op === 10) {
      ws.send(JSON.stringify({
        op: 2,
        d: {
          token: 'QQBot ' + tj.access_token,
          intents: INTENTS_GROUP_AND_C2C,
          shard: [0, 1],
          properties: { $os: 'linux', $browser: 'node', $device: 'node' },
        },
      }));
      heartbeat = setInterval(() => {
        try { ws.send(JSON.stringify({ op: 1, d: seq })); } catch (e) {}
      }, 40000);
      return;
    }

    if (p2.op === 9) {
      console.error('✗ 鉴权失败：intents 没权限。去 q.qq.com 确认机器人开通了「私聊消息」事件。');
      cleanup(1);
      return;
    }

    if (p2.op !== 0 || !p2.t) return;

    if (p2.t === 'READY') {
      console.log('   鉴权通过，正在等你发消息…');
      return;
    }

    const d = p2.d || {};
    const author = d.author || {};
    const oid = author.user_openid || author.member_openid || d.user_openid || '';
    if (oid) {
      console.log('');
      console.log('==============================================');
      console.log('✅ 拿到了 OpenID：');
      console.log('');
      console.log('   ' + oid);
      console.log('');
      console.log('事件类型: ' + p2.t);
      console.log('==============================================');
      console.log('');
      console.log('把上面这串填进签到控制台 → 通知 → QQ 机器人的「OpenID」，保存即可。');
      cleanup(0);
      return;
    }

    console.log('   收到事件 ' + p2.t + '，不是消息事件，继续等…');
  };

  ws.onerror = () => console.error('   连接异常，继续等待…');
}

main().catch((e) => {
  console.error('✗ ' + (e && e.message ? e.message : e));
  process.exit(1);
});
