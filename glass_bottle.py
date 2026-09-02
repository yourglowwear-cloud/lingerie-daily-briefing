#!/usr/bin/env python3
"""
玻璃瓶行业每日资讯简报 - GitHub Actions 云端版
功能：搜索过去24小时玻璃瓶/玻璃包装行业动态，智能筛选5-8条，生成HTML邮件并发送
"""

import os
import re
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


# ============================================================
# 核心关键词库（用于相关性判断和过滤）
# ============================================================
CORE_KEYWORDS = [
    "glass bottle", "glass packaging", "玻璃瓶", "玻璃包装",
    "玻璃容器", "glass container", "药用玻璃", "化妆品瓶",
    "饮料瓶", "wine bottle", "beer bottle", "玻璃器皿",
    "glassware", "硼硅玻璃", "钢化玻璃", "glass jar",
]

# 低质量/无关内容过滤词
LOW_QUALITY_WORDS = [
    "批发", "厂家直销", "一件代发", "价格", "报价", "采购",
    "wholesale", "cheap", "buy now", "shop now", "discount",
    "coupon", "promo code", "free shipping", "二手", "回收价格",
]


def search_news(keywords, max_per_keyword=10, max_retries=3):
    """使用 DuckDuckGo 搜索过去24小时的新闻，带重试机制"""
    results = []
    for keyword in keywords:
        success = False
        for attempt in range(max_retries):
            try:
                with DDGS(timeout=25) as ddgs:
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
                count = sum(1 for r in results if r["keyword"] == keyword)
                print(f"[搜索] '{keyword}' -> {count} 条结果")
                success = True
                break
            except Exception as e:
                print(f"[搜索] '{keyword}' 第{attempt+1}次失败: {e}", file=sys.stderr)
                if attempt < max_retries - 1:
                    time.sleep(4)
        if not success:
            print(f"[搜索] '{keyword}' 最终失败，跳过", file=sys.stderr)
        time.sleep(1.5)
    return results


def is_relevant(item):
    """判断内容是否与玻璃瓶行业相关"""
    text = (item.get("title", "") + " " + item.get("body", "")).lower()
    title = item.get("title", "").lower()

    if len(title) < 12:
        return False

    has_core = any(kw.lower() in text for kw in CORE_KEYWORDS)
    if not has_core:
        return False

    has_low_quality = any(lw.lower() in title for lw in LOW_QUALITY_WORDS)
    if has_low_quality and not any(
        kw in title for kw in ["行业", "市场", "品牌", "政策", "融资", "展会", "趋势", "industry", "market", "brand", "regulation", "技术", "创新"]
    ):
        return False

    return True


def title_similarity(t1, t2):
    """简单标题相似度判断"""
    s1 = set(re.findall(r"\w+", t1.lower()))
    s2 = set(re.findall(r"\w+", t2.lower()))
    if not s1 or not s2:
        return 0
    return len(s1 & s2) / min(len(s1), len(s2))


def deduplicate(news_list):
    """URL去重 + 标题相似度去重"""
    seen_urls = set()
    seen_titles = []
    unique = []

    for item in news_list:
        url = item.get("url", "")
        title = item.get("title", "")

        if url and url in seen_urls:
            continue

        is_dup = False
        for st in seen_titles:
            if title_similarity(title, st) > 0.6:
                is_dup = True
                break

        if is_dup:
            continue

        if url:
            seen_urls.add(url)
        seen_titles.append(title)
        unique.append(item)

    return unique


