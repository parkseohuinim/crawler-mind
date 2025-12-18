## 1. membership.py (2개 핸들러)

### `handle_membership_partner_list_playwright` ⭕️
| 패턴 | `membership.kt.com/discount/partner/PartnerList.do` |
|------|-----------------------------------------------------|

| 메뉴 | URL |
|------|-----|
| 혜택^멤버십 할인^제휴브랜드 | https://membership.kt.com/discount/partner/PartnerList.do |

### `handle_membership_faq_all_playwright` ⭕️
| 패턴 | `membership.kt.com/guide/faq/FAQList.do` |
|------|------------------------------------------|

| 메뉴 | URL |
|------|-----|
| 혜택^멤버십 안내^FAQ | https://membership.kt.com/guide/faq/FAQList.do |

---

## 2. interpark.py (2개 핸들러)

### `handle_interpark_notice_main` ⭕️
| 패턴 | `kt.interpark.com/Partner/KT/Event/NoticeList.asp` |
|------|---------------------------------------------------|

| 메뉴 | URL |
|------|-----|
| 혜택^영화/공연^공연예매^공연예매 메인^공지사항 | https://kt.interpark.com/Partner/KT/Event/NoticeList.asp |

### `handle_show_notice`
> 상세 페이지는 목록에서 동적 추출됨

---

## 3. globalroaming.py (2개 핸들러)

### `handle_globalroaming_notice_main` ⭕️
| 패턴 | `globalroaming.kt.com/news/list.asp` |
|------|--------------------------------------|

| 메뉴 | URL |
|------|-----|
| 상품^로밍^한눈에보기^공지사항 | https://globalroaming.kt.com/news/list.asp |

### `handle_roaming_notice`
> 상세 페이지는 목록에서 동적 추출됨

---

## 4. kt_notice.py (2개 핸들러)

### `handle_kt_notice_main` ⭕️
| 패턴 | `inside.kt.com/html/notice/notice_list.html` |
|------|---------------------------------------------|

| 메뉴 | URL |
|------|-----|
| 고객지원^공지/이용안내^공지사항 | https://inside.kt.com/html/notice/notice_list.html |

### `handle_kt_notice_detail`
> 상세 페이지는 목록에서 동적 추출됨

---

## 5. network_notice.py (2개 핸들러)

### `handle_network_notice_main` ⭕️
| 패턴 | `inside.kt.com/html/notice/net_notice_list.html` |
|------|-------------------------------------------------|

| 메뉴 | URL |
|------|-----|
| 고객지원^공지/이용안내^통신서비스중단작업공지 | https://inside.kt.com/html/notice/net_notice_list.html |

### `handle_network_notice_detail`
> 상세 페이지는 목록에서 동적 추출됨

---

## 6. safety_notice.py (2개 핸들러)

### `handle_safety_notice_main` ⭕️
| 패턴 | `inside.kt.com/html/safety/notice_list.html` |
|------|---------------------------------------------|

| 메뉴 | URL |
|------|-----|
| 고객지원^안전한 통신생활^통신사기주의보 | https://inside.kt.com/html/safety/notice_list.html |

### `handle_safety_notice_detail`
> 상세 페이지는 목록에서 동적 추출됨

---

## 7. gigagenie.py (4개 핸들러)

### `handle_gigagenie_detail` ⭕️
| 패턴 | `gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=*` |
|------|----------------------------------------------------------|

| 메뉴 | URL |
|------|-----|
| 상품^TV^지니 AI서비스^서비스^서비스 안내^개인비서 | https://gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=secretary |
| 상품^TV^지니 AI서비스^서비스^서비스 안내^게임 | https://gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=homeEnt |
| 상품^TV^지니 AI서비스^서비스^서비스 안내^금융커머스 | https://gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=finance |
| 상품^TV^지니 AI서비스^서비스^서비스 안내^라이프스타일 | https://gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=lifestyle |
| 상품^TV^지니 AI서비스^서비스^서비스 안내^미디어 | https://gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=media |
| 상품^TV^지니 AI서비스^서비스^서비스 안내^생활정보 | https://gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=livingInfo |
| 상품^TV^지니 AI서비스^서비스^서비스 안내^키즈 | https://gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=kids |
| 상품^TV^지니 AI서비스^서비스^서비스 안내^편리한기능 | https://gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=useful |
| 상품^TV^지니 AI서비스^서비스^서비스 안내^multi-agent | https://gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=alexa |

