#!/usr/bin/env python3
"""
情趣内衣行业每日资讯简报 - 外贸销售经理专版
整合：分市场搜索、B2B采购线索、品牌动态、电商趋势、政策法规、销售行动建议、客户清单
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
# 核心关键词库
# ============================================================
CORE_KEYWORDS = [
    "lingerie", "intimate apparel", "underwear", "bra", "panties",
    "情趣内衣", "内衣", "文胸", "成人用品", "私密",
    "adult apparel", "sexy lingerie", "lace", "bodysuit",
    "corset", "babydoll", "teddy", "stockings", "hosiery",
    "shapewear", "loungewear", "sleepwear", "睡衣", "家居服",
    "intimates", "lingerie manufacturer", "lingerie supplier",
    "情趣用品", "adult products", "sex toy",
]

CUSTOMER_KEYWORDS = [
    "采购", "sourcing", "buyer", "importer", "distributor",
    "wholesale", "招标", "tender", "rfq", "request for quote",
    "purchase", "order", "订单", "供应商", "supplier",
    "进口商", "经销商", "代理商", "采购商", "bulk order",
    "private label", "oem", "odm", "定制", "custom",
    "white label", "contract manufacturing",
]

LOW_QUALITY_WORDS = [
    "一件代发", "淘宝", "拼多多", "京东", "天猫",
    "diy", "tutorial", "how to", "craft", "review",
    "best lingerie", "top 10", "buying guide", "试穿",
    "测评", "穿搭", "街拍", "网红", "直播带货",
]

# 区域市场关键词
REGION_KEYWORDS = {
    "北美": ["US lingerie market", "USA intimate apparel", "American lingerie brand",
             "Canada lingerie", "North America adult products"],
    "欧洲": ["EU lingerie market", "Europe intimate apparel", "Germany lingerie",
             "France lingerie brand", "UK adult products", "European lingerie"],
    "东南亚": ["Southeast Asia lingerie", "Vietnam adult products",
               "Thailand lingerie", "Indonesia intimate apparel", "Philippines lingerie"],
    "其他": ["Australia lingerie", "Japan adult products", "Korea lingerie",
             "Brazil lingerie", "Mexico intimate apparel"],
}


def search_news(keywords, max_per_keyword=8, max_retries=2, timelimit="w"):
    """搜索新闻（过去7天）"""
    results = []
    for keyword in keywords:
        success = False
        for attempt in range(max_retries):
            try:
                with DDGS(timeout=20) as ddgs:
                    for r in ddgs.news(
                        query=keyword, region="wt-wt", safesearch="off",
                        timelimit=timelimit, max_results=max_per_keyword,
                    ):
                        results.append({
                            "title": r.get("title", "").strip(),
                            "url": r.get("url", "").strip(),
                            "source": r.get("source", "").strip(),
                            "date": r.get("date", "").strip(),
                            "body": r.get("body", "").strip(),
                            "keyword": keyword, "type": "news",
                        })
                success = True
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(3)
        if not success:
            print(f"[新闻失败] {keyword}", file=sys.stderr)
        time.sleep(1)
    return results


def search_web(keywords, max_per_keyword=6, max_retries=2):
    """搜索网页（客户线索补充）"""
    results = []
    for keyword in keywords:
        success = False
        for attempt in range(max_retries):
            try:
                with DDGS(timeout=20) as ddgs:
                    for r in ddgs.text(
                        query=keyword, region="wt-wt", safesearch="off",
                        max_results=max_per_keyword,
                    ):
                        href = r.get("href", "")
                        source = href.split("/")[2] if "://" in href else href
                        results.append({
                            "title": r.get("title", "").strip(),
                            "url": href,
                            "source": source,
                            "date": "近期",
                            "body": r.get("body", "").strip(),
                            "keyword": keyword, "type": "web",
                        })
                success = True
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(3)
        if not success:
            print(f"[网页失败] {keyword}", file=sys.stderr)
        time.sleep(1)
    return results


def detect_region(text):
    """检测资讯所属区域市场"""
    text_lower = text.lower()
    region_map = {
        "北美": ["usa", "united states", "america", "canada", "north america", "美国", "加拿大"],
        "欧洲": ["europe", "eu ", "germany", "france", "uk ", "united kingdom", "italy", "spain", "欧洲", "德国", "法国", "英国"],
        "东南亚": ["southeast asia", "vietnam", "thailand", "indonesia", "malaysia", "philippines", "东南亚", "越南", "泰国", "印尼"],
        "中国": ["china", "中国", "国内"],
    }
    for region, words in region_map.items():
        if any(w in text_lower for w in words):
            return region
    return "全球"


def detect_category(item):
    """资讯分类"""
    text = (item.get("title", "") + " " + item.get("body", "")).lower()
    title = item.get("title", "").lower()

    if any(kw in text for kw in CUSTOMER_KEYWORDS):
        return "客户线索"
    if any(w in text for w in ["tariff", "trade war", "关税", "反倾销", "sanction", "制裁", "regulation", "法规", "policy", "政策", "import", "进口", "labeling", "标签", "compliance", "合规"]):
        return "政策法规"
    if any(w in text for w in ["exhibition", "expo", "trade show", "展会", "博览会", "forum", "峰会", "conference", "avn", " Venus", "成人展"]):
        return "展会动态"
    if any(w in text for w in ["amazon", "tiktok", "shein", "shopify", "dropshipping", "电商", "平台", "online retail", "e-commerce", "直播"]):
        return "电商平台"
    if any(w in text for w in ["sustainable", "eco-friendly", "recycled", "环保", "可持续", "innovation", "技术", "新材料", "fabric", "面料", "3d", "smart"]):
        return "技术趋势"
    if any(w in text for w in ["acquisition", "merger", "收购", "并购", "expansion", "扩张", "ipo", "上市", "funding", "融资", "bankruptcy", "破产", "layoff", "裁员"]):
        return "企业动态"
    return "市场动态"


def generate_action_advice(item, category):
    """生成销售行动建议"""
    text = (item.get("title", "") + " " + item.get("body", "")).lower()
    region = detect_region(text)

    advice_map = {
        "客户线索": f"🔥 该信息含采购/进口商线索，建议：①提取公司名称和网站 ②通过LinkedIn核实采购决策人 ③3天内发送开发信，突出OEM/ODM能力和MOQ",
        "政策法规": f"⚠️ {region}市场政策变化，建议：①评估对现有订单影响 ②确认产品是否符合新法规 ③通知客户合规要求变化",
        "展会动态": "📅 展会信息，建议：①确认参展计划 ②提前1个月邀约老客户见面 ③准备新品样品和目录",
        "电商平台": "🛒 电商平台动态，建议：①关注平台卖家采购需求 ②分析热销款式 ③考虑通过平台联系大卖家",
        "技术趋势": "📈 技术/材料趋势，建议：①关注客户新品动态 ②提前准备对应面料/工艺方案 ③主动推荐新材料给老客户",
        "企业动态": "🏢 竞品/品牌动态，建议：①分析对自身影响 ②关注品牌扩张带来的采购机会 ③调整竞争策略",
        "市场动态": f"🌍 {region}市场动态，建议：①评估市场需求变化 ②调整该区域开发优先级 ③收集更多客户信息",
    }
    return advice_map.get(category, "📌 建议关注该动态，评估对业务的影响")


def is_relevant(item):
    """相关性过滤"""
    text = (item.get("title", "") + " " + item.get("body", "")).lower()
    title = item.get("title", "").lower()
    if len(title) < 10:
        return False
    if not any(kw.lower() in text for kw in CORE_KEYWORDS):
        return False
    if any(lw.lower() in title for lw in LOW_QUALITY_WORDS):
        return False
    return True


def title_similarity(t1, t2):
    s1 = set(re.findall(r"\w+", t1.lower()))
    s2 = set(re.findall(r"\w+", t2.lower()))
    if not s1 or not s2:
        return 0
    return len(s1 & s2) / min(len(s1), len(s2))


def deduplicate(news_list):
    seen_urls, seen_titles, unique = set(), [], []
    for item in news_list:
        url = item.get("url", "")
        title = item.get("title", "")
        if url and url in seen_urls:
            continue
        if any(title_similarity(title, st) > 0.6 for st in seen_titles):
            continue
        if url:
            seen_urls.add(url)
        seen_titles.append(title)
        unique.append(item)
    return unique


def score_news(item):
    """外贸销售视角评分"""
    score = 0
    text = (item.get("title", "") + " " + item.get("body", "")).lower()
    title = item.get("title", "").lower()
    source = item.get("source", "").lower()

    # 客户线索（最高优先级）
    if any(kw.lower() in text for kw in CUSTOMER_KEYWORDS):
        score += 50
    if any(kw.lower() in title for kw in CUSTOMER_KEYWORDS):
        score += 10

    # 头部品牌动态
    brands = ["victoria's secret", "victoria secret", "agent provocateur", "la perla",
              "hunkemoller", "adore me", "yandy", "lovehoney", "bellesa",
              "skims", "savage x fenty", "thirdlove", "knix", "aerie",
              "都市丽人", "曼妮芬", "爱慕", "蕉内", "内外", "ubras",
              "calvin klein", "honey birdette", "frederick's of hollywood"]
    if any(b in text for b in brands):
        score += 40

    # 贸易政策
    trade_words = ["tariff", "trade war", "关税", "反倾销", "sanction", "import duty", "进口税", "labeling requirement"]
    if any(w in text for w in trade_words):
        score += 40

    # 资本动作
    capital = ["acquisition", "merger", "收购", "并购", "expansion", "扩张", "ipo", "上市", "funding", "融资", "bankruptcy"]
    if any(w in text for w in capital):
        score += 30

    # 市场数据
    market = ["market size", "market share", "growth", "市场规模", "增长率", "billion", "亿元", "revenue", "sales"]
    if any(w in text for w in market):
        score += 25

    # 电商平台
    ecommerce = ["amazon", "tiktok shop", "shein", "shopify", "dropshipping", "跨境电商"]
    if any(w in text for w in ecommerce):
        score += 20

    # 展会
    expo = ["exhibition", "expo", "trade show", "展会", "avn", " Venus", "成人展", "lingerie show"]
    if any(w in text for w in expo):
        score += 20

    # 技术创新
    tech = ["innovation", "sustainable", "eco-friendly", "创新", "环保", "新材料", "smart", "3d"]
    if any(w in text for w in tech):
        score += 15

    # 来源权威
    auth = ["reuters", "bloomberg", "forbes", "fashionunited", "lingerieinsider",
            "adultvideo", "xbiz", "36kr", "第一财经", "界面新闻", "亿邦动力"]
    if any(a in source for a in auth):
        score += 15

    return score


def extract_company_names(item):
    """简单提取可能的公司名"""
    text = item.get("title", "") + " " + item.get("body", "")
    patterns = [
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+(?:Inc|LLC|Ltd|GmbH|Co|Corp|Corporation|Group|Holdings|Brands|Intimates|Lingerie)',
        r'([\u4e00-\u9fa5]{2,8}(?:公司|集团|股份|有限公司|内衣|服饰))',
    ]
    companies = set()
    for p in patterns:
        matches = re.findall(p, text)
        companies.update(matches)
    return list(companies)[:3]


def generate_html(news_list, today_str):
    """生成外贸销售经理版HTML邮件"""
    categories = ["客户线索", "政策法规", "企业动态", "电商平台", "市场动态", "技术趋势", "展会动态"]
    categorized = {c: [] for c in categories}

    for item in news_list:
        cat = detect_category(item)
        if cat in categorized:
            categorized[cat].append(item)
        else:
            categorized["市场动态"].append(item)

    sections_html = ""
    all_companies = []

    for cat in categories:
        items = categorized.get(cat, [])
        if not items:
            continue

        items_html = ""
        for i, item in enumerate(items, 1):
            title = item.get("title", "无标题")
            body = item.get("body", "")
            source = item.get("source", "未知来源")
            date = item.get("date", "")
            url = item.get("url", "#")
            region = detect_region(title + " " + body)
            advice = generate_action_advice(item, cat)
            companies = extract_company_names(item)
            all_companies.extend(companies)

            if len(body) > 180:
                body = body[:180] + "..."

            company_str = ""
            if companies:
                company_str = f'<div class="company">🏢 涉及企业：{"、".join(companies)}</div>'

            items_html += f"""
