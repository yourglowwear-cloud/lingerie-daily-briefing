#!/usr/bin/env python3
"""
食用菌外贸政策每日资讯简报 - 政策重点版
重点：国内外食品政策、出口政策、贸易壁垒、行业标准、市场准入
适用：江苏省食用菌企业（菌包、鲜菇出口）
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
    "mushroom", "edible fungi", "edible mushroom", "食用菌", "蘑菇",
    "shiitake", "香菇", "oyster mushroom", "平菇", "pleurotus",
    "agaricus", "双孢菇", "enoki", "金针菇", "king oyster", "杏鲍菇",
    "mushroom spawn", "菌包", "菌种", "fresh mushroom", "鲜菇",
    "fungi", "菌菇", "木耳", "black fungus", "white fungus", "银耳",
    "mycelium", "菌丝", "substrate", "培养料",
]

POLICY_KEYWORDS = [
    "policy", "regulation", "法规", "政策", "standard", "标准",
    "tariff", "关税", "quarantine", "检疫", "inspection", "检验",
    "food safety", "食品安全", "import requirement", "进口要求",
    "market access", "市场准入", "export control", "出口管制",
    "trade barrier", "贸易壁垒", "certification", "认证",
    "labeling", "标签", "pesticide residue", "农残", "heavy metal", "重金属",
    "FDA", "USDA", "EFSA", "欧盟", "美国", "日本", "韩国",
    "海关", "customs", "农业农村部", "商务部", "质检总局",
]

LOW_QUALITY_WORDS = [
    "recipe", "食谱", "做法", "怎么做好吃", "功效", "禁忌",
    "diy", "tutorial", "how to cook", "栽培技术", "种植教程",
    "价格行情", "今日价格", "批发价格", "采购价格",
]


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
    """搜索网页（政策文件补充）"""
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


def detect_category(item):
    """政策分类"""
    text = (item.get("title", "") + " " + item.get("body", "")).lower()
    title = item.get("title", "").lower()

    # 国外政策
    if any(w in text for w in ["fda", "usda", "美国", "united states", "usa"]):
        if any(w in text for w in ["policy", "regulation", "rule", "standard", "政策", "法规", "标准", "禁令", "ban", "requirement"]):
            return "美国政策"
    if any(w in text for w in ["eu ", "european union", "欧盟", "europe", "efsa"]):
        if any(w in text for w in ["policy", "regulation", "standard", "政策", "法规", "标准", "directive", "regulation"]):
            return "欧盟政策"
    if any(w in text for w in ["japan", "日本", "korea", "韩国"]):
        if any(w in text for w in ["policy", "regulation", "standard", "政策", "法规", "标准", "quarantine", "检疫", "import"]):
            return "日韩政策"

    # 国内政策
    if any(w in text for w in ["中国", "china", "农业农村部", "海关总署", "商务部", "市场监管总局", "国家标准"]):
        if any(w in text for w in ["政策", "法规", "标准", "通知", "公告", "policy", "regulation", "standard"]):
            return "国内政策"

    # 贸易政策
    if any(w in text for w in ["tariff", "关税", "trade", "贸易", "export", "出口", "import", "进口", "quarantine", "检疫", "customs", "海关", "dumping", "反倾销", "barrier", "壁垒"]):
        return "贸易政策"

    # 行业标准
    if any(w in text for w in ["standard", "标准", "gb", "iso", "食品安全", "food safety", "residue", "农残", "heavy metal", "重金属", "contaminant", "污染物"]):
        return "行业标准"

    # 市场准入
    if any(w in text for w in ["market access", "市场准入", "registration", "注册", "certification", "认证", "organic", "有机", "gap", "labeling", "标签"]):
        return "市场准入"

    return "行业动态"


def generate_policy_advice(item, category):
    """生成政策应对建议"""
    text = (item.get("title", "") + " " + item.get("body", "")).lower()

    advice_map = {
        "美国政策": "⚠️ 美国政策变化，建议：①评估对美出口影响 ②确认FDA/USDA最新要求 ③与美国客户沟通合规变化",
        "欧盟政策": "⚠️ 欧盟政策变化，建议：①关注EFSA/欧盟委员会最新法规 ②确认产品是否符合新要求 ③提前准备认证和检测",
        "日韩政策": "⚠️ 日韩政策变化，建议：①确认进口检疫要求 ②关注肯定列表制度/农药残留标准 ③与客户确认合规文件",
        "国内政策": "📋 国内政策更新，建议：①确认是否影响出口退税/补贴 ②检查企业资质是否需要更新 ③关注海关/商检流程变化",
        "贸易政策": "⚖️ 贸易政策变化，建议：①评估关税/检疫成本影响 ②考虑市场多元化 ③与客户协商费用分担",
        "行业标准": "📏 标准更新，建议：①对照新标准检查产品 ②更新检测项目 ③确认包装标签是否需要调整",
        "市场准入": "🚪 市场准入变化，建议：①确认目标市场注册/认证要求 ②准备相关文件 ③评估是否需要第三方检测",
        "行业动态": "📰 行业动态，建议：关注对出口业务的潜在影响，评估是否需要调整策略",
    }
    return advice_map.get(category, "📌 建议关注该政策动态，评估对出口业务的影响")


def is_relevant(item):
    """相关性过滤"""
    text = (item.get("title", "") + " " + item.get("body", "")).lower()
    title = item.get("title", "").lower()
    if len(title) < 10:
        return False
    # 必须含食用菌核心词
    if not any(kw.lower() in text for kw in CORE_KEYWORDS):
        return False
    # 必须含政策相关词（政策重点版）
    if not any(kw.lower() in text for kw in POLICY_KEYWORDS):
        return False
    # 过滤低质量内容
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
    """政策重要性评分"""
    score = 0
    text = (item.get("title", "") + " " + item.get("body", "")).lower()
    title = item.get("title", "").lower()
    source = item.get("source", "").lower()

    # 主要出口市场政策（最高优先级）
    if any(w in text for w in ["fda", "usda", "美国", "eu ", "欧盟", "european union", "efsa"]):
        score += 50

    # 直接影响出口的政策
    if any(w in text for w in ["tariff", "关税", "ban", "禁令", "quarantine", "检疫", "import restriction", "进口限制", "export control", "出口管制"]):
        score += 45

    # 国内出口相关政策
    if any(w in text for w in ["出口退税", "export rebate", "海关", "customs", "商检", "检验检疫", "农业农村部", "商务部"]):
        score += 40

    # 食品安全标准
    if any(w in text for w in ["food safety", "食品安全", "pesticide residue", "农残", "heavy metal", "重金属", "contaminant", "maximum residue", "mrl"]):
        score += 35

    # 法规/标准正式发布
    if any(w in text for w in ["regulation", "法规", "standard", "标准", "directive", "公告", "通知", "正式实施", "effective"]):
        score += 30

    # 认证/市场准入
    if any(w in text for w in ["certification", "认证", "registration", "注册", "market access", "市场准入", "organic", "有机"]):
        score += 25

    # 来源权威性
    auth = ["reuters", "bloomberg", "fda.gov", "usda.gov", "ec.europa.eu",
            "efsa.europa.eu", "gov.cn", "customs.gov", "moa.gov",
            "中国政府网", "农业农村部", "海关总署", "第一财经", "界面新闻"]
    if any(a in source for a in auth):
        score += 20

    # 标题直接含政策词
    if any(w in title for w in ["政策", "法规", "标准", "关税", "检疫", "policy", "regulation", "tariff", "ban"]):
        score += 10

    return score


def generate_html(news_list, today_str):
    """生成政策版HTML邮件"""
    categories = ["美国政策", "欧盟政策", "日韩政策", "国内政策", "贸易政策", "行业标准", "市场准入", "行业动态"]
    categorized = {c: [] for c in categories}

    for item in news_list:
        cat = detect_category(item)
        if cat in categorized:
            categorized[cat].append(item)
        else:
            categorized["行业动态"].append(item)

    sections_html = ""
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
            advice = generate_policy_advice(item, cat)

            if len(body) > 200:
                body = body[:200] + "..."

            items_html += f"""
