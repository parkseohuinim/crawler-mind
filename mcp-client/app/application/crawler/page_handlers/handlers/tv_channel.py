"""
지니 TV 채널 편성표 핸들러

tv.kt.com 채널 편성표 추출
"""

import asyncio
import html
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup, NavigableString

from ..handler_registry import register_page_handler

logger = logging.getLogger(__name__)


async def handle_whygenietv_channel_schedule(
    url: str, 
    fclient: Any, 
    menu: Optional[str] = None
) -> Dict[str, Any]:
    """
    지니 TV(WhyGenieTV) 채널 편성표 추출 핸들러
    """
    logger.info(f"🎬 Genie TV Channel Schedule processing started: {url}")

    base_menu = (menu or "상품^WhyGenieTV^채널 편성표").strip()
    menus: List[Dict[str, Any]] = []
    datas: List[Dict[str, Any]] = []

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": url
    })

    try:
        response = await asyncio.to_thread(session.get, url, timeout=30)
    except Exception as e:
        session.close()
        logger.error(f"❌ Genie TV Channel Schedule request failed: {e}")
        return {
            "menus": [],
            "datas": [],
            "total_processed": 0,
            "status": "failed",
            "message": f"요청 실패: {e}"
        }

    status_code = getattr(response, "status_code", None)
    if not response or not getattr(response, "content", b""):
        session.close()
        logger.error("❌ Genie TV Channel Schedule response is empty")
        return {
            "menus": [],
            "datas": [],
            "total_processed": 0,
            "status": "failed",
            "status_code": status_code,
            "message": "응답이 비어 있습니다."
        }

    # 인코딩 자동 감지 - apparent_encoding 사용
    detected_encoding = response.apparent_encoding
    logger.info(f"📡 Detected encoding: {detected_encoding}")
    
    # Content-Type 헤더에서 charset 확인
    content_type = response.headers.get("Content-Type", "")
    if "charset=" in content_type.lower():
        header_charset = content_type.lower().split("charset=")[-1].split(";")[0].strip()
        logger.info(f"📡 Content-Type charset: {header_charset}")
        response.encoding = header_charset
    elif detected_encoding:
        response.encoding = detected_encoding
    else:
        response.encoding = "euc-kr"
    
    logger.info(f"📡 Final encoding used: {response.encoding}")
    soup = BeautifulSoup(response.text, "html.parser")

    channel_guide_el = soup.select_one("div.channel_guide")
    noti_desc_el = soup.select_one("div.noti_desc")

    def normalize_multiline(text: str) -> str:
        if not text:
            return ""
        lines = [line.strip() for line in text.splitlines()]
        cleaned = "\n".join(line for line in lines if line)
        return cleaned.strip()

    channel_guide_text = normalize_multiline(channel_guide_el.get_text("\n", strip=True)) if channel_guide_el else ""
    noti_desc_text = normalize_multiline(noti_desc_el.get_text("\n", strip=True)) if noti_desc_el else ""
    channel_guide_html = str(channel_guide_el) if channel_guide_el else ""
    noti_desc_html = str(noti_desc_el) if noti_desc_el else ""

    super_tab_pattern = re.compile(r"fnSearchChannel\((?P<ch_type>[^,]+),'(?P<prod>[^']*)',\s*(?P<mid>[^)]+)\)")
    plan_pattern = re.compile(r"fnSearchChannelNoSubmit\('(?P<ch_type>[^']*)','(?P<product_cd>[^']*)',\s*(?P<mid>[^)]+)\)")

    super_tabs: List[Dict[str, Any]] = []
    for anchor in soup.select(".channel_content .sub-tabs-1st .sub-trigger"):
        tab_name = (anchor.get_text(" ", strip=True) or "").replace("\xa0", " ").strip()
        href = (anchor.get("href") or "").strip()
        if not tab_name or not href:
            continue
        match = super_tab_pattern.search(anchor.get("onclick") or "")
        if not match:
            continue
        ch_type = match.group("ch_type").strip() or "3"
        target = soup.select_one(href)
        if not target:
            continue
        plan_ul = target.select_one("ul.channel_select")
        if not plan_ul:
            continue
        super_tabs.append({
            "name": tab_name,
            "ch_type": ch_type,
            "plan_ul": plan_ul
        })

    if not super_tabs:
        plan_container = soup.select_one("div#trigger2-1-1 ul.channel_select.tv_live") or soup.select_one("ul.channel_select.tv_live")
        if plan_container:
            super_tabs.append({
                "name": "지니 TV",
                "ch_type": "3",
                "plan_ul": plan_container
            })

    if not super_tabs:
        session.close()
        logger.error("❌ Genie TV tab information not found")
        return {
            "menus": [],
            "datas": [],
            "total_processed": 0,
            "status": "failed",
            "status_code": status_code,
            "message": "탭 정보를 찾을 수 없습니다."
        }

    channel_cache: Dict[Tuple[str, str, str], Tuple[int, str]] = {}

    def parse_channel_html(html_text: str) -> List[Dict[str, str]]:
        if not html_text:
            return []
        inner_soup = BeautifulSoup(html_text, "html.parser")
        channels: List[Dict[str, str]] = []
        for anchor in inner_soup.select("ul.channel li a"):
            span = anchor.select_one("span.ch")
            if not span:
                continue

            text_parts: List[str] = []
            for node in span.contents:
                if isinstance(node, NavigableString):
                    value = str(node).strip()
                    if value:
                        text_parts.append(value)

            channel_text = " ".join(text_parts).replace("\xa0", " ")
            channel_text = re.sub(r"\s+", " ", channel_text).strip()
            if not channel_text:
                continue

            channel_text = html.unescape(unquote(channel_text))

            number = channel_text
            name = ""
            number_match = re.match(r"^(\S+)\s+(.*)$", channel_text)
            if number_match:
                number = number_match.group(1).strip()
                name = number_match.group(2).strip()

            alt_text = html.unescape(unquote((anchor.get("alt") or "").strip()))

            channels.append({
                "channel_number": number,
                "channel_name": name,
                "note": alt_text
            })
        return channels

    async def fetch_channels(ch_type: str, product_cd: str, parent_menu_id: str) -> Tuple[int, List[Dict[str, str]]]:
        cache_key = (ch_type, product_cd or "", parent_menu_id or "0")
        if cache_key in channel_cache:
            cached_status, cached_html = channel_cache[cache_key]
            return cached_status, parse_channel_html(cached_html)

        data = {
            "ch_type": ch_type,
            "parent_menu_id": parent_menu_id or "0",
            "product_cd": product_cd or "",
            "option_cd_list": ""
        }

        try:
            resp = await asyncio.to_thread(session.post, "https://tv.kt.com/tv/channel/pChList.asp", data=data, timeout=30)
        except Exception as e:
            logger.error(f"❌ Channel list request failed (product_cd={product_cd}): {e}")
            return None, []

        # 인코딩 자동 감지
        detected_encoding = resp.apparent_encoding
        content_type = resp.headers.get("Content-Type", "")
        if "charset=" in content_type.lower():
            resp.encoding = content_type.lower().split("charset=")[-1].split(";")[0].strip()
        elif detected_encoding:
            resp.encoding = detected_encoding
        else:
            resp.encoding = "euc-kr"
        
        channel_cache[cache_key] = (resp.status_code, resp.text)
        return resp.status_code, parse_channel_html(resp.text)

    def escape_md(value: str) -> str:
        if not value:
            return ""
        return value.replace("|", "\\|")

    total_plans_processed = 0

    for super_tab in super_tabs:
        super_name = super_tab["name"]
        super_ch_type = super_tab["ch_type"]
        plan_ul = super_tab["plan_ul"]

        seen_codes: Set[str] = set()
        plan_entries: List[Dict[str, str]] = []

        for anchor in plan_ul.select("li a"):
            onclick = anchor.get("onclick") or ""
            match = plan_pattern.search(onclick)
            if not match:
                continue

            product_cd = match.group("product_cd").strip()
            parent_menu_id = match.group("mid").strip().strip(";") or "0"

            span = anchor.select_one("span")
            raw_title = (span.get_text(" ", strip=True) if span else "").replace("\xa0", " ").strip()
            clean_title = re.sub(r"\([^)]*\)", "", raw_title).strip()

            if not raw_title or not product_cd:
                continue
            if not clean_title or clean_title in ("전체",):
                continue
            if "선택형" in clean_title:
                continue
            if product_cd in seen_codes:
                continue

            seen_codes.add(product_cd)
            plan_entries.append({
                "title": clean_title,
                "raw_title": raw_title,
                "ch_type": super_ch_type,
                "product_cd": product_cd,
                "parent_menu_id": parent_menu_id
            })

        if not plan_entries:
            logger.warning(f"⚠️ No plan information found for '{super_name}'")
            continue

        for plan in plan_entries:
            plan_title = plan["title"]
            plan_code = plan["product_cd"]
            plan_ch_type = plan["ch_type"]
            parent_menu_id = plan["parent_menu_id"]

            channel_status, channels = await fetch_channels(plan_ch_type, plan_code, parent_menu_id)
            channel_count = len(channels)

            markdown_lines = [
                "| 채널 번호 | 채널명 | 비고 |",
                "| --- | --- | --- |"
            ]
            for channel in channels:
                markdown_lines.append(
                    f"| {escape_md(channel['channel_number'])} | {escape_md(channel['channel_name'])} | {escape_md(channel['note'])} |"
                )
            markdown_table = "\n".join(markdown_lines)

            markdown_sections: List[str] = []
            markdown_sections.append(f"# {super_name} - {plan_title}")
            markdown_sections.append(markdown_table)
            if channel_guide_text:
                markdown_sections.append(channel_guide_text)
            if noti_desc_text:
                markdown_sections.append(noti_desc_text)
            full_markdown = "\n\n".join(markdown_sections)

            menu_path = f"{base_menu}^{super_name}^{plan_title}" if base_menu else f"{super_name}^{plan_title}"
            menus.append({
                "menu": menu_path,
                "url": url
            })
            datas.append({
                "menu": menu_path,
                "title": plan_title,
                "parent_tab": super_name,
                "url": url,
                "plan_code": plan_code,
                "ch_type": plan_ch_type,
                "parent_menu_id": parent_menu_id,
                "channel_count": channel_count,
                "channels": channels,
                "channel_guide_text": channel_guide_text,
                "channel_guide_html": channel_guide_html,
                "noti_desc_text": noti_desc_text,
                "noti_desc_html": noti_desc_html,
                "markdown": full_markdown,
                "status_code": channel_status
            })

            total_plans_processed += 1
            logger.info(f"✅ Channel plan processed: '{super_name}' > '{plan_title}' ({channel_count} channels)")

    session.close()

    logger.info(f"✅ Genie TV Channel Schedule completed: {total_plans_processed} plans")

    return {
        "menus": menus,
        "datas": datas,
        "total_processed": total_plans_processed,
        "status": "completed",
        "status_code": status_code,
        "message": f"지니 TV 채널 편성표 플랜 {total_plans_processed}건 처리 완료"
    }


# 핸들러 등록
register_page_handler(
    r'https?://tv\.kt\.com/tv/channel/pChInfo\.asp.*',
    handle_whygenietv_channel_schedule
)