<div class="news-item">
<div class="news-title"><span class="rank">{i}</span>{title}
<span class="region-tag">{region}</span></div>
<div class="news-content">{body}</div>
{company_str}
<div class="advice">{advice}</div>
<div class="news-meta">时间：{date} ｜ 来源：<a href="{url}">{source}</a></div>
</div>"""

        cat_icons = {"客户线索": "🎯", "政策法规": "⚖️", "企业动态": "🏢",
                     "电商平台": "🛒", "市场动态": "🌍", "技术趋势": "📈", "展会动态": "📅"}
        icon = cat_icons.get(cat, "📌")
        sections_html += f"""
<div class="section">
<div class="section-title">{icon} {cat}（{len(items)}条）</div>
{items_html}
</div>"""

    # 客户清单
    unique_companies = list(dict.fromkeys(all_companies))[:10]
    company_section = ""
    if unique_companies:
        company_items = "".join(f"<li>{c}</li>" for c in unique_companies)
        company_section = f"""
<div class="section">
<div class="section-title">📋 本期潜在客户/企业清单</div>
<div class="company-list"><ul>{company_items}</ul>
<p style="font-size:12px;color:#888;">提示：以上企业名从资讯中自动提取，建议通过LinkedIn、海关数据、企业官网进一步核实联系方式。</p>
</div>
</div>"""

    # 统计
    total = len(news_list)
    customer_count = len(categorized.get("客户线索", []))
    regions = {}
    for item in news_list:
        r = detect_region(item.get("title", "") + " " + item.get("body", ""))
        regions[r] = regions.get(r, 0) + 1
    region_str = "、".join(f"{k}{v}条" for k, v in sorted(regions.items(), key=lambda x: -x[1]))

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; line-height: 1.7; color: #333; max-width: 760px; margin: 0 auto; padding: 20px; }}
.header {{ background: linear-gradient(135deg, #6a1b9a, #8e24aa); color: #fff; padding: 30px; border-radius: 10px; margin-bottom: 20px; }}
.header h1 {{ margin: 0; font-size: 22px; }}
.header .date {{ font-size: 13px; opacity: 0.85; margin-top: 8px; }}
.stats {{ background: #f3e5f5; padding: 12px 18px; border-radius: 6px; margin-bottom: 20px; font-size: 13px; color: #4a148c; }}
.section {{ margin-bottom: 25px; }}
.section-title {{ font-size: 16px; font-weight: bold; color: #6a1b9a; border-left: 4px solid #8e24aa; padding-left: 10px; margin-bottom: 12px; }}
.news-item {{ margin-bottom: 16px; padding: 12px; background: #fafafa; border-radius: 6px; }}
.rank {{ display: inline-block; background: #8e24aa; color: #fff; width: 22px; height: 22px; line-height: 22px; text-align: center; border-radius: 50%; font-size: 12px; font-weight: bold; margin-right: 8px; }}
.news-title {{ font-size: 14px; font-weight: bold; color: #4a148c; margin-bottom: 5px; }}
.region-tag {{ background: #f3e5f5; color: #6a1b9a; padding: 1px 6px; border-radius: 3px; font-size: 11px; margin-left: 6px; }}
.news-content {{ font-size: 13px; color: #555; margin-bottom: 5px; }}
.company {{ font-size: 12px; color: #6a1b9a; margin-bottom: 5px; }}
.advice {{ background: #fff8e1; padding: 8px 10px; border-radius: 4px; font-size: 12px; color: #f57f17; margin-bottom: 5px; }}
.news-meta {{ font-size: 11px; color: #999; }}
.news-meta a {{ color: #8e24aa; text-decoration: none; }}
.company-list {{ background: #fafafa; padding: 12px 18px; border-radius: 6px; }}
.company-list li {{ margin-bottom: 4px; font-size: 13px; }}
.footer {{ text-align: center; font-size: 11px; color: #aaa; margin-top: 25px; padding-top: 12px; border-top: 1px solid #eee; }}
</style>
</head>
<body>

<div class="header">
<h1>情趣内衣行业每日资讯（外贸销售版）</h1>
<div class="date">{today_str} ｜ 过去7天 ｜ 共 {total} 条 ｜ 客户线索 {customer_count} 条</div>
</div>

<div class="stats">
📊 <strong>区域分布：</strong>{region_str}<br>
💡 <strong>使用提示：</strong>每条资讯附带销售行动建议，客户线索类请优先跟进；企业清单可作为开发方向参考。
</div>

{sections_html}
{company_section}

<div class="footer">
本简报由 GitHub Actions 自动搜集整理 ｜ 数据来源：公开网络信息 ｜ 仅供参考<br>
发送时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}
</div>

</body>
</html>"""
    return html


