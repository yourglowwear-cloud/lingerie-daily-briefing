#!/usr/bin/env python3
"""
情趣内衣行业每日资讯简报 - GitHub Actions 云端版
功能：搜索过去24小时行业动态，筛选5-8条，生成HTML邮件并发送
"""

import os
import smtplib
import sys
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

try:
    from ddgs import DDGS
except ImportError:
    print("请先安装依赖: pip install ddgs", file=sys.stderr)
    sys.exit(1)


def search_news(keywords, max_per_keyword=8, max_retries=3):
    """使用 DuckDuckGo 搜索过去24小时的新闻，带重试机制"""
    results = []
    for keyword in keywords:
        success = False
        for attempt in range(max_retries):
            try:
                with DDGS(timeout=20) as ddgs:
                    for r in ddgs.news(
                        query=keyword,
                        region="wt-wt",
                        safesearch="off",
                        timelimit="d",
                        max_results=max_per_keyword,
                    ):
                        results.append(
                            {
                                "title": r.get("title", "").strip(),
                                "url": r.get("url", "").strip(),
                                "source": r.get("source", "").strip(),
                                "date": r.get("date", "").strip(),
                                "body": r.get("body", "").strip(),
                                "keyword": keyword,
                            }
                        )
                print(f"[搜索] '{keyword}' -> 获取到结果 (第{attempt+1}次尝试)")
                success = True
                break
            except Exception as e:
                print(f"[搜索] '{keyword}' 第{attempt+1}次尝试失败: {e}", file=sys.stderr)
                if attempt < max_retries - 1:
                    time.sleep(3)
        if not success:
            print(f"[搜索] '{keyword}' 最终失败，跳过", file=sys.stderr)
        time.sleep(1)
    return results


def deduplicate(news_list):
    """按URL去重"""
    seen = set()
    unique = []
    for item in news_list:
        url = item.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(item)
    return unique


def score_news(item):
    """
    简单价值评分，用于排序。
    维度：头部品牌/平台关键词加分、市场规模/政策关键词加分、来源权威性加分。
    """
    score = 0
    text = (item.get("title", "") + " " + item.get("body", "")).lower()

    # 头部品牌/平台
    high_value_brands = [
        "victoria's secret", "维密", "shein", "temu", "amazon", "亚马逊",
        "蕉内", "ubras", "曼妮芬", "爱慕", "la perla", "savage x fenty",
    ]
    for brand in high_value_brands:
        if brand.lower() in text:
            score += 30
            break

    # 行业事件关键词
    event_keywords = [
        "融资", "收购", "并购", "funding", "acquisition", "ipo",
        "政策", "法规", "regulation", "ban", "合规", "compliance",
        "展会", "exhibition", "expo", "show",
        "市场规模", "market size", "增长", "growth", "报告", "report",
    ]
    for kw in event_keywords:
        if kw.lower() in text:
            score += 15

    # 来源权威性
    authoritative_sources = [
        "wwd", "reuters", "bloomberg", "forbes", "36氪", "搜狐", "网易",
        "腾讯", "新浪", "时尚", "fashion", "glamour", "vogue",
    ]
    source = item.get("source", "").lower()
    for auth in authoritative_sources:
        if auth in source:
            score += 10
            break

    return score


def generate_html(news_list, today_str):
    """生成HTML邮件正文"""
    items_html = ""
    for i, item in enumerate(news_list, 1):
        title = item.get("title", "无标题")
        body = item.get("body", "")
        source = item.get("source", "未知来源")
        date = item.get("date", "")
        url = item.get("url", "#")

        # 摘要截断到200字
        if len(body) > 200:
            body = body[:200] + "..."

        items_html += f"""
<div class="news-item">
<div class="news-title"><span class="rank">{i}</span>{title}</div>
<div class="news-content">{body}</div>
<div class="news-meta">发布时间：{date} ｜ 来源：<a href="{url}">{source}</a></div>
</div>
"""

    # 生成摘要
    titles = [item.get("title", "") for item in news_list[:3]]
    summary = "；".join(titles)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; line-height: 1.7; color: #333; max-width: 720px; margin: 0 auto; padding: 20px; }}