def score_news(item):
    """多维度价值评分"""
    score = 0
    text = (item.get("title", "") + " " + item.get("body", "")).lower()
    title = item.get("title", "").lower()
    source = item.get("source", "").lower()

    # 1. 头部企业/品牌（+40）
    high_value_brands = [
        "owens-illinois", "o-i", "verallia", "arc international",
        "肖特", "schott", "康宁", "corning", "山东药玻", "正川股份",
        "力诺特玻", "华兴玻璃", "德力股份", "珠江玻璃", "glasspack",
        "stölzle", "stolzle", "bormioli", " Luigi bormioli", "raja",
    ]
    if any(b in text for b in high_value_brands):
        score += 40

    # 2. 资本动作（+35）
    capital_words = [
        "融资", "收购", "并购", "ipo", "上市", "估值", "扩产", "投产",
        "funding", "acquisition", "merger", "investment", "valuation",
        "raises", "raised", "series a", "series b", "series c",
        "新建工厂", "产能扩张", "capacity expansion",
    ]
    if any(w in text for w in capital_words):
        score += 35

    # 3. 政策法规（+30）
    policy_words = [
        "政策", "法规", "监管", "合规", "禁令", "标准", "新规", "环保政策",
        "regulation", "ban", "compliance", "law", "legislation",
        "tariff", "tax", "customs", "关税", "出口管制", "双碳", "碳中和",
    ]
    if any(w in text for w in policy_words):
        score += 30

    # 4. 市场数据/行业报告（+25）
    market_words = [
        "市场规模", "市场份额", "增长率", "行业报告", "白皮书", "数据",
        "market size", "market share", "growth rate", "industry report",
        "revenue", "sales", "billion", "million", "亿元", "万亿",
        "产能", "产量", "出口量", "进口",
    ]
    if any(w in text for w in market_words):
        score += 25

    # 5. 展会/行业活动（+20）
    expo_words = [
        "展会", "博览会", "展览", "发布会", "论坛",
        "expo", "exhibition", "trade show", "conference",
        "summit", "forum", "glasstec", "中国玻璃展",
    ]
    if any(w in text for w in expo_words):
        score += 20

    # 6. 技术/材料创新（+15）
    tech_words = [
        "创新", "新技术", "新材料", "可持续", "环保", "智能", "科技",
        "innovation", "sustainable", "eco-friendly", "technology",
        "smart", "recycled", "轻量化", "薄壁", "高白料", "晶质料",
        "纳米", "涂层", "抗菌", "可降解",
    ]
    if any(w in text for w in tech_words):
        score += 15

    # 7. 来源权威性（+15）
    authoritative_sources = [
        "reuters", "bloomberg", "forbes", "glassonline", "glassmagazine",
        "glass-international", "36氪", "36kr", "钛媒体", "搜狐", "网易",
        "腾讯", "新浪", "第一财经", "界面新闻", "中国玻璃网", "中玻网",
    ]
    if any(a in source for a in authoritative_sources):
        score += 15

    # 8. 标题直接含核心行业词（+10）
    title_core = [
        "玻璃瓶", "玻璃包装", "glass bottle", "glass packaging",
        "玻璃容器", "药用玻璃", "glass container",
    ]
    if any(w in title for w in title_core):
        score += 10

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
        score = item.get("score", 0)

        if len(body) > 180:
            body = body[:180] + "..."

        if score >= 80:
            tag = '<span style="background:#dc3545;color:#fff;padding:2px 6px;border-radius:3px;font-size:11px;">重磅</span>'
        elif score >= 50:
            tag = '<span style="background:#fd7e14;color:#fff;padding:2px 6px;border-radius:3px;font-size:11px;">重要</span>'
        else:
            tag = '<span style="background:#6c757d;color:#fff;padding:2px 6px;border-radius:3px;font-size:11px;">关注</span>'

        items_html += f"""
<div class="news-item">
<div class="news-title"><span class="rank">{i}</span>{title} {tag}</div>
<div class="news-content">{body}</div>
<div class="news-meta">发布时间：{date} ｜ 来源：<a href="{url}">{source}</a></div>
</div>
"""

    titles = [item.get("title", "") for item in news_list[:3]]
    summary = "；".join(t[:40] + "..." if len(t) > 40 else t for t in titles)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; line-height: 1.7; color: #333; max-width: 720px; margin: 0 auto; padding: 20px; }}