### `handle_gigagenie_faq_playwright` ⭕️
| 패턴 | `gigagenie.kt.com/whyGenieFaq.do` |
|------|-----------------------------------|

| 메뉴 | URL |
|------|-----|
| 상품^TV^지니 AI서비스^자주 하는 질문 | https://gigagenie.kt.com/whyGenieFaq.do |

### `handle_gigagenie_news_list` ⭕️
| 패턴 | `gigagenie.kt.com/whyGenieNews.do` |
|------|-----------------------------------|

| 메뉴 | URL |
|------|-----|
| 상품^TV^지니 AI서비스^지니소식 | https://gigagenie.kt.com/whyGenieNews.do |

---

## 8. ktshop.py (11개 핸들러)

### `handle_ktshop_popup_extractor` ⭕️
| 패턴 | `shop.kt.com/direct/*` |
|------|------------------------|

| 메뉴 | URL |
|------|-----|
| Shop^USIM/eSIM 가입^eSIM 이동 | https://shop.kt.com/direct/directEsimMove.do |
| Shop^USIM/eSIM 가입^듀얼번호 가입 | https://shop.kt.com/direct/directDual.do |
| Shop^USIM/eSIM 가입^스마트기기 요금제 가입 | https://shop.kt.com/direct/directSmart.do |
| Shop^USIM/eSIM 가입^휴대폰 요금제 가입^USIM 구매 | https://shop.kt.com/direct/quickUsim.do |
| Shop^USIM/eSIM 가입^휴대폰 요금제 가입^USIM 가입 | https://shop.kt.com/direct/directUsim.do |
| Shop^USIM/eSIM 가입^휴대폰 요금제 가입^eSIM 가입 | https://shop.kt.com/direct/directEsim.do |

### `handle_mobile_products_list` ⭕️
| 패턴 | `shop.kt.com/mobile/products.do?category=*` |
|------|---------------------------------------------|

| 메뉴 | URL |
|------|-----|
| Shop^모바일 가입^핸드폰 | https://shop.kt.com/mobile/products.do?category=mobile |
| Shop^모바일 가입^스마트 워치 | https://shop.kt.com/mobile/products.do?category=watch |
| Shop^모바일 가입^태블릿 | https://shop.kt.com/mobile/products.do?category=tablet |
| Shop^모바일 가입^노트북/에그 | https://shop.kt.com/mobile/products.do?category=eggand |

### `handle_goodbye_phoneview` ⭕️
| 패턴 | `shop.kt.com/goodbye/phoneView.do` |
|------|-----------------------------------|

| 메뉴 | URL |
|------|-----|
| Shop^모바일 가입^중고폰 보상 신청 | https://shop.kt.com/goodbye/phoneView.do |

### `handle_store_plans_list` ⭕️
| 패턴 | `shop.kt.com/display/olhsStore.do?dispNo=STOR05&subDispNo=STOR0501` |
|------|-------------------------------------------------------------------|
| 패턴 | `shop.kt.com/display/olhsStore.do?dispNo=STOR05&subDispNo=STOR0503` |

| 메뉴 | URL |
|------|-----|
| Shop^핫딜/기획전^기획전^통신상품 | https://shop.kt.com/display/olhsStore.do?dispNo=STOR05&subDispNo=STOR0501 |
| Shop^핫딜/기획전^기획전^액세서리 | https://shop.kt.com/display/olhsStore.do?dispNo=STOR05&subDispNo=STOR0503 |

### `handle_accessory_display_list` ⭕️
| 패턴 | `shop.kt.com/display/olhsStore.do?dispNo=STOR04290*` |
|------|-----------------------------------------------------|