.header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); color: #fff; padding: 30px; border-radius: 10px; margin-bottom: 25px; }}
.header h1 {{ margin: 0; font-size: 24px; }}
.header .date {{ font-size: 14px; opacity: 0.8; margin-top: 8px; }}
.summary {{ background: #f8f9fa; padding: 15px 20px; border-left: 4px solid #16213e; margin-bottom: 25px; border-radius: 4px; }}
.news-item {{ margin-bottom: 22px; padding-bottom: 18px; border-bottom: 1px solid #eee; }}
.news-item:last-child {{ border-bottom: none; }}
.rank {{ display: inline-block; background: #16213e; color: #fff; width: 28px; height: 28px; line-height: 28px; text-align: center; border-radius: 50%; font-size: 14px; font-weight: bold; margin-right: 10px; }}
.news-title {{ font-size: 16px; font-weight: bold; color: #1a1a2e; margin-bottom: 6px; }}
.news-content {{ font-size: 14px; color: #555; margin-bottom: 6px; }}
.news-meta {{ font-size: 12px; color: #999; }}
.news-meta a {{ color: #4a69bd; text-decoration: none; }}
.footer {{ text-align: center; font-size: 12px; color: #aaa; margin-top: 30px; padding-top: 15px; border-top: 1px solid #eee; }}
</style>
</head>
<body>

<div class="header">
<h1>情趣内衣行业每日资讯</h1>
<div class="date">{today_str} ｜ 过去24小时 ｜ 共筛选 {len(news_list)} 条重要动态</div>
</div>

<div class="summary">
<strong>今日要点：</strong>{summary}
</div>

{items_html}

<div class="footer">
本简报由 GitHub Actions 自动搜集整理 ｜ 数据来源：公开网络信息 ｜ 仅供参考<br>
发送时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}
</div>

</body>
</html>"""
    return html


def send_email(html_content, subject, sender, password, recipients, smtp_server, smtp_port):
    """发送HTML邮件"""
    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)

    body = MIMEText(html_content, "html", "utf-8")
    msg.attach(body)

    try:
        server = smtplib.SMTP_SSL(smtp_server, int(smtp_port), timeout=30)
        server.login(sender, password)
        server.sendmail(sender, recipients, msg.as_string())
        server.quit()
        print(f"[邮件] 发送成功 -> {', '.join(recipients)}")
        return True
    except Exception as e:
        print(f"[邮件] 发送失败: {e}", file=sys.stderr)
        return False


def main():
    # 从环境变量读取配置（GitHub Secrets 注入）
    sender_email = os.environ.get("SENDER_EMAIL", "")
    sender_password = os.environ.get("SENDER_PASSWORD", "")
    receiver_emails_str = os.environ.get("RECEIVER_EMAILS", "")
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.qq.com")
    smtp_port = os.environ.get("SMTP_PORT", "465")

    if not sender_email or not sender_password or not receiver_emails_str:
        print("错误：请配置 SENDER_EMAIL、SENDER_PASSWORD、RECEIVER_EMAILS 环境变量", file=sys.stderr)
        sys.exit(1)

    receiver_emails = [e.strip() for e in receiver_emails_str.split(",") if e.strip()]

    # 搜索关键词（中英文并行）
    keywords = [
        "情趣内衣 行业动态",
        "lingerie industry news",
        "intimate apparel market trends",
        "adult lingerie brand",
        "情趣内衣 品牌 融资 政策 展会",
    ]

    print("=" * 50)
    print(f"情趣内衣行业每日资讯 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    # 1. 搜索新闻
    print("\n[1/4] 正在搜索过去24小时行业动态...")
    all_news = search_news(keywords, max_per_keyword=8)
    print(f"      共获取 {len(all_news)} 条原始结果")

    # 2. 去重
    print("\n[2/4] 去重处理...")
    unique_news = deduplicate(all_news)
    print(f"      去重后 {len(unique_news)} 条")

    # 3. 按价值评分排序，取前8条
    print("\n[3/4] 按重要性排序筛选...")
    scored = sorted(unique_news, key=score_news, reverse=True)
    selected = scored[:8]

    if len(selected) < 5:
        print(f"      注意：仅找到 {len(selected)} 条有效信息（不足5条）")

    for i, item in enumerate(selected, 1):
        print(f"      {i}. {item.get('title', '无标题')[:50]}")

    # 4. 生成HTML并发送
    print("\n[4/4] 生成邮件并发送...")
    today_str = datetime.now().strftime("%Y年%m月%d日")
    html_content = generate_html(selected, today_str)
    subject = f"情趣内衣行业每日资讯 - {today_str}"

    success = send_email(
        html_content, subject, sender_email, sender_password,
        receiver_emails, smtp_server, smtp_port
    )

    if success:
        print("\n" + "=" * 50)
        print("任务完成！邮件已发送。")
        print("=" * 50)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
