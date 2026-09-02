#!/usr/bin/env python3
"""
玻璃瓶包装行业每日资讯简报 - 销售经理版
重点：全球市场动态、采购需求、客户线索、展会招标、竞品动态、贸易政策
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
# 核心关键词库（用于相关性判断）
# ============================================================
CORE_KEYWORDS = [
    "glass bottle", "glass packaging", "玻璃瓶", "玻璃包装",
    "玻璃容器", "glass container", "药用玻璃", "化妆品玻璃瓶",
    "饮料瓶", "wine bottle", "beer bottle", "玻璃器皿",
    "glassware", "硼硅玻璃", "glass jar", "glass vial",
    "玻璃酒瓶", "香水瓶", "罐头瓶", "glass manufacturer",
    "glass supplier", "玻璃瓶厂", "玻璃包装厂",
]

# 客户/采购相关高价值词
CUSTOMER_KEYWORDS = [
    "采购", "sourcing", "buyer", "importer", "distributor",
    "wholesale", "招标", "tender", "rfq", "request for quote",
    "purchase", "order", "订单", "供应商", "supplier",
    "进口商", "经销商", "代理商", "采购商", "bulk order",
]

# 低质量/纯零售过滤词
LOW_QUALITY_WORDS = [
    "一件代发", "淘宝", "拼多多", "京东", "天猫", "amazon",
    "ebay", "etsy", "diy", "tutorial", "how to", "craft",
    "回收价格", "废品", "二手", "个人", "零售",
]


def search_news(keywords, max_per_keyword=10, max_retries=3, timelimit="w"):
    """搜索新闻（过去7天）"""
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
                        timelimit=timelimit,
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
                                "type": "news",
                            }
                        )
                count = sum(1 for r in results if r["keyword"] == keyword)
                print(f"[新闻] '{keyword}' -> {count} 条")
                success = True
                break
            except Exception as e:
                print(f"[新闻] '{keyword}' 第{attempt+1}次失败: {e}", file=sys.stderr)
                if attempt < max_retries - 1:
                    time.sleep(4)
        if not success:
            print(f"[新闻] '{keyword}' 最终失败", file=sys.stderr)
        time.sleep(1.5)
    return results


def search_web(keywords, max_per_keyword=8, max_retries=3):
    """搜索网页（补充行业资讯、客户线索）"""
    results = []
    for keyword in keywords:
        success = False
        for attempt in range(max_retries):
            try:
                with DDGS(timeout=25) as ddgs:
                    for r in ddgs.text(
                        query=keyword,
                        region="wt-wt",
                        safesearch="off",
                        max_results=max_per_keyword,
                    ):
                        results.append(
                            {
                                "title": r.get("title", "").strip(),
                                "url": r.get("url", "").strip(),
                                "source": r.get("source", "") or r.get("href", "").split("/")[2] if r.get("href") else "",
                                "date": "近期",
                                "body": r.get("body", "").strip(),
                                "keyword": keyword,
                                "type": "web",
                            }
                        )
                count = sum(1 for r in results if r["keyword"] == keyword)
                print(f"[网页] '{keyword}' -> {count} 条")
                success = True
                break
            except Exception as e:
                print(f"[网页] '{keyword}' 第{attempt+1}次失败: {e}", file=sys.stderr)
                if attempt < max_retries - 1:
                    time.sleep(4)
        if not success:
            print(f"[网页] '{keyword}' 最终失败", file=sys.stderr)
        time.sleep(1.5)
    return results


def is_relevant(item):
    """相关性过滤"""
    text = (item.get("title", "") + " " + item.get("body", "")).lower()
    title = item.get("title", "").lower()

    if len(title) < 10:
        return False

    # 必须含核心行业词
    has_core = any(kw.lower() in text for kw in CORE_KEYWORDS)
    if not has_core:
        return False

    # 过滤纯零售/无关内容
    has_low_quality = any(lw.lower() in title for lw in LOW_QUALITY_WORDS)
    if has_low_quality:
        return False

    return True


def title_similarity(t1, t2):
    """标题相似度"""
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
        is_dup = any(title_similarity(title, st) > 0.6 for st in seen_titles)
        if is_dup:
            continue
        if url:
            seen_urls.add(url)
        seen_titles.append(title)
        unique.append(item)
    return unique


def score_news(item):
    """销售经理视角多维度评分"""
    score = 0
    text = (item.get("title", "") + " " + item.get("body", "")).lower()
    title = item.get("title", "").lower()
    source = item.get("source", "").lower()

    # 1. 客户线索/采购需求（最高优先级 +50）
    if any(kw.lower() in text for kw in CUSTOMER_KEYWORDS):
        score += 50

    # 2. 头部企业/品牌动态（+40）
    high_value_brands = [
        "owens-illinois", "o-i", "verallia", "arc international",
        "肖特", "schott", "康宁", "corning", "山东药玻", "正川股份",
        "力诺特玻", "华兴玻璃", "德力股份", "glasspack",
        "stölzle", "stolzle", "bormioli", "raja", "pegas",
        "heineken", "coca-cola", "l'oreal", "estee lauder",
        "pfizer", "novartis", "roche", "茅台", "五粮液",
    ]
    if any(b in text for b in high_value_brands):
        score += 40

    # 3. 资本/产能动作（+35）
    capital_words = [
        "融资", "收购", "并购", "ipo", "上市", "扩产", "投产",
        "新建工厂", "产能扩张", "funding", "acquisition",
        "merger", "investment", "capacity expansion", "new plant",
    ]
    if any(w in text for w in capital_words):
        score += 35

    # 4. 贸易政策/关税（+35，直接影响出口）
    trade_words = [
        "关税", "tariff", "trade war", "出口管制", "制裁",
        "sanction", "反倾销", "antidumping", "贸易壁垒",
        "customs", "报关", "退税", "export control",
    ]
    if any(w in text for w in trade_words):
        score += 35

    # 5. 市场数据/行业报告（+25）
    market_words = [
        "市场规模", "市场份额", "增长率", "行业报告", "白皮书",
        "market size", "market share", "growth rate", "industry report",
        "revenue", "billion", "million", "亿元", "产能", "产量",
        "出口量", "进口数据",
    ]
    if any(w in text for w in market_words):
        score += 25

    # 6. 展会/行业活动（+20，获客渠道）
    expo_words = [
        "展会", "博览会", "展览", "发布会", "论坛", "峰会",
        "expo", "exhibition", "trade show", "conference",
        "summit", "forum", "glasstec", "中国玻璃展",
        "packaging show", "cosmoprof", "pharmapack",
    ]
    if any(w in text for w in expo_words):
        score += 20

    # 7. 技术/材料创新（+15）
    tech_words = [
        "创新", "新技术", "新材料", "可持续", "环保", "轻量化",
        "innovation", "sustainable", "eco-friendly", "technology",
        "recycled", "薄壁", "高白料", "晶质料", "纳米", "涂层",
    ]
    if any(w in text for w in tech_words):
        score += 15

    # 8. 来源权威性（+15）
    authoritative_sources = [
        "reuters", "bloomberg", "forbes", "glassonline",
        "glassmagazine", "glass-international", "36氪", "36kr",
        "第一财经", "界面新闻", "中国玻璃网", "中玻网",
        "packagingdigest", "packagingstrategies",
    ]
    if any(a in source for a in authoritative_sources):
        score += 15

    # 9. 标题直接含采购/客户词（+10）
    if any(kw.lower() in title for kw in CUSTOMER_KEYWORDS):
        score += 10

    return score


def generate_html(news_list, today_str):
    """生成HTML邮件正文（销售经理版）"""
    items_html = ""
    for i, item in enumerate(news_list, 1):
        title = item.get("title", "无标题")
        body = item.get("body", "")
        source = item.get("source", "未知来源")
        date = item.get("date", "")
        url = item.get("url", "#")
        score = item.get("score", 0)
        ntype = item.get("type", "news")

        if len(body) > 200:
            body = body[:200] + "..."

        if score >= 90:
            tag = '<span style="background:#dc3545;color:#fff;padding:2px 6px;border-radius:3px;font-size:11px;">客户线索</span>'
        elif score >= 60:
            tag = '<span style="background:#fd7e14;color:#fff;padding:2px 6px;border-radius:3px;font-size:11px;">重要</span>'
        else:
            tag = '<span style="background:#6c757d;color:#fff;padding:2px 6px;border-radius:3px;font-size:11px;">关注</span>'

        type_tag = '<span style="background:#e9ecef;color:#495057;padding:2px 6px;border-radius:3px;font-size:11px;margin-left:5px;">新闻</span>' if ntype == "news" else '<span style="background:#d1ecf1;color:#0c5460;padding:2px 6px;border-radius:3px;font-size:11px;margin-left:5px;">网页</span>'

        items_html += f"""
