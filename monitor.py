#!/usr/bin/env python3
"""
X (Twitter) 账户发帖监控脚本
通过 X API v2 检查目标用户是否发了新帖子，有新帖时发送邮件通知。

使用方法:
    python monitor.py --target USERNAME
    python monitor.py --target USERNAME --filter "Booster,#币安钱包"
    python monitor.py --target USERNAME --filter "Booster,币安" --match-all

环境变量 (通过 GitHub Secrets 或 .env 文件设置):
    X_BEARER_TOKEN    - X API v2 的 Bearer Token
    SMTP_HOST         - SMTP 服务器地址 (默认 smtp.gmail.com)
    SMTP_PORT         - SMTP 端口 (默认 465)
    SMTP_USER         - 发件邮箱地址
    SMTP_PASS         - 发件邮箱密码/应用密码
    NOTIFY_EMAIL      - 接收通知的邮箱地址
    FILTER_KEYWORDS   - 过滤关键词，多个用逗号分隔 (可选，等同于 --filter)
"""

import argparse
import json
import os
import smtplib
import sys
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests

# --- 配置 ---
STATE_FILE = Path(__file__).parent / "state.json"
API_BASE = "https://api.twitter.com/2"
MAX_TWEETS_PER_CHECK = 5  # 每次检查获取最近的推文数


def load_state() -> dict:
    """加载上次检查的状态"""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    """保存检查状态"""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


API_BASE = "https://api.twitterapi.io"




def get_recent_tweets(api_key: str, username: str) -> list[dict]:
    """获取用户最近的推文"""
    url = f"{API_BASE}/twitter/user/last_tweets"
    headers = {"X-API-Key": api_key}
    params = {"userName": username}
    resp = requests.get(url, headers=headers, params=params, timeout=15)

    if resp.status_code == 429:
        print("⚠️  触发速率限制，请稍后重试")
        sys.exit(1)

    if resp.status_code != 200:
        print(f"❌ 获取推文失败: HTTP {resp.status_code}")
        print(f"   响应: {resp.text[:300]}")
        sys.exit(1)

    payload = resp.json().get("data", {})
    # 注意：不同版本的返回结构可能是 data 直接是 list，也可能是 {"tweets": [...]}
    tweets = payload.get("tweets", payload) if isinstance(payload, dict) else payload
    tweets = tweets[:MAX_TWEETS_PER_CHECK]

    print(f"📋 获取到 {len(tweets)} 条最近推文")
    return tweets


def find_new_tweets(tweets: list[dict], last_seen_id: str | None) -> list[dict]:
    """找出上次检查之后发布的新推文"""
    if not tweets:
        return []

    new_tweets = []
    for tweet in tweets:
        if tweet["id"] == last_seen_id:
            break  # 遇到上次见过的推文就停
        new_tweets.append(tweet)

    return new_tweets


def match_keywords(text: str, keywords: list[str], match_all: bool = False) -> bool:
    """
    检查文本是否包含指定关键词，大小写不敏感。

    match_all=False: 任一关键词匹配即返回 True (OR 逻辑)
    match_all=True:  所有关键词都匹配才返回 True (AND 逻辑)
    """
    if not keywords:
        return True  # 没有设置过滤关键词，全部通过

    text_lower = text.lower()
    if match_all:
        return all(kw.lower() in text_lower for kw in keywords)
    else:
        return any(kw.lower() in text_lower for kw in keywords)


def format_tweet(tweet: dict, username: str, matched_keywords: list[str] | None = None) -> tuple[str, str]:
    """格式化推文，返回 (标题, 正文)"""
    created_at = tweet.get("created_at", "未知时间")
    text = tweet.get("text", "")
    tweet_url = f"https://twitter.com/{username}/status/{tweet['id']}"

    keyword_hint = ""
    if matched_keywords:
        keyword_hint = f" [匹配: {', '.join(matched_keywords)}]"

    title = f"@{username} 发布了新帖子{keyword_hint}"
    body = f"""
<p><strong>发布时间:</strong> {created_at}</p>
<p><strong>内容:</strong></p>
<blockquote style="border-left:3px solid #1d9bf0;padding-left:12px;color:#333;">
  {text}
</blockquote>
<p><a href="{tweet_url}" style="color:#1d9bf0;">🔗 在 X 上查看</a></p>
"""
    return title, body


