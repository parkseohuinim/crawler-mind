from fastmcp import FastMCP
import asyncio
from playwright.async_api import async_playwright
import base64
import json
from typing import Dict, List, Any
import logging
from urllib.parse import urljoin, urlparse
import re

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP(name="CrawlerMindServer")

@mcp.tool
async def crawl_webpage(url: str) -> Dict[str, Any]:
    """
    Playwright를 사용하여 웹페이지를 크롤링합니다.
    페이지 로드, HTML 추출, 기본 메타데이터를 수집합니다.
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # 페이지 로드 (더 관대한 전략)
            try:
                await page.goto(url, wait_until='networkidle', timeout=30000)
            except Exception:
                # networkidle 실패 시 domcontentloaded로 재시도
                await page.goto(url, wait_until='domcontentloaded', timeout=15000)
            
            # 기본 정보 추출
            title = await page.title()
            html_content = await page.content()
            
            # 메타 정보 추출 (타임아웃 방지)
            try:
                meta_description = await page.get_attribute('meta[name="description"]', 'content', timeout=5000) or ""
            except Exception:
                meta_description = ""
            
            await browser.close()
            
            return {
                "success": True,
                "url": url,
                "title": title,
                "html_content": html_content,
                "meta_description": meta_description,
                "content_length": len(html_content)
            }
            
    except Exception as e:
        logger.error(f"크롤링 실패 {url}: {str(e)}")
        return {
            "success": False,
            "url": url,
            "error": str(e)
        }

@mcp.tool
def extract_text_content(html_content: str) -> Dict[str, Any]:
    """
    HTML 콘텐츠에서 텍스트만 추출합니다.
    태그를 제거하고 읽기 가능한 텍스트만 반환합니다.
    """
    try:
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 스크립트와 스타일 태그 제거
        for script in soup(["script", "style"]):
            script.decompose()
        
        # 텍스트 추출
        text = soup.get_text()
        
        # 공백 정리
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return {
            "success": True,
            "text_content": text,
            "text_length": len(text),
            "word_count": len(text.split())
        }
        
    except Exception as e:
        logger.error(f"텍스트 추출 실패: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool
def extract_links(html_content: str, base_url: str) -> Dict[str, Any]:
    """
    HTML 콘텐츠에서 모든 링크를 추출합니다.
    상대 링크는 절대 링크로 변환합니다.
    """
    try:
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html_content, 'html.parser')
        links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href'].strip()
            if href:
                # 절대 URL로 변환
                absolute_url = urljoin(base_url, href)
                link_text = link.get_text(strip=True)
                
                links.append({
                    "url": absolute_url,
                    "text": link_text,
                    "is_external": urlparse(absolute_url).netloc != urlparse(base_url).netloc
                })
        
        # 중복 제거 (URL 기준)
        unique_links = []
        seen_urls = set()
        for link in links:
            if link["url"] not in seen_urls:
                unique_links.append(link)
                seen_urls.add(link["url"])
        
        return {
            "success": True,
            "links": unique_links,
            "total_links": len(unique_links),
            "internal_links": len([l for l in unique_links if not l["is_external"]]),
            "external_links": len([l for l in unique_links if l["is_external"]])
        }
        
    except Exception as e:
        logger.error(f"링크 추출 실패: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool
async def take_screenshot(url: str) -> Dict[str, Any]:
    """
    웹페이지의 스크린샷을 촬영합니다.
    Base64 인코딩된 이미지를 반환합니다.
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # 페이지 로드 (더 관대한 전략)
            try:
                await page.goto(url, wait_until='networkidle', timeout=30000)
            except Exception:
                # networkidle 실패 시 domcontentloaded로 재시도
                await page.goto(url, wait_until='domcontentloaded', timeout=15000)
            
            # 스크린샷 촬영
            screenshot_bytes = await page.screenshot(full_page=True, type='png')
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            
            await browser.close()
            
            return {
                "success": True,
                "url": url,
                "screenshot": screenshot_base64,
                "format": "png",
                "size_bytes": len(screenshot_bytes)
            }
            
    except Exception as e:
        logger.error(f"스크린샷 촬영 실패 {url}: {str(e)}")
        return {
            "success": False,
            "url": url,
            "error": str(e)
        }

@mcp.tool
def summarize_content(text_content: str, max_length: int = 500) -> Dict[str, Any]:
    """
    텍스트 콘텐츠를 요약합니다.
    간단한 추출 요약을 수행합니다.
    """
    try:
        if not text_content.strip():
            return {
                "success": False,
                "error": "텍스트 콘텐츠가 비어있습니다"
            }
        
        # 문장 단위로 분할
        sentences = re.split(r'[.!?]+', text_content)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return {
                "success": False,
                "error": "유효한 문장을 찾을 수 없습니다"
            }
        
        # 간단한 추출 요약 (처음 몇 문장)
        summary_sentences = []
        current_length = 0
        
        for sentence in sentences:
            if current_length + len(sentence) > max_length:
                break
            summary_sentences.append(sentence)
            current_length += len(sentence)
        
        summary = '. '.join(summary_sentences)
        if not summary.endswith('.'):
            summary += '.'
        
        return {
            "success": True,
            "summary": summary,
            "original_length": len(text_content),
            "summary_length": len(summary),
            "compression_ratio": len(summary) / len(text_content) if text_content else 0
        }
        
    except Exception as e:
        logger.error(f"요약 생성 실패: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

async def main():
    await mcp.run_async(
        transport="http",
        host="127.0.0.1",
        port=4200,
        path="/my-custom-path",
        log_level="debug",
    )

if __name__ == "__main__":
    asyncio.run(main())