<div class="news-item">
<div class="news-title"><span class="rank">{i}</span>{title}</div>
<div class="news-content">{body}</div>
<div class="advice">{advice}</div>
<div class="news-meta">时间：{date} ｜ 来源：<a href="{url}">{source}</a></div>
</div>"""

        cat_icons = {"美国政策": "🇺🇸", "欧盟政策": "🇪🇺", "日韩政策": "🌏",
                     "国内政策": "🇨🇳", "贸易政策": "⚖️", "行业标准": "📏",
                     "市场准入": "🚪", "行业动态": "📰"}
        icon = cat_icons.get(cat, "📌")
        sections_html += f"""
<div class="section">
<div class="section-title">{icon} {cat}（{len(items)}条）</div>
{items_html}
</div>"""

    total = len(news_list)
    policy_count = sum(len(categorized.get(c, [])) for c in ["美国政策", "欧盟政策", "日韩政策", "国内政策", "贸易政策"])

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; line-height: 1.7; color: #333; max-width: 760px; margin: 0 auto; padding: 20px; }}
.header {{ background: linear-gradient(135deg, #1b5e20, #2e7d32); color: #fff; padding: 30px; border-radius: 10px; margin-bottom: 20px; }}
.header h1 {{ margin: 0; font-size: 22px; }}
.header .date {{ font-size: 13px; opacity: 0.85; margin-top: 8px; }}
.stats {{ background: #e8f5e9; padding: 12px 18px; border-radius: 6px; margin-bottom: 20px; font-size: 13px; color: #1b5e20; }}
.section {{ margin-bottom: 25px; }}
.section-title {{ font-size: 16px; font-weight: bold; color: #1b5e20; border-left: 4px solid #2e7d32; padding-left: 10px; margin-bottom: 12px; }}
.news-item {{ margin-bottom: 16px; padding: 12px; background: #fafafa; border-radius: 6px; }}
.rank {{ display: inline-block; background: #2e7d32; color: #fff; width: 22px; height: 22px; line-height: 22px; text-align: center; border-radius: 50%; font-size: 12px; font-weight: bold; margin-right: 8px; }}
.news-title {{ font-size: 14px; font-weight: bold; color: #1b5e20; margin-bottom: 5px; }}
.news-content {{ font-size: 13px; color: #555; margin-bottom: 5px; }}
.advice {{ background: #fff3e0; padding: 8px 10px; border-radius: 4px; font-size: 12px; color: #e65100; margin-bottom: 5px; }}
.news-meta {{ font-size: 11px; color: #999; }}
.news-meta a {{ color: #2e7d32; text-decoration: none; }}
.footer {{ text-align: center; font-size: 11px; color: #aaa; margin-top: 25px; padding-top: 12px; border-top: 1px solid #eee; }}
</style>
</head>
<body>

<div class="header">
<h1>食用菌外贸政策每日资讯</h1>
<div class="date">{today_str} ｜ 过去7天 ｜ 共 {total} 条 ｜ 政策类 {policy_count} 条</div>
</div>

<div class="stats">
📊 <strong>适用对象：</strong>江苏省食用菌企业（菌包、鲜菇出口）<br>
💡 <strong>使用提示：</strong>每条政策附带应对建议，重点关注美国/欧盟/日韩政策和贸易壁垒变化。
</div>

{sections_html}

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
    # 政策重点搜索关键词
    # ============================================================
    news_keywords = [
        # 美国政策
        "mushroom FDA regulation import",
        "edible fungi USDA policy USA",
        "美国 食用菌 进口 政策 检疫",
        # 欧盟政策
        "mushroom EU regulation food safety",
        "edible fungi EFSA pesticide residue",
        "欧盟 食用菌 法规 农残 标准",
        # 日韩政策
        "mushroom Japan import quarantine",
        "edible fungi Korea food standard",
        "日本 韩国 食用菌 进口 肯定列表",
        # 国内政策
        "食用菌 出口 政策 海关 退税",
        "农业农村部 食用菌 标准 通知",
        "中国 食用菌 出口 检验检疫",
        # 贸易政策
        "mushroom tariff trade barrier export",
        "食用菌 关税 贸易壁垒 反倾销",
        # 行业标准
        "edible mushroom food safety standard",
        "食用菌 食品安全 国家标准 重金属",
        # 市场准入
        "mushroom organic certification market access",
        "食用菌 有机认证 出口注册 标签",
    ]

    web_keywords = [
        "FDA mushroom import requirements",
        "EU edible fungi regulation",
        "China mushroom export policy 2026",
        "食用菌出口检验检疫要求",
        "食用菌农药残留限量标准",
        "mushroom spawn export regulation",
        "fresh mushroom import requirements",
    ]

    print("=" * 50)
    print(f"食用菌外贸政策每日资讯 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    print(f"\n[1/6] 搜索新闻（{len(news_keywords)}组）...")
    news_results = search_news(news_keywords, max_per_keyword=8, timelimit="w")
    print(f"      新闻结果：{len(news_results)} 条")

    print(f"\n[2/6] 搜索网页（{len(web_keywords)}组）...")
    web_results = search_web(web_keywords, max_per_keyword=6)
    print(f"      网页结果：{len(web_results)} 条")

    all_news = news_results + web_results
    print(f"\n      原始合计：{len(all_news)} 条")

    print("\n[3/6] 相关性过滤（政策重点）...")
    relevant = [item for item in all_news if is_relevant(item)]
    print(f"      过滤后：{len(relevant)} 条")

    print("\n[4/6] 去重...")
    unique_news = deduplicate(relevant)
    print(f"      去重后：{len(unique_news)} 条")

    print("\n[5/6] 评分排序+分类...")
    for item in unique_news:
        item["score"] = score_news(item)
        item["category"] = detect_category(item)
    scored = sorted(unique_news, key=lambda x: x["score"], reverse=True)
    selected = scored[:12]

    print(f"      最终入选：{len(selected)} 条")
    for i, item in enumerate(selected, 1):
        print(f"      {i}. [{item['category']}|{item['score']}分] {item['title'][:50]}")

    print("\n[6/6] 生成邮件并发送...")
    today_str = datetime.now().strftime("%Y年%m月%d日")
    html_content = generate_html(selected, today_str)
    subject = f"食用菌外贸政策每日资讯 - {today_str}"

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