| 메뉴 | URL |
|------|-----|
| Shop^액세서리 구매^자급제폰/중고폰^갤럭시 자급제폰 | https://shop.kt.com/display/olhsStore.do?dispNo=STOR042902 |
| Shop^액세서리 구매^자급제폰/중고폰^샤오미 자급제폰 | https://shop.kt.com/display/olhsStore.do?dispNo=STOR042903 |

### `handle_accessory_detail`
> 상세 페이지는 목록에서 동적 추출됨

---

## 9. kt_event.py (2개 핸들러)

### `handle_kt_event_main` ⭕️
| 패턴 | `event.kt.com/html/event/ongoing_event_list.html` |
|------|--------------------------------------------------|

| 메뉴 | URL |
|------|-----|
| 혜택^이벤트/핫딜^진행중인 이벤트 | https://event.kt.com/html/event/ongoing_event_list.html |

### `handle_kt_event_detail`
> 상세 페이지는 목록에서 동적 추출됨

---

## 10. kt_past_event.py (2개 핸들러)

### `handle_kt_past_event_main` ⭕️
| 패턴 | `event.kt.com/html/event/past_event_list.html` |
|------|-----------------------------------------------|

| 메뉴 | URL |
|------|-----|
| 혜택^이벤트/핫딜^지난 이벤트 | https://event.kt.com/html/event/past_event_list.html |

### `handle_kt_past_event_detail`
> 상세 페이지는 목록에서 동적 추출됨

---

## 11. tv_channel.py (1개 핸들러)

### `handle_whygenietv_channel_schedule` ⭕️
| 패턴 | `tv.kt.com/tv/channel/pChInfo.asp` |
|------|-----------------------------------|

| 메뉴 | URL |
|------|-----|
| 상품^Why Genie TV^채널편성표 | https://tv.kt.com/tv/channel/pChInfo.asp |

---

## 12. webzine.py (1개 핸들러)

### `handle_webzine_list` ⭕️
| 패턴 | `shop.kt.com/unify/webzineList.do` |
|------|-----------------------------------|

| 메뉴 | URL |
|------|-----|
| Shop^핫딜/기획전^k-tmi 웹진 | https://shop.kt.com/unify/webzineList.do |

---

## 13. faq.py (2개 핸들러)

### `handle_movie_customer_center_faq_playwright` ⭕️
| 패턴 | `membership.kt.com/culture/movie/CustomerCenterInfo.do` |
|------|--------------------------------------------------------|

| 메뉴 | URL |
|------|-----|
| 혜택^영화/공연^영화예매^고객센터 | https://membership.kt.com/culture/movie/CustomerCenterInfo.do |

### `handle_ermsweb_faq_all_playwright` ⭕️
| 패턴 | `ermsweb.kt.com/pc/faq/faqList.do` |
|------|-----------------------------------|

| 메뉴 | URL |
|------|-----|
| 혜택^멤버십 안내^FAQ | https://membership.kt.com/guide/faq/FAQList.do |

---

## 14. wdic.py (2개 핸들러)

### `handle_product_detail`  ⭕️
| 패턴 | `product.kt.com/wDic/(soho/)?productDetail.do?ItemCode=*` |
|------|----------------------------------------------------------|

| 메뉴 | URL |
|------|-----|
| 상품^결합^따로살아도가족결합 | https://product.kt.com/wDic/productDetail.do?ItemCode=1630 |
| 상품^결합^신혼미리결합 | https://product.kt.com/wDic/productDetail.do?ItemCode=1441 |
| 상품^결합^프리미엄가족결합 | https://product.kt.com/wDic/productDetail.do?ItemCode=1193 |
| 상품^결합^프리미엄싱글결합 | https://product.kt.com/wDic/productDetail.do?ItemCode=1267 |
| 상품^모바일^듀얼번호/eSIM | https://product.kt.com/wDic/productDetail.do?ItemCode=1545 |
| 상품^인터넷^와이파이(WiFi)^소개 | https://product.kt.com/wDic/productDetail.do?ItemCode=1533 |
| 상품^TV^키즈랜드 | https://product.kt.com/wDic/productDetail.do?ItemCode=1243 |
| 상품^TV^Why Genie TV^소개 | https://product.kt.com/wDic/productDetail.do?ItemCode=1163 |
| 상품^인터넷^Why KT 인터넷^프리미엄급 인터넷 | https://product.kt.com/wDic/productDetail.do?ItemCode=1262 |
| 상품^인터넷^Why KT 인터넷^소개 | https://product.kt.com/wDic/productDetail.do?ItemCode=1452 |
| 상품^전화^국제전화^국제전화 이용방법 | https://product.kt.com/wDic/productDetail.do?ItemCode=1212 |
| 상품^소상공인^사장님혜택존 | https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1513 |