def send_email(html_content, subject, sender, password, recipients, smtp_server, smtp_port):
    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg.attach(MIMEText(html_content, "html", "utf-8"))
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
    # 外贸销售版搜索关键词
    # ============================================================
    news_keywords = [
        # 综合市场
        "lingerie industry news",
        "intimate apparel market trends",
        "情趣内衣 行业动态 市场",
        "adult products industry news",
        # 客户线索
        "lingerie importer distributor wholesale",
        "intimate apparel buyer sourcing",
        "情趣内衣 采购 进口商 批发商",
        "lingerie private label OEM manufacturer",
        # 政策法规
        "lingerie import regulation tariff",
        "adult products labeling compliance",
        "情趣内衣 出口 关税 法规",
        # 品牌动态
        "Victoria's Secret Agent Provocateur news",
        "lingerie brand acquisition expansion",
        "情趣内衣 品牌 融资 上市",
        # 电商平台
        "Amazon lingerie seller trends",
        "TikTok Shop Shein intimate apparel",
        "情趣内衣 跨境电商 平台",
        # 技术趋势
        "lingerie sustainable fabric innovation",
        "情趣内衣 新材料 环保 技术",
        # 展会
        "lingerie trade show exhibition 2026",
        "adult products expo AVN Venus",
    ]

    # 分市场网页搜索
    web_keywords = []
    for region, kws in REGION_KEYWORDS.items():
        web_keywords.extend(kws[:2])
    web_keywords.extend([
        "lingerie private label OEM supplier",
        "custom lingerie manufacturer China",
        "top lingerie brands wholesale",
        "lingerie RFQ request for quote",
        "adult products distributor directory",
    ])

    print("=" * 50)
    print(f"情趣内衣行业每日资讯（外贸销售版）- {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    print(f"\n[1/6] 搜索新闻（{len(news_keywords)}组）...")
    news_results = search_news(news_keywords, max_per_keyword=8, timelimit="w")
    print(f"      新闻结果：{len(news_results)} 条")

    print(f"\n[2/6] 搜索网页（{len(web_keywords)}组，分市场+客户）...")
    web_results = search_web(web_keywords, max_per_keyword=6)
    print(f"      网页结果：{len(web_results)} 条")

    all_news = news_results + web_results
    print(f"\n      原始合计：{len(all_news)} 条")

    print("\n[3/6] 相关性过滤...")
    relevant = [item for item in all_news if is_relevant(item)]
    print(f"      过滤后：{len(relevant)} 条")

    print("\n[4/6] 去重...")
    unique_news = deduplicate(relevant)
    print(f"      去重后：{len(unique_news)} 条")

    print("\n[5/6] 评分排序+分类...")
    for item in unique_news:
        item["score"] = score_news(item)
        item["category"] = detect_category(item)
        item["region"] = detect_region(item.get("title", "") + " " + item.get("body", ""))
    scored = sorted(unique_news, key=lambda x: x["score"], reverse=True)
    selected = scored[:12]

    print(f"      最终入选：{len(selected)} 条")
    for i, item in enumerate(selected, 1):
        print(f"      {i}. [{item['category']}|{item['region']}|{item['score']}分] {item['title'][:50]}")

    print("\n[6/6] 生成邮件并发送...")
    today_str = datetime.now().strftime("%Y年%m月%d日")
    html_content = generate_html(selected, today_str)
    subject = f"情趣内衣行业每日资讯（外贸销售版）- {today_str}"

    success = send_email(html_content, subject, sender_email, sender_password,
                         receiver_emails, smtp_server, smtp_port)

    if success:
        print("\n" + "=" * 50)
        print(f"完成！已发送 {len(selected)} 条到 {', '.join(receiver_emails)}")
        print("=" * 50)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