def send_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_pass: str,
    to_email: str,
    subject: str,
    html_body: str,
) -> None:
    """发送 HTML 邮件通知"""
    msg = MIMEMultipart("alternative")
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, to_email, msg.as_string())
        server.quit()
        print(f"📧 邮件已发送至 {to_email}")
    except smtplib.SMTPAuthenticationError:
        print("❌ SMTP 认证失败，请检查邮箱和密码（Gmail 需使用应用专用密码）")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 发送邮件失败: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="监控 X 账户发帖",
        epilog="示例: python monitor.py --target binancezh --filter Booster '#币安钱包'",
    )
    parser.add_argument("--target", required=True, help="目标用户名 (不含 @)")
    parser.add_argument(
        "--filter",
        default=None,
        help="过滤关键词，逗号分隔。只通知包含这些词的帖子。"
        "默认 OR 逻辑（任一匹配即通知），加 --match-all 切换为 AND 逻辑。"
        '例如: --filter "Booster,#币安钱包,USD"',
    )
    parser.add_argument(
        "--match-all",
        action="store_true",
        help="关键词匹配改为 AND 逻辑（全部匹配才通知）",
    )
    args = parser.parse_args()
    username = args.target.lstrip("@")

    # 关键词来源: 命令行参数 > 环境变量
    raw_filter = args.filter or os.getenv("FILTER_KEYWORDS", "")
    keywords = [kw.strip() for kw in raw_filter.split(",") if kw.strip()]

    # --- 读取环境变量 ---
    twitterapi = os.getenv("twitteri_api")
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    notify_email = os.getenv("NOTIFY_EMAIL")

    missing = []
    if not twitterapi:
        missing.append("TWITTERI_API")
    if not smtp_user:
        missing.append("SMTP_USER")
    if not smtp_pass:
        missing.append("SMTP_PASS")
    if not notify_email:
        missing.append("NOTIFY_EMAIL")

    if missing:
        print(f"❌ 缺少环境变量: {', '.join(missing)}")
        print("   请在 GitHub Secrets 或 .env 文件中设置这些变量")
        sys.exit(1)

    print(f"🔍 开始检查 @{username} 的新帖子...")
    if keywords:
        logic = "AND" if args.match_all else "OR"
        print(f"   🔎 过滤关键词 ({logic}): {keywords}")
    print(f"   时间: {datetime.now(timezone.utc).isoformat()}")



    # 2. 获取最近推文
    tweets = get_recent_tweets(twitterapi, username)

    # 3. 加载状态
    state = load_state()
    state_key = f"last_tweet_id_{username}"
    last_seen_id = state.get(state_key)

    if not tweets:
        print("ℹ️  该用户暂无推文")
        return

    latest_tweet = tweets[0]

    # 4. 首次运行 — 只记录不通知
    if last_seen_id is None:
        print(f"📝 首次运行，记录最新推文 ID: {latest_tweet['id']}")
        if keywords:
            print(f"   已设置 {len(keywords)} 个过滤关键词，下次匹配到才通知")
        print(f"   下次检查时将通知新推文")
        state[state_key] = latest_tweet["id"]
        save_state(state)
        return

    # 5. 查找新推文
    new_tweets = find_new_tweets(tweets, last_seen_id)

    if not new_tweets:
        print(f"✅ 没有新推文 (上次 ID: {last_seen_id[:8]}...)")
    else:
        # 关键词过滤
        matched_tweets: list[tuple[dict, list[str]]] = []
        skipped_count = 0
        for tweet in new_tweets:
            text = tweet.get("text", "")
            if keywords:
                # 找出具体匹配了哪些关键词
                matched = [kw for kw in keywords if kw.lower() in text.lower()]
                if match_keywords(text, keywords, args.match_all):
                    matched_tweets.append((tweet, matched))
                else:
                    skipped_count += 1
            else:
                matched_tweets.append((tweet, []))

        print(f"🎉 发现 {len(new_tweets)} 条新推文", end="")
        if keywords:
            print(f"，其中 {len(matched_tweets)} 条匹配关键词", end="")
            if skipped_count > 0:
                print(f"，{skipped_count} 条被过滤", end="")
        print()

        if not matched_tweets:
            print("ℹ️  没有匹配关键词的推文，跳过通知")
        else:
            for i, (tweet, matched_kws) in enumerate(matched_tweets, 1):
                text_preview = tweet.get("text", "")[:80]
                print(f"   [{i}] {text_preview}...")
                title, body = format_tweet(tweet, username, matched_kws if matched_kws else None)
                send_email(
                    smtp_host=smtp_host,
                    smtp_port=smtp_port,
                    smtp_user=smtp_user,
                    smtp_pass=smtp_pass,
                    to_email=notify_email,
                    subject=title,
                    html_body=body,
                )
                # 每条通知之间间隔，避免 SMTP 限流
                if len(matched_tweets) > 1 and i < len(matched_tweets):
                    time.sleep(2)

    # 6. 更新状态 — 始终更新到最新推文，避免重复检查
    state[state_key] = latest_tweet["id"]
    save_state(state)


if __name__ == "__main__":
    main()
