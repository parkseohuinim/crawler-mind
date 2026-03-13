#!/usr/bin/env python3
"""
GNB 메뉴 CSV와 크롤링 결과 JSON의 URL/Hierarchy 검증 레포트 생성 스크립트

Usage:
    python verify_report.py <menu_csv_path> <json_data_path> [--output <output_path>]

Example:
    python verify_report.py result/gnb_menus_20260226.csv result/data_2026-02-26_114503.json
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

try:
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


FILL_HEADER = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid") if HAS_OPENPYXL else None
FILL_ONLY_MENU = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid") if HAS_OPENPYXL else None
FILL_ONLY_JSON = PatternFill(start_color="D6E4F0", end_color="D6E4F0", fill_type="solid") if HAS_OPENPYXL else None
FILL_HIER_MATCH = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid") if HAS_OPENPYXL else None


def normalize_url(url: str) -> str:
    """URL 정규화: 프로토콜 통일, .asp 제거, 상품 URL 통일, 쿼리 파라미터 정렬, trailing slash 제거"""
    if not url:
        return ""
    url = url.strip()
    parsed = urlparse(url)

    scheme = "https"
    netloc = parsed.netloc
    path = parsed.path.rstrip("/") if parsed.path != "/" else parsed.path

    if path.endswith(".asp"):
        path = path[:-4]

    query_params = parse_qs(parsed.query, keep_blank_values=True)

    # shop.kt.com 상품 URL 통일: olhsGoodsDtl.do?goodsCode=X → mobile/view.do?prodNo=X
    if "shop.kt.com" in netloc and "/display/olhsGoodsDtl.do" in path:
        goods_code = query_params.pop("goodsCode", [None])[0]
        if goods_code:
            path = "/mobile/view.do"
            query_params["prodNo"] = [goods_code]

    sorted_query = urlencode(
        {k: v[0] if len(v) == 1 else v for k, v in sorted(query_params.items())},
        doseq=True,
    )
    normalized = urlunparse((
        scheme,
        netloc,
        path,
        parsed.params,
        sorted_query,
        "",
    ))
    return normalized


def load_menu_csv(csv_path: str) -> list[dict]:
    """CSV에서 (pc_url, menu_path) 추출"""
    entries = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pc_url = row.get("pc_url", "").strip()
            menu_path = row.get("menu_path", "").strip()
            entries.append({
                "url": pc_url,
                "url_normalized": normalize_url(pc_url),
                "hierarchy": menu_path,
            })
    return entries


def load_json_data(json_path: str) -> list[dict]:
    """JSON에서 (url, hierarchy) 추출, hierarchy 배열을 ^로 조인"""
    entries = []
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for item in data:
        url = item.get("url", "").strip()
        hierarchy_arr = item.get("hierarchy", [])
        hierarchy = "^".join(hierarchy_arr)
        entries.append({
            "url": url,
            "url_normalized": normalize_url(url),
            "hierarchy": hierarchy,
        })
    return entries


def _strip_symbols(text: str) -> str:
    """기호, 공백 등 비문자 요소를 모두 제거하여 비교용 문자열 생성"""
    return re.sub(r"[^a-zA-Z0-9가-힣]", "", text)


def _hierarchy_fuzzy_equal(menu_h: str, json_h: str) -> bool:
    """
    Fuzzy hierarchy 비교:
    1) depth(레벨 수)가 동일해야 함
    2) 각 레벨을 기호/공백 제거 후 비교하여 모두 동일해야 함
    """
    m_levels = menu_h.split("^")
    j_levels = json_h.split("^")

    if len(m_levels) != len(j_levels):
        return False

    return all(
        _strip_symbols(ml) == _strip_symbols(jl)
        for ml, jl in zip(m_levels, j_levels)
    )


def build_report(menu_entries: list[dict], json_entries: list[dict]) -> list[dict]:
    """
    URL 기준 Full Outer Join 후 hierarchy 매칭 수행.
    매칭 우선순위: 1) exact match  2) fuzzy match (기호/공백 차이 무시)
    """
    menu_by_url: dict[str, list[dict]] = {}
    for e in menu_entries:
        menu_by_url.setdefault(e["url_normalized"], []).append(e)

    json_by_url: dict[str, list[dict]] = {}
    for e in json_entries:
        json_by_url.setdefault(e["url_normalized"], []).append(e)

    all_urls = set(menu_by_url.keys()) | set(json_by_url.keys())
    rows = []

    for norm_url in sorted(all_urls):
        m_entries = menu_by_url.get(norm_url, [])
        j_entries = json_by_url.get(norm_url, [])

        if not m_entries:
            for je in j_entries:
                rows.append(_row(
                    json_url=je["url"], json_hierarchy=je["hierarchy"],
                    only_json=True,
                ))
            continue

        if not j_entries:
            for me in m_entries:
                rows.append(_row(
                    menu_url=me["url"], menu_hierarchy=me["hierarchy"],
                    only_menu=True,
                ))
            continue

        m_hierarchies = list({me["hierarchy"] for me in m_entries})
        j_hierarchies = list({je["hierarchy"] for je in j_entries})
        m_url_orig = m_entries[0]["url"]
        j_url_orig = j_entries[0]["url"]

        j_used = set()
        m_used = set()

        # Pass 1: exact match
        for mi, mh in enumerate(m_hierarchies):
            for ji, jh in enumerate(j_hierarchies):
                if ji in j_used:
                    continue
                if mh == jh:
                    rows.append(_row(
                        menu_url=m_url_orig, menu_hierarchy=mh,
                        is_matched=True,
                        json_url=j_url_orig, json_hierarchy=jh,
                    ))
                    m_used.add(mi)
                    j_used.add(ji)
                    break

        # Pass 2: fuzzy match (기호/공백 차이만 허용, depth 동일 필수)
        for mi, mh in enumerate(m_hierarchies):
            if mi in m_used:
                continue
            for ji, jh in enumerate(j_hierarchies):
                if ji in j_used:
                    continue
                if _hierarchy_fuzzy_equal(mh, jh):
                    rows.append(_row(
                        menu_url=m_url_orig, menu_hierarchy=mh,
                        is_matched=True, is_fuzzy=True,
                        json_url=j_url_orig, json_hierarchy=jh,
                    ))
                    m_used.add(mi)
                    j_used.add(ji)
                    break

        # Pass 3: URL은 동일하지만 hierarchy가 다른 것들 → only_menu / only_json 으로 분류
        for mi, mh in enumerate(m_hierarchies):
            if mi in m_used:
                continue
            rows.append(_row(
                menu_url=m_url_orig, menu_hierarchy=mh,
                only_menu=True,
            ))

        for ji, jh in enumerate(j_hierarchies):
            if ji in j_used:
                continue
            rows.append(_row(
                json_url=j_url_orig, json_hierarchy=jh,
                only_json=True,
            ))

    # Pass 4: only_menu / only_json 간 hierarchy 매칭 (URL은 다르지만 hierarchy 동일)
    only_menu_rows = [r for r in rows if r["only_menu"]]
    only_json_rows = [r for r in rows if r["only_json"]]

    # hierarchy → row index 맵핑 (json 쪽)
    j_hier_exact: dict[str, list[int]] = {}
    j_hier_fuzzy: dict[str, list[int]] = {}
    for idx, r in enumerate(only_json_rows):
        jh = r["json_hierarchy"]
        j_hier_exact.setdefault(jh, []).append(idx)
        j_hier_fuzzy.setdefault(_strip_symbols(jh), []).append(idx)

    j_matched_indices = set()
    m_matched_indices = set()

    for m_idx, mr in enumerate(only_menu_rows):
        mh = mr["menu_hierarchy"]

        # exact hierarchy match
        candidates = j_hier_exact.get(mh, [])
        matched_j_idx = next((i for i in candidates if i not in j_matched_indices), None)

        # fuzzy hierarchy match
        if matched_j_idx is None:
            stripped = _strip_symbols(mh)
            candidates = j_hier_fuzzy.get(stripped, [])
            matched_j_idx = next((i for i in candidates if i not in j_matched_indices), None)

        if matched_j_idx is not None:
            jr = only_json_rows[matched_j_idx]
            m_matched_indices.add(m_idx)
            j_matched_indices.add(matched_j_idx)
            mr["json_url"] = jr["json_url"]
            mr["json_hierarchy"] = jr["json_hierarchy"]
            mr["only_menu"] = False
            mr["hierarchy_matched_only"] = True
            jr["_consumed"] = True

    # json 쪽에서 매칭된 row는 제거
    rows = [r for r in rows if not r.get("_consumed")]
    for r in rows:
        r.pop("_consumed", None)

    # Pass 5: 제목(leaf) 기반 매칭 — 상위 2레벨 이상 겹치고 마지막 요소(제목)가 동일하면 매칭
    remaining_menu = [r for r in rows if r["only_menu"]]
    remaining_json = [r for r in rows if r["only_json"]]

    def _hierarchy_levels(h: str) -> list[str]:
        return [_strip_symbols(lv) for lv in h.split("^")]

    # (상위2레벨 키, leaf) → index 맵핑
    j_title_map: dict[tuple[str, str], list[int]] = {}
    for idx, r in enumerate(remaining_json):
        jh = r["json_hierarchy"]
        levels = _hierarchy_levels(jh)
        if len(levels) < 3:
            continue
        prefix_key = "^".join(levels[:2])
        leaf = levels[-1]
        j_title_map.setdefault((prefix_key, leaf), []).append(idx)

    j_title_used = set()
    for mr in remaining_menu:
        mh = mr["menu_hierarchy"]
        levels = _hierarchy_levels(mh)
        if len(levels) < 3:
            continue
        prefix_key = "^".join(levels[:2])
        leaf = levels[-1]
        if not leaf:
            continue
        candidates = j_title_map.get((prefix_key, leaf), [])
        matched_j_idx = next((i for i in candidates if i not in j_title_used), None)
        if matched_j_idx is not None:
            jr = remaining_json[matched_j_idx]
            j_title_used.add(matched_j_idx)
            mr["json_url"] = jr["json_url"]
            mr["json_hierarchy"] = jr["json_hierarchy"]
            mr["only_menu"] = False
            mr["is_matched"] = True
            mr["is_fuzzy"] = True
            jr["_consumed"] = True

    rows = [r for r in rows if not r.get("_consumed")]
    for r in rows:
        r.pop("_consumed", None)

    # 참조 컬럼: JSON URL에 대응하는 메뉴 hierarchy 표시
    for r in rows:
        r["menu_ref_hierarchy"] = ""
        json_url = r.get("json_url", "")
        if not json_url:
            continue
        norm = normalize_url(json_url)
        m_entries = menu_by_url.get(norm, [])
        if m_entries:
            ref_hierarchies = sorted({me["hierarchy"] for me in m_entries})
            r["menu_ref_hierarchy"] = " | ".join(ref_hierarchies)

    rows.sort(key=lambda r: (
        not r["is_matched"],
        not r["hierarchy_matched_only"],
        r["only_menu"],
        r["only_json"],
        r["menu_url"] or r["json_url"],
    ))

    return rows


def _row(
    menu_url="", menu_hierarchy="",
    is_matched=False, is_fuzzy=False,
    json_url="", json_hierarchy="",
    only_menu=False, only_json=False,
    hierarchy_matched_only=False,
) -> dict:
    return {
        "menu_url": menu_url,
        "menu_hierarchy": menu_hierarchy,
        "is_matched": is_matched,
        "is_fuzzy": is_fuzzy,
        "json_url": json_url,
        "json_hierarchy": json_hierarchy,
        "menu_ref_hierarchy": "",
        "only_menu": only_menu,
        "only_json": only_json,
        "hierarchy_matched_only": hierarchy_matched_only,
    }


def generate_summary(rows: list[dict], menu_count: int, json_count: int) -> dict:
    """통계 요약 생성"""
    total = len(rows)
    exact_matched = sum(1 for r in rows if r["is_matched"] and not r["is_fuzzy"])
    fuzzy_matched = sum(1 for r in rows if r["is_matched"] and r["is_fuzzy"])
    matched = exact_matched + fuzzy_matched
    only_menu = sum(1 for r in rows if r["only_menu"])
    only_json = sum(1 for r in rows if r["only_json"])
    hierarchy_matched_only = sum(1 for r in rows if r["hierarchy_matched_only"])

    return {
        "menu_total": menu_count,
        "json_total": json_count,
        "report_rows": total,
        "matched": matched,
        "exact_matched": exact_matched,
        "fuzzy_matched": fuzzy_matched,
        "only_menu": only_menu,
        "only_json": only_json,
        "hierarchy_matched_only": hierarchy_matched_only,
        "match_rate_menu": f"{matched / menu_count * 100:.1f}%" if menu_count else "N/A",
        "match_rate_json": f"{matched / json_count * 100:.1f}%" if json_count else "N/A",
    }


def write_xlsx(rows: list[dict], summary: dict, output_path: str):
    """XLSX 파일로 출력 (셀 배경색 적용)"""
    if not HAS_OPENPYXL:
        print("openpyxl 미설치 — XLSX 출력 건너뜀")
        return

    wb = Workbook()

    # --- Summary 시트 ---
    ws_summary = wb.active
    ws_summary.title = "Summary"
    ws_summary.column_dimensions["A"].width = 35
    ws_summary.column_dimensions["B"].width = 20

    summary_items = [
        ("검증 레포트 생성 일시", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("", ""),
        ("Menu CSV 고유 항목 수", summary["menu_total"]),
        ("JSON 고유 항목 수", summary["json_total"]),
        ("", ""),
        ("레포트 총 행 수", summary["report_rows"]),
        ("일치 합계 (exact + fuzzy)", summary["matched"]),
        ("  ├ 완전 일치 (URL + Hierarchy 동일)", summary["exact_matched"]),
        ("  └ Fuzzy 일치 (기호/공백 차이만 허용)", summary["fuzzy_matched"]),
        ("Hierarchy만 일치 (URL 불일치)", summary["hierarchy_matched_only"]),
        ("Menu에만 존재", summary["only_menu"]),
        ("JSON에만 존재", summary["only_json"]),
        ("", ""),
        ("Menu 기준 매칭률", summary["match_rate_menu"]),
        ("JSON 기준 매칭률", summary["match_rate_json"]),
    ]
    for i, (label, value) in enumerate(summary_items, 1):
        ws_summary.cell(row=i, column=1, value=label).font = Font(bold=True)
        ws_summary.cell(row=i, column=2, value=value)

    legend_row = len(summary_items) + 2
    ws_summary.cell(row=legend_row, column=1, value="범례").font = Font(bold=True, size=12)
    legend_items = [
        (FILL_ONLY_MENU, "Menu에만 존재 (옅은 회색)"),
        (FILL_ONLY_JSON, "JSON에만 존재 (옅은 파랑)"),
        (FILL_HIER_MATCH, "Hierarchy 일치, URL 불일치 (옅은 초록)"),
    ]
    for j, (fill, desc) in enumerate(legend_items, 1):
        cell = ws_summary.cell(row=legend_row + j, column=1, value=desc)
        cell.fill = fill

    # --- Detail 시트 ---
    ws_detail = wb.create_sheet("Detail")
    columns = [
        "menu_url", "menu_hierarchy", "is_matched", "is_fuzzy",
        "json_url", "json_hierarchy", "menu_ref_hierarchy",
        "only_menu", "only_json", "hierarchy_matched_only",
    ]
    col_widths = [60, 40, 12, 12, 60, 40, 50, 12, 12, 20]

    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    for col_idx, (col_name, width) in enumerate(zip(columns, col_widths), 1):
        cell = ws_detail.cell(row=1, column=col_idx, value=col_name)
        cell.fill = FILL_HEADER
        cell.font = Font(bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border
        ws_detail.column_dimensions[cell.column_letter].width = width

    for row_idx, row_data in enumerate(rows, 2):
        fill = None
        if row_data["only_menu"]:
            fill = FILL_ONLY_MENU
        elif row_data["only_json"]:
            fill = FILL_ONLY_JSON
        elif row_data["hierarchy_matched_only"]:
            fill = FILL_HIER_MATCH

        for col_idx, col_name in enumerate(columns, 1):
            value = row_data[col_name]
            if isinstance(value, bool):
                value = "O" if value else ""
            cell = ws_detail.cell(row=row_idx, column=col_idx, value=value)
            cell.border = thin_border
            if fill:
                cell.fill = fill

    ws_detail.auto_filter.ref = f"A1:J{len(rows) + 1}"
    ws_detail.freeze_panes = "A2"

    wb.save(output_path)
    print(f"XLSX 저장 완료: {output_path}")


def write_csv(rows: list[dict], output_path: str):
    """CSV 파일로 출력 (only_menu, only_json 컬럼 포함)"""
    columns = [
        "menu_url", "menu_hierarchy", "is_matched", "is_fuzzy",
        "json_url", "json_hierarchy", "menu_ref_hierarchy",
        "only_menu", "only_json", "hierarchy_matched_only",
    ]
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            out = {}
            for c in columns:
                val = row[c]
                if isinstance(val, bool):
                    out[c] = "O" if val else ""
                else:
                    out[c] = val
            writer.writerow(out)

    print(f"CSV 저장 완료: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="GNB 메뉴 vs JSON 크롤링 데이터 검증 레포트 생성")
    parser.add_argument("menu_csv", help="GNB 메뉴 CSV 파일 경로")
    parser.add_argument("json_data", help="크롤링 결과 JSON 파일 경로")
    parser.add_argument(
        "--output", "-o",
        help="출력 파일 경로 (확장자 없이 입력 시 .xlsx, .csv 모두 생성)",
        default=None,
    )
    args = parser.parse_args()

    if not os.path.exists(args.menu_csv):
        print(f"파일을 찾을 수 없습니다: {args.menu_csv}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(args.json_data):
        print(f"파일을 찾을 수 없습니다: {args.json_data}", file=sys.stderr)
        sys.exit(1)

    print("=" * 60)
    print("GNB 메뉴 vs JSON 크롤링 데이터 검증 레포트")
    print("=" * 60)

    print(f"\n[1/4] Menu CSV 로딩: {args.menu_csv}")
    menu_entries = load_menu_csv(args.menu_csv)
    print(f"  → {len(menu_entries)}건 로드")

    print(f"\n[2/4] JSON 데이터 로딩: {args.json_data}")
    json_entries = load_json_data(args.json_data)
    print(f"  → {len(json_entries)}건 로드")

    print("\n[3/4] 매칭 분석 중...")
    rows = build_report(menu_entries, json_entries)
    summary = generate_summary(
        rows,
        menu_count=len(set((e["url_normalized"], e["hierarchy"]) for e in menu_entries)),
        json_count=len(set((e["url_normalized"], e["hierarchy"]) for e in json_entries)),
    )

    print(f"\n  ✓ 일치 합계: {summary['matched']}건")
    print(f"    ├ 완전 일치 (exact): {summary['exact_matched']}건")
    print(f"    └ Fuzzy 일치 (기호/공백 차이): {summary['fuzzy_matched']}건")
    print(f"  ▽ Hierarchy만 일치 (URL 불일치): {summary['hierarchy_matched_only']}건")
    print(f"  ◇ Menu에만 존재: {summary['only_menu']}건")
    print(f"  ◆ JSON에만 존재: {summary['only_json']}건")
    print(f"  ─ Menu 기준 매칭률: {summary['match_rate_menu']}")
    print(f"  ─ JSON 기준 매칭률: {summary['match_rate_json']}")

    if args.output:
        base = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_dir = os.path.dirname(args.menu_csv) or "."
        base = os.path.join(result_dir, f"verify_report_{timestamp}")

    base_no_ext = os.path.splitext(base)[0]
    if os.path.splitext(base)[1]:
        base_no_ext = os.path.splitext(base)[0]

    print("\n[4/4] 레포트 파일 생성 중...")

    csv_path = base_no_ext + ".csv"
    write_csv(rows, csv_path)

    if HAS_OPENPYXL:
        xlsx_path = base_no_ext + ".xlsx"
        write_xlsx(rows, summary, xlsx_path)

    print("\n" + "=" * 60)
    print("검증 레포트 생성 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