<div class="news-item">
<div class="news-title"><span class="rank">{i}</span>{title} {tag}{type_tag}</div>
<div class="news-content">{body}</div>
<div class="news-meta">时间：{date} ｜ 来源：<a href="{url}">{source}</a></div>
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
.header {{ background: linear-gradient(135deg, #1b5e20, #2e7d32); color: #fff; padding: 30px; border-radius: 10px; margin-bottom: 25px; }}
.header h1 {{ margin: 0; font-size: 24px; }}
.header .date {{ font-size: 14px; opacity: 0.8; margin-top: 8px; }}
.summary {{ background: #f8f9fa; padding: 15px 20px; border-left: 4px solid #2e7d32; margin-bottom: 25px; border-radius: 4px; }}
.news-item {{ margin-bottom: 22px; padding-bottom: 18px; border-bottom: 1px solid #eee; }}
.news-item:last-child {{ border-bottom: none; }}
.rank {{ display: inline-block; background: #2e7d32; color: #fff; width: 28px; height: 28px; line-height: 28px; text-align: center; border-radius: 50%; font-size: 14px; font-weight: bold; margin-right: 10px; }}
.news-title {{ font-size: 16px; font-weight: bold; color: #1b5e20; margin-bottom: 6px; }}
.news-content {{ font-size: 14px; color: #555; margin-bottom: 6px; }}
.news-meta {{ font-size: 12px; color: #999; }}
.news-meta a {{ color: #2e7d32; text-decoration: none; }}
.tip {{ background: #fff3cd; padding: 12px 16px; border-radius: 6px; margin-bottom: 20px; font-size: 13px; color: #856404; }}
.footer {{ text-align: center; font-size: 12px; color: #aaa; margin-top: 30px; padding-top: 15px; border-top: 1px solid #eee; }}
</style>
</head>
<body>

<div class="header">
<h1>玻璃瓶包装行业每日资讯</h1>
<div class="date">{today_str} ｜ 销售经理版 ｜ 过去7天 ｜ 共筛选 {len(news_list)} 条</div>
</div>

<div class="tip">
<strong>销售提示：</strong>标注「客户线索」的内容含采购/招标/进口商信息，建议优先跟进；「重要」为影响市场的大事件；「关注」为行业趋势参考。
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
        print("错误：请配置邮箱环境变量", file=sys.stderr)
        sys.exit(1)

    receiver_emails = [e.strip() for e in receiver_emails_str.split(",") if e.strip()]

    # ============================================================
    # 销售经理版搜索关键词（新闻 + 网页）
    # ============================================================
    news_keywords = [
        # 市场动态
        "glass packaging market trends",
        "glass bottle industry news",
        "玻璃瓶 行业动态 市场",
        "glass container market report",
        # 客户/采购
        "glass bottle buyer importer sourcing",
        "玻璃瓶 采购 招标 订单",
        "glass packaging wholesale distributor",
        # 贸易政策
        "glass bottle tariff trade export",
        "玻璃瓶 出口 关税 贸易",
        # 企业动态
        "glass bottle manufacturer acquisition expansion",
        "玻璃瓶 企业 扩产 上市 收购",
        # 展会
        "glass exhibition packaging trade show 2026",
        "玻璃展 包装展 2026",
        # 技术
        "glass bottle innovation lightweight sustainable",
        "玻璃瓶 新技术 环保 轻量化",
    ]

    web_keywords = [
        "glass bottle importer directory",
        "glass packaging buyers list",
        "cosmetic glass bottle brands",
        "pharmaceutical glass vial suppliers",
        "glass bottle wholesale companies",
        "top glass packaging manufacturers",
        "玻璃瓶 进口商 采购商 名录",
        "化妆品玻璃瓶 品牌 采购",
        "药用玻璃瓶 招标 供应商",
    ]

    print("=" * 50)
    print(f"玻璃瓶包装行业每日资讯（销售经理版）- {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    print(f"\n[1/6] 搜索新闻（{len(news_keywords)}组，过去7天）...")
    news_results = search_news(news_keywords, max_per_keyword=10, timelimit="w")

    print(f"\n[2/6] 搜索网页（{len(web_keywords)}组，客户线索补充）...")
    web_results = search_web(web_keywords, max_per_keyword=8)

    all_news = news_results + web_results
    print(f"\n      原始结果合计：{len(all_news)} 条（新闻{len(news_results)} + 网页{len(web_results)}）")

    print("\n[3/6] 相关性过滤...")
    relevant = [item for item in all_news if is_relevant(item)]
    print(f"      过滤后 {len(relevant)} 条")

    print("\n[4/6] 去重处理...")
    unique_news = deduplicate(relevant)
    print(f"      去重后 {len(unique_news)} 条")

    print("\n[5/6] 销售视角评分排序...")
    for item in unique_news:
        item["score"] = score_news(item)
    scored = sorted(unique_news, key=lambda x: x["score"], reverse=True)
    selected = scored[:8]

    if len(selected) < 3:
        print(f"      注意：仅找到 {len(selected)} 条有效信息")

    for i, item in enumerate(selected, 1):
        print(f"      {i}. [分值{item['score']}] {item.get('title', '无标题')[:55]}")

    print("\n[6/6] 生成邮件并发送...")
    today_str = datetime.now().strftime("%Y年%m月%d日")
    html_content = generate_html(selected, today_str)
    subject = f"玻璃瓶包装行业每日资讯（销售版）- {today_str}"

    success = send_email(
        html_content, subject, sender_email, sender_password,
        receiver_emails, smtp_server, smtp_port
    )

    if success:
        print("\n" + "=" * 50)
        print(f"任务完成！已发送 {len(selected)} 条到 {', '.join(receiver_emails)}")
        print("=" * 50)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