### `handle_wdic_mobile_list`  ⭕️
| 패턴 | `product.kt.com/wDic/*index.do?CateCode=*` |
|------|-------------------------------------------|

| 메뉴 | URL |
|------|-----|
| 상품^결합^결합상품 | https://product.kt.com/wDic/index.do?CateCode=6027 |
| 상품^모바일^부가서비스 | https://product.kt.com/wDic/index.do?CateCode=6003 |
| 상품^모바일^요금제 | https://product.kt.com/wDic/index.do?CateCode=6002 |
| 상품^인터넷^부가서비스 | https://product.kt.com/wDic/index.do?CateCode=6006 |
| 상품^인터넷^와이파이(WiFi)^요금제 | https://product.kt.com/wDic/index.do?CateCode=6042 |
| 상품^인터넷^요금제 | https://product.kt.com/wDic/index.do?CateCode=6005 |
| 상품^전화^일반전화^집전화/매장전화 | https://product.kt.com/wDic/index.do?CateCode=6011 |
| 상품^전화^일반전화^인터넷전화 | https://product.kt.com/wDic/index.do?CateCode=6012 |
| 상품^전화^일반전화^카드 콜렉트콜 | https://product.kt.com/wDic/index.do?CateCode=6014 |
| 상품^전화^국제전화^요금제 | https://product.kt.com/wDic/index.do?CateCode=6016 |
| 상품^전화^국제전화^부가서비스 | https://product.kt.com/wDic/index.do?CateCode=6017 |
| 상품^TV^부가서비스 | https://product.kt.com/wDic/index.do?CateCode=6009 |
| 상품^TV^요금제 | https://product.kt.com/wDic/index.do?CateCode=6008 |
| 상품^소상공인^매장솔루션 | https://product.kt.com/wDic/soho/index.do?CateCode=7008 |
| 상품^소상공인^통신상품 | https://product.kt.com/wDic/soho/index.do?CateCode=7002 |

---

## 15. winner_announcements.py (1개 핸들러)

### `handle_event_winner_announcements`  ⭕️
| 패턴 | `shop.kt.com/display/olhsStore.do?dispNo=STOR05&subDispNo=STOR0506` |
|------|-------------------------------------------------------------------|

| 메뉴 | URL |
|------|-----|
| Shop^핫딜/기획전^기획전^당첨자발표 | https://shop.kt.com/display/olhsStore.do?dispNo=STOR05&subDispNo=STOR0506 |

---

## 📊 요약

| 파일 | 핸들러 수 | 테스트 URL 수 |
|------|----------|--------------|
| membership.py | 2 | 2 |
| interpark.py | 2 | 1 |
| globalroaming.py | 2 | 1 |
| kt_notice.py | 2 | 1 |
| network_notice.py | 2 | 1 |
| safety_notice.py | 2 | 1 |
| gigagenie.py | 3 | 10 |
| ktshop.py | 6 | 14 |
| kt_event.py | 2 | 1 |
| kt_past_event.py | 2 | 1 (🔒) |
| tv_channel.py | 1 | 0 (직접) |
| webzine.py | 1 | 1 |
| faq.py | 2 | 1 |
| wdic.py | 2 | 27 |
| winner_announcements.py | 1 | 1 |
| **합계** | **32** | **63** |