.header {{ background: linear-gradient(135deg, #0d47a1, #1565c0); color: #fff; padding: 30px; border-radius: 10px; margin-bottom: 25px; }}
.header h1 {{ margin: 0; font-size: 24px; }}
.header .date {{ font-size: 14px; opacity: 0.8; margin-top: 8px; }}
.summary {{ background: #f8f9fa; padding: 15px 20px; border-left: 4px solid #1565c0; margin-bottom: 25px; border-radius: 4px; }}
.news-item {{ margin-bottom: 22px; padding-bottom: 18px; border-bottom: 1px solid #eee; }}
.news-item:last-child {{ border-bottom: none; }}
.rank {{ display: inline-block; background: #1565c0; color: #fff; width: 28px; height: 28px; line-height: 28px; text-align: center; border-radius: 50%; font-size: 14px; font-weight: bold; margin-right: 10px; }}
.news-title {{ font-size: 16px; font-weight: bold; color: #0d47a1; margin-bottom: 6px; }}
.news-content {{ font-size: 14px; color: #555; margin-bottom: 6px; }}
.news-meta {{ font-size: 12px; color: #999; }}
.news-meta a {{ color: #1565c0; text-decoration: none; }}
.footer {{ text-align: center; font-size: 12px; color: #aaa; margin-top: 30px; padding-top: 15px; border-top: 1px solid #eee; }}
</style>
</head>
<body>

<div class="header">
<h1>玻璃瓶行业每日资讯</h1>
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
    sender_email = os.environ.get("SENDER_EMAIL", "")
    sender_password = os.environ.get("SENDER_PASSWORD", "")
    receiver_emails_str = os.environ.get("RECEIVER_EMAILS", "")
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.qq.com")
    smtp_port = os.environ.get("SMTP_PORT", "465")

    if not sender_email or not sender_password or not receiver_emails_str:
        print("错误：请配置 SENDER_EMAIL、SENDER_PASSWORD、RECEIVER_EMAILS 环境变量", file=sys.stderr)
        sys.exit(1)

    receiver_emails = [e.strip() for e in receiver_emails_str.split(",") if e.strip()]

    # ============================================================
    # 玻璃瓶行业分类搜索关键词
    # ============================================================
    keywords = [
        # 综合行业
        "glass bottle industry news",
        "玻璃瓶 行业动态",
        "glass packaging market trends",
        "玻璃包装 行业新闻",
        # 市场数据
        "glass bottle market size growth",
        "玻璃瓶 市场规模 产量 数据",
        "glass container industry report",
        # 政策法规
        "glass packaging regulation environmental",
        "玻璃瓶 环保政策 双碳 标准",
        "glass bottle tariff trade",
        # 技术材料
        "glass bottle innovation lightweight sustainable",
        "玻璃瓶 新技术 轻量化 环保",
        "borosilicate glass pharmaceutical",
        # 企业动态
        "glass bottle manufacturer acquisition expansion",
        "玻璃瓶 企业 扩产 收购 上市",
        "Owens-Illinois Verallia glass news",
        # 应用领域
        "pharmaceutical glass bottle vial",
        "cosmetic glass packaging bottle",
        "beverage glass bottle wine beer",
        # 展会
        "glass exhibition trade show 2026",
        "玻璃展 玻璃瓶展会",
    ]

    print("=" * 50)
    print(f"玻璃瓶行业每日资讯 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    print(f"\n[1/5] 正在搜索过去24小时行业动态（{len(keywords)}组关键词）...")
    all_news = search_news(keywords, max_per_keyword=10)
    print(f"      共获取 {len(all_news)} 条原始结果")

    print("\n[2/5] 相关性过滤...")
    relevant = [item for item in all_news if is_relevant(item)]
    print(f"      过滤后 {len(relevant)} 条（移除 {len(all_news) - len(relevant)} 条无关内容）")

    print("\n[3/5] 去重处理...")
    unique_news = deduplicate(relevant)
    print(f"      去重后 {len(unique_news)} 条")

    print("\n[4/5] 多维度价值评分排序...")
    for item in unique_news:
        item["score"] = score_news(item)
    scored = sorted(unique_news, key=lambda x: x["score"], reverse=True)
    selected = scored[:8]

    if len(selected) < 5:
        print(f"      注意：仅找到 {len(selected)} 条有效信息（不足5条）")

    for i, item in enumerate(selected, 1):
        print(f"      {i}. [分值{item['score']}] {item.get('title', '无标题')[:55]}")

    print("\n[5/5] 生成邮件并发送...")
    today_str = datetime.now().strftime("%Y年%m月%d日")
    html_content = generate_html(selected, today_str)
    subject = f"玻璃瓶行业每日资讯 - {today_str}"

    success = send_email(
        html_content, subject, sender_email, sender_password,
        receiver_emails, smtp_server, smtp_port
    )

    if success:
        print("\n" + "=" * 50)
        print(f"任务完成！已发送 {len(selected)} 条资讯到 {', '.join(receiver_emails)}")
        print("=" * 50)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
