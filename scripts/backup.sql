--
-- PostgreSQL database dump
--

\restrict s05W6zfdVqFNmpMP0rGVSQn3xm3zbbCCpeu9FFCLz8LFniIYuiXC0OLSDGj3TM5

-- Dumped from database version 15.13 (Debian 15.13-1.pgdg120+1)
-- Dumped by pg_dump version 15.14 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: crawler_mind; Type: SCHEMA; Schema: -; Owner: admin
--

CREATE SCHEMA crawler_mind;


ALTER SCHEMA crawler_mind OWNER TO admin;

--
-- Name: check_menu_access(text[], character varying); Type: FUNCTION; Schema: crawler_mind; Owner: admin
--

CREATE FUNCTION crawler_mind.check_menu_access(p_role_names text[], p_menu_path character varying) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
DECLARE
    access_allowed BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 
        FROM accessible_menus_by_role_view amv
        WHERE amv.role_name = ANY(p_role_names)
            AND amv.path = p_menu_path
    ) INTO access_allowed;
    
    RETURN access_allowed;
END;
$$;


ALTER FUNCTION crawler_mind.check_menu_access(p_role_names text[], p_menu_path character varying) OWNER TO admin;

--
-- Name: check_role_permission(text[], character varying); Type: FUNCTION; Schema: crawler_mind; Owner: admin
--

CREATE FUNCTION crawler_mind.check_role_permission(p_role_names text[], p_permission_name character varying) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
DECLARE
    permission_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 
        FROM role_permissions rp
        JOIN permissions p ON rp.permission_id = p.id
        WHERE rp.role_name = ANY(p_role_names)
            AND p.name = p_permission_name
            AND p.is_active = TRUE
    ) INTO permission_exists;
    
    RETURN permission_exists;
END;
$$;


ALTER FUNCTION crawler_mind.check_role_permission(p_role_names text[], p_permission_name character varying) OWNER TO admin;

--
-- Name: get_accessible_menus(text[]); Type: FUNCTION; Schema: crawler_mind; Owner: admin
--

CREATE FUNCTION crawler_mind.get_accessible_menus(p_role_names text[]) RETURNS TABLE(menu_id bigint, parent_id bigint, name character varying, path character varying, icon character varying, order_index integer, description character varying)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT
        amv.menu_id,
        amv.parent_id,
        amv.menu_name,
        amv.path,
        amv.icon,
        amv.order_index,
        amv.description
    FROM accessible_menus_by_role_view amv
    WHERE amv.role_name = ANY(p_role_names)
    ORDER BY amv.order_index, amv.menu_name;
END;
$$;


ALTER FUNCTION crawler_mind.get_accessible_menus(p_role_names text[]) OWNER TO admin;

--
-- Name: get_role_permissions(text[]); Type: FUNCTION; Schema: crawler_mind; Owner: admin
--

CREATE FUNCTION crawler_mind.get_role_permissions(p_role_names text[]) RETURNS TABLE(permission_name character varying, resource character varying, action character varying, description character varying)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT
        p.name,
        p.resource,
        p.action,
        p.description
    FROM role_permissions rp
    JOIN permissions p ON rp.permission_id = p.id
    WHERE rp.role_name = ANY(p_role_names)
        AND p.is_active = TRUE
    ORDER BY p.resource, p.action;
END;
$$;


ALTER FUNCTION crawler_mind.get_role_permissions(p_role_names text[]) OWNER TO admin;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: menu_permissions; Type: TABLE; Schema: crawler_mind; Owner: admin
--

CREATE TABLE crawler_mind.menu_permissions (
    menu_id bigint NOT NULL,
    permission_id bigint NOT NULL
);


ALTER TABLE crawler_mind.menu_permissions OWNER TO admin;

--
-- Name: menus; Type: TABLE; Schema: crawler_mind; Owner: admin
--

CREATE TABLE crawler_mind.menus (
    id bigint NOT NULL,
    parent_id bigint,
    name character varying(100) NOT NULL,
    path character varying(255),
    icon character varying(100),
    order_index integer DEFAULT 0,
    is_active boolean DEFAULT true,
    is_visible boolean DEFAULT true,
    description character varying(255),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE crawler_mind.menus OWNER TO admin;

--
-- Name: role_permissions; Type: TABLE; Schema: crawler_mind; Owner: admin
--

CREATE TABLE crawler_mind.role_permissions (
    role_name character varying(50) NOT NULL,
    permission_id bigint NOT NULL,
    assigned_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE crawler_mind.role_permissions OWNER TO admin;

--
-- Name: accessible_menus_by_role_view; Type: VIEW; Schema: crawler_mind; Owner: admin
--

CREATE VIEW crawler_mind.accessible_menus_by_role_view AS
 SELECT DISTINCT rp.role_name,
    m.id AS menu_id,
    m.parent_id,
    m.name AS menu_name,
    m.path,
    m.icon,
    m.order_index,
    m.description
   FROM ((crawler_mind.role_permissions rp
     JOIN crawler_mind.menu_permissions mp ON ((rp.permission_id = mp.permission_id)))
     JOIN crawler_mind.menus m ON ((mp.menu_id = m.id)))
  WHERE ((m.is_active = true) AND (m.is_visible = true))
  ORDER BY rp.role_name, m.order_index, m.name;


ALTER TABLE crawler_mind.accessible_menus_by_role_view OWNER TO admin;

--
-- Name: menu_links; Type: TABLE; Schema: crawler_mind; Owner: admin
--

CREATE TABLE crawler_mind.menu_links (
    id bigint NOT NULL,
    document_id character varying(50),
    menu_path text NOT NULL,
    pc_url text,
    mobile_url text,
    created_by character varying(100),
    created_at timestamp with time zone DEFAULT now(),
    updated_by character varying(100),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE crawler_mind.menu_links OWNER TO admin;

--
-- Name: menu_links_id_seq; Type: SEQUENCE; Schema: crawler_mind; Owner: admin
--

CREATE SEQUENCE crawler_mind.menu_links_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE crawler_mind.menu_links_id_seq OWNER TO admin;

--
-- Name: menu_links_id_seq; Type: SEQUENCE OWNED BY; Schema: crawler_mind; Owner: admin
--

ALTER SEQUENCE crawler_mind.menu_links_id_seq OWNED BY crawler_mind.menu_links.id;


--
-- Name: menu_manager_info; Type: TABLE; Schema: crawler_mind; Owner: admin
--

CREATE TABLE crawler_mind.menu_manager_info (
    id integer NOT NULL,
    menu_id bigint NOT NULL,
    team_name text NOT NULL,
    manager_names text NOT NULL,
    created_by character varying(100),
    created_at timestamp with time zone DEFAULT now(),
    updated_by character varying(100),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE crawler_mind.menu_manager_info OWNER TO admin;

--
-- Name: menu_manager_info_id_seq; Type: SEQUENCE; Schema: crawler_mind; Owner: admin
--

CREATE SEQUENCE crawler_mind.menu_manager_info_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE crawler_mind.menu_manager_info_id_seq OWNER TO admin;

--
-- Name: menu_manager_info_id_seq; Type: SEQUENCE OWNED BY; Schema: crawler_mind; Owner: admin
--

ALTER SEQUENCE crawler_mind.menu_manager_info_id_seq OWNED BY crawler_mind.menu_manager_info.id;


--
-- Name: permissions; Type: TABLE; Schema: crawler_mind; Owner: admin
--

CREATE TABLE crawler_mind.permissions (
    id bigint NOT NULL,
    name character varying(100) NOT NULL,
    resource character varying(50) NOT NULL,
    action character varying(50) NOT NULL,
    description character varying(255),
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE crawler_mind.permissions OWNER TO admin;

--
-- Name: menu_permissions_view; Type: VIEW; Schema: crawler_mind; Owner: admin
--

CREATE VIEW crawler_mind.menu_permissions_view AS
 SELECT m.id AS menu_id,
    m.name AS menu_name,
    m.path,
    m.icon,
    m.order_index,
    m.parent_id,
    p.id AS permission_id,
    p.name AS permission_name,
    p.resource,
    p.action
   FROM ((crawler_mind.menus m
     JOIN crawler_mind.menu_permissions mp ON ((m.id = mp.menu_id)))
     JOIN crawler_mind.permissions p ON ((mp.permission_id = p.id)))
  WHERE ((m.is_active = true) AND (m.is_visible = true) AND (p.is_active = true))
  ORDER BY m.order_index, m.name;


ALTER TABLE crawler_mind.menu_permissions_view OWNER TO admin;

--
-- Name: menus_id_seq; Type: SEQUENCE; Schema: crawler_mind; Owner: admin
--

CREATE SEQUENCE crawler_mind.menus_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE crawler_mind.menus_id_seq OWNER TO admin;

--
-- Name: menus_id_seq; Type: SEQUENCE OWNED BY; Schema: crawler_mind; Owner: admin
--

ALTER SEQUENCE crawler_mind.menus_id_seq OWNED BY crawler_mind.menus.id;


--
-- Name: permissions_id_seq; Type: SEQUENCE; Schema: crawler_mind; Owner: admin
--

CREATE SEQUENCE crawler_mind.permissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE crawler_mind.permissions_id_seq OWNER TO admin;

--
-- Name: permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: crawler_mind; Owner: admin
--

ALTER SEQUENCE crawler_mind.permissions_id_seq OWNED BY crawler_mind.permissions.id;


--
-- Name: role_permissions_view; Type: VIEW; Schema: crawler_mind; Owner: admin
--

CREATE VIEW crawler_mind.role_permissions_view AS
 SELECT rp.role_name,
    p.id AS permission_id,
    p.name AS permission_name,
    p.resource,
    p.action,
    p.description AS permission_description
   FROM (crawler_mind.role_permissions rp
     JOIN crawler_mind.permissions p ON ((rp.permission_id = p.id)))
  WHERE (p.is_active = true)
  ORDER BY rp.role_name, p.resource, p.action;


ALTER TABLE crawler_mind.role_permissions_view OWNER TO admin;

--
-- Name: menu_links id; Type: DEFAULT; Schema: crawler_mind; Owner: admin
--

ALTER TABLE ONLY crawler_mind.menu_links ALTER COLUMN id SET DEFAULT nextval('crawler_mind.menu_links_id_seq'::regclass);


--
-- Name: menu_manager_info id; Type: DEFAULT; Schema: crawler_mind; Owner: admin
--

ALTER TABLE ONLY crawler_mind.menu_manager_info ALTER COLUMN id SET DEFAULT nextval('crawler_mind.menu_manager_info_id_seq'::regclass);


--
-- Name: menus id; Type: DEFAULT; Schema: crawler_mind; Owner: admin
--

ALTER TABLE ONLY crawler_mind.menus ALTER COLUMN id SET DEFAULT nextval('crawler_mind.menus_id_seq'::regclass);


--
-- Name: permissions id; Type: DEFAULT; Schema: crawler_mind; Owner: admin
--

ALTER TABLE ONLY crawler_mind.permissions ALTER COLUMN id SET DEFAULT nextval('crawler_mind.permissions_id_seq'::regclass);


--
-- Data for Name: menu_links; Type: TABLE DATA; Schema: crawler_mind; Owner: admin
--

COPY crawler_mind.menu_links (id, document_id, menu_path, pc_url, mobile_url, created_by, created_at, updated_by, updated_at) FROM stdin;
102	ktcom_368	상품	https://product.kt.com	https://m.product.kt.com/	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
377	ktcom_430	상품^모바일^WiFi이용안내^MACID등록	https://wifi.kt.com/kt/kt_wifi_macid2.html		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
375	ktcom_655	상품^모바일^추천앱^PASS	https://fido.kt.com/ktauthIntro		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
382	ktcom_435	상품^모바일^WiFi이용안내^WiFi설정안내	https://wifi.kt.com/kt/kt_main.html		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
144	ktcom_412	상품^로밍^한눈에보기	http://globalroaming.kt.com/main.asp	http://m.globalroaming.kt.com/main.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
558	ktcom_365	상품^TV^요금제	https://product.kt.com/wDic/index.do?CateCode=6008	https://m.product.kt.com/wDic/index.do?CateCode=6008	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
142	ktcom_410	상품^로밍^로밍이용꿀팁^통화데이터이용법	https://globalroaming.kt.com/info/all2.asp	https://m.globalroaming.kt.com/info/all2.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
616	ktcom_12	Shop^마이샵이용안내^이용안내^인터넷TV가입이용안내	https://shop.kt.com/support/shopInternetTvGuide.do	https://m.shop.kt.com/support/shopInternetTvGuide.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
1	ktcom_14	고객지원	https://help.kt.com/main.jsp	https://m.help.kt.com/s_main.jsp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
2	ktcom_14	고객지원^공지이용안내	https://help.kt.com/main.jsp	https://m.help.kt.com/s_main.jsp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
3	\N	고객지원^공지이용안내^공지사항	https://inside.kt.com/html/notice/notice_list.html	https://m.kt.com/html/notice/notice_list.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
4	ktcom_206	고객지원^공지이용안내^서비스안내	http://help.kt.com/serviceinfo/ServiceJoinGuide.do	http://m.help.kt.com/serviceinfo/s_ServiceJoinGuide.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
5	ktcom_209	고객지원^공지이용안내^서비스안내^상품가입^가입방법안내	http://help.kt.com/serviceinfo/ServiceJoinGuideL1.do	http://m.help.kt.com/serviceinfo/s_ServiceJoinGuideL1.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
6	ktcom_210	고객지원^공지이용안내^서비스안내^상품가입^가입비안내	http://help.kt.com/serviceinfo/ServiceJoinGuideL3.do	https://m.help.kt.com/serviceinfo/s_ServiceJoinGuideL3.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
7	ktcom_211	고객지원^공지이용안내^서비스안내^상품가입^가입신청구비서류안내	http://help.kt.com/serviceinfo/ServiceJoinGuideL4.do	https://m.help.kt.com/serviceinfo/s_ServiceJoinGuideL4.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
8	ktcom_212	고객지원^공지이용안내^서비스안내^상품가입^모바일번호이동가입안내	http://help.kt.com/serviceinfo/ServiceJoinGuideL2.do	https://m.help.kt.com/serviceinfo/s_ServiceJoinGuideL2.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
9	ktcom_213	고객지원^공지이용안내^서비스안내^상품가입^애플워치연결안내	http://help.kt.com/serviceinfo/ServiceJoinGuideL7.do	https://m.help.kt.com/serviceinfo/s_ServiceJoinGuideL7.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
10	ktcom_208	고객지원^공지이용안내^서비스안내^상품가입^KT모바일전화번호관리기준	http://help.kt.com/serviceinfo/ServiceJoinGuideL5.do	https://m.help.kt.com/serviceinfo/s_ServiceJoinGuideL5.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
11	ktcom_207	고객지원^공지이용안내^서비스안내^상품가입^KT모바일전화번호관리기준^KT모바일010MappingTable보기	https://help.kt.com/custom/MoCustomInfoPopup1.do		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
12	ktcom_216	고객지원^공지이용안내^서비스안내^상품변경^금융USIM활용	http://help.kt.com/serviceinfo/ServiceAlterGuideL20.do	https://m.help.kt.com/serviceinfo/s_ServiceAlterGuideL20.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
13	ktcom_217	고객지원^공지이용안내^서비스안내^상품변경^기변안내	http://help.kt.com/serviceinfo/ServiceAlterGuideL4.do	https://m.help.kt.com/serviceinfo/s_ServiceAlterGuideL4.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
14	ktcom_218	고객지원^공지이용안내^서비스안내^상품변경^다른고객의휴대폰사용방법	http://help.kt.com/serviceinfo/ServiceAlterGuideL13.do	https://m.help.kt.com/serviceinfo/s_ServiceAlterGuideL13.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
15	ktcom_219	고객지원^공지이용안내^서비스안내^상품변경^명의변경방법	http://help.kt.com/serviceinfo/ServiceAlterGuideL1.do	https://m.help.kt.com/serviceinfo/s_ServiceAlterGuideL1.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
16	ktcom_220	고객지원^공지이용안내^서비스안내^상품변경^모바일일시정지	http://help.kt.com/serviceinfo/ServiceAlterGuideL6.do	https://m.help.kt.com/serviceinfo/s_ServiceAlterGuideL6.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
17	ktcom_221	고객지원^공지이용안내^서비스안내^상품변경^사업자간USIM이동성	http://help.kt.com/serviceinfo/ServiceAlterGuideL12.do	https://m.help.kt.com/serviceinfo/s_ServiceAlterGuideL12.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
18	ktcom_222	고객지원^공지이용안내^서비스안내^상품변경^승계프로그램	http://help.kt.com/serviceinfo/ServiceAlterGuideL5.do	https://m.help.kt.com/serviceinfo/s_ServiceAlterGuideL5.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
19	ktcom_223	고객지원^공지이용안내^서비스안내^상품변경^이동성관련유의사항	http://help.kt.com/serviceinfo/ServiceAlterGuideL18.do	https://m.help.kt.com/serviceinfo/s_ServiceAlterGuideL18.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
20	ktcom_224	고객지원^공지이용안내^서비스안내^상품변경^타통신사휴대폰에서무선인터넷이용	http://help.kt.com/serviceinfo/ServiceAlterGuideL15.do	https://m.help.kt.com/serviceinfo/s_ServiceAlterGuideL15.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
21	ktcom_225	고객지원^공지이용안내^서비스안내^상품변경^타통신사휴대폰으로USIM이동	http://help.kt.com/serviceinfo/ServiceAlterGuideL14.do	https://m.help.kt.com/serviceinfo/s_ServiceAlterGuideL14.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
22	ktcom_226	고객지원^공지이용안내^서비스안내^상품변경^타통신사휴대폰이동시기존서비스이용	http://help.kt.com/serviceinfo/ServiceAlterGuideL16.do	https://m.help.kt.com/serviceinfo/s_ServiceAlterGuideL16.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
23	ktcom_227	고객지원^공지이용안내^서비스안내^상품변경^통화내역열람(지점방문)	http://help.kt.com/serviceinfo/ServiceAlterGuideL7.do	https://m.help.kt.com/serviceinfo/s_ServiceAlterGuideL7.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
24	ktcom_228	고객지원^공지이용안내^서비스안내^상품변경^통화내역열람(홈페이지)	http://help.kt.com/serviceinfo/ServiceAlterGuideL8.do	https://m.help.kt.com/serviceinfo/s_ServiceAlterGuideL8.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
25	ktcom_229	고객지원^공지이용안내^서비스안내^상품변경^휴대폰분실시해야할일	http://help.kt.com/serviceinfo/ServiceAlterGuideL17.do	https://m.help.kt.com/serviceinfo/s_ServiceAlterGuideL17.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
26	ktcom_214	고객지원^공지이용안내^서비스안내^상품변경^USIM	http://help.kt.com/serviceinfo/ServiceAlterGuideL9.do	https://m.help.kt.com/serviceinfo/s_ServiceAlterGuideL9.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
27	ktcom_215	고객지원^공지이용안내^서비스안내^상품변경^USIM이동성	http://help.kt.com/serviceinfo/ServiceAlterGuideL11.do	https://m.help.kt.com/serviceinfo/s_ServiceAlterGuideL11.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
28	ktcom_230	고객지원^공지이용안내^서비스안내^상품해지^모바일해지구비서류안내	http://help.kt.com/serviceinfo/ServiceCloseGuideL1.do	https://m.help.kt.com/serviceinfo/s_ServiceCloseGuideL1.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
29	ktcom_231	고객지원^공지이용안내^서비스안내^상품해지^홈상품해지구비서류안내	http://help.kt.com/serviceinfo/ServiceCloseGuideL2.do	https://m.help.kt.com/serviceinfo/s_ServiceCloseGuideL2.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
30	ktcom_232	고객지원^공지이용안내^서비스안내^요금납부^과오납등유보금미환급요금안내	http://help.kt.com/serviceinfo/BillPaymentGuideL7.do	https://m.help.kt.com/serviceinfo/s_BillPaymentGuideL7.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
31	ktcom_233	고객지원^공지이용안내^서비스안내^요금납부^납기일	http://help.kt.com/serviceinfo/BillPaymentGuideL6.do	https://m.help.kt.com/serviceinfo/s_BillPaymentGuideL6.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
32	ktcom_234	고객지원^공지이용안내^서비스안내^요금납부^모바일채권보존료미환급금안내	http://help.kt.com/serviceinfo/BillPaymentGuideL9.do	https://m.help.kt.com/serviceinfo/s_BillPaymentGuideL9.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
33	ktcom_235	고객지원^공지이용안내^서비스안내^요금납부^모바일해지미환급금안내	http://help.kt.com/serviceinfo/BillPaymentGuideL8.do	https://m.help.kt.com/serviceinfo/s_BillPaymentGuideL8.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
34	ktcom_236	고객지원^공지이용안내^서비스안내^요금납부^온라인즉시납부	http://help.kt.com/serviceinfo/BillPaymentGuideL2.do	https://m.help.kt.com/serviceinfo/s_BillPaymentGuideL2.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
35	ktcom_237	고객지원^공지이용안내^서비스안내^요금납부^요금기준안내	http://help.kt.com/serviceinfo/BillPaymentGuideL1.do	https://m.help.kt.com/serviceinfo/s_BillPaymentGuideL1.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
36	ktcom_238	고객지원^공지이용안내^서비스안내^요금납부^요금항목	http://help.kt.com/serviceinfo/BillPaymentGuideL5.do	https://m.help.kt.com/serviceinfo/s_BillPaymentGuideL5.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
37	ktcom_239	고객지원^공지이용안내^서비스안내^요금납부^자동납부	http://help.kt.com/serviceinfo/BillPaymentGuideL3.do	https://m.help.kt.com/serviceinfo/s_BillPaymentGuideL3.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
38	ktcom_240	고객지원^공지이용안내^서비스안내^요금납부^지로납부	http://help.kt.com/serviceinfo/BillPaymentGuideL4.do	https://m.help.kt.com/serviceinfo/s_BillPaymentGuideL4.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
39	ktcom_241	고객지원^공지이용안내^서비스안내^요금납부^통신비자동이체변경	http://help.kt.com/serviceinfo/BillPaymentGuideL10.do	https://m.help.kt.com/serviceinfo/s_BillPaymentGuideL10.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
40	ktcom_242	고객지원^공지이용안내^서비스안내^요금명세서^요금명세서안내	http://help.kt.com/serviceinfo/BillStatementGuideL1.do	https://m.help.kt.com/serviceinfo/s_BillStatementGuideL1.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
41	ktcom_243	고객지원^공지이용안내^서비스안내^제휴혜택^금리우대혜택	http://help.kt.com/serviceinfo/ServiceBenefitGuideL1.do		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
42	ktcom_244	고객지원^공지이용안내^신청서자료실^신청서다운로드^모바일이용신청서	https://help.kt.com/serviceinfo/UseRegUseInfo.do		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
43	ktcom_245	고객지원^공지이용안내^신청서자료실^신청서다운로드^모바일이용신청서^이용신청서작성	https://help.kt.com/serviceinfo/UseRegUseWriter.do		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
44	ktcom_247	고객지원^공지이용안내^웹접근성가이드^보이스오버이용안내	https://inside.kt.com/html/accessibility/webHelp_04.html	https://m.kt.com/html/accessibility/m_accessibility_03.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
45	ktcom_248	고객지원^공지이용안내^웹접근성가이드^웹접근성이란	https://inside.kt.com/html/accessibility/webHelp_01.html	https://m.kt.com/html/accessibility/m_accessibility_01.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
46	ktcom_249	고객지원^공지이용안내^웹접근성가이드^차별없는환경만들기	https://inside.kt.com/html/accessibility/webHelp_02.html	https://m.kt.com/html/accessibility/m_accessibility_02.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
47	ktcom_246	고객지원^공지이용안내^웹접근성가이드^ktcom단축키안내	https://inside.kt.com/html/accessibility/webHelp_03.html		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
48	ktcom_250	고객지원^공지이용안내^장애인전용서비스^장애인상품가입안내^복지할인제도	https://help.kt.com/disabledInfo/DisabledProdGuide3.do	https://m.help.kt.com/disabledInfo/s_DisabledProdGuide3.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
49	ktcom_251	고객지원^공지이용안내^장애인전용서비스^장애인상품가입안내^전용부가서비스	https://help.kt.com/disabledInfo/DisabledProdGuide2.do	https://m.help.kt.com/disabledInfo/s_DisabledProdGuide2.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
50	ktcom_252	고객지원^공지이용안내^장애인전용서비스^장애인상품가입안내^전용요금제	https://help.kt.com/disabledInfo/DisabledProdGuide1.do	https://m.help.kt.com/disabledInfo/s_DisabledProdGuide1.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
51	ktcom_253	고객지원^공지이용안내^장애인전용서비스^장애인용서비스이용안내^기타유용한TIP	https://help.kt.com/disabledInfo/DisabledServiceGuide4.do	https://m.help.kt.com/disabledInfo/s_DisabledServiceGuide4.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
52	ktcom_254	고객지원^공지이용안내^장애인전용서비스^장애인용서비스이용안내^전용고객센터	https://help.kt.com/disabledInfo/DisabledServiceGuide1.do	https://m.help.kt.com/disabledInfo/s_DisabledServiceGuide1.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
53	ktcom_255	고객지원^공지이용안내^장애인전용서비스^장애인용서비스이용안내^전용요금명세서	https://help.kt.com/disabledInfo/DisabledServiceGuide2.do	https://m.help.kt.com/disabledInfo/s_DisabledServiceGuide2.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
54	\N	고객지원^공지이용안내^통신서비스중단작업공지	https://inside.kt.com/html/notice/net_notice_list.html	https://m.kt.com/html/notice/net_notice_list.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
55	ktcom_260	고객지원^공지이용안내^통신장애손해배상안내	https://help.kt.com/serviceinfo/CommTrobReptnInfo.do	https://m.help.kt.com/serviceinfo/s_CommTrobReptnInfo.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
56	ktcom_12	고객지원^공지이용안내^Shop이용안내^인터넷TV가입이용안내	https://shop.kt.com/support/shopInternetTvGuide.do	https://m.shop.kt.com/support/shopInternetTvGuide.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
57	ktcom_13	고객지원^공지이용안내^Shop이용안내^핸드폰구매이용안내	https://shop.kt.com/support/shopMobileGuide.do	https://m.shop.kt.com/support/shopMobileGuide.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
58	ktcom_261	고객지원^대리점고객센터안내	https://help.kt.com/store/KtStoreSearch.do	https://m.help.kt.com/store/s_KtStoreSearch.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
59	ktcom_264	고객지원^대리점고객센터안내^고객센터안내^수어시각장애인상담	https://help.kt.com/store/VideoCnslg.do		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
60	ktcom_265	고객지원^대리점고객센터안내^고객센터안내^채팅상담	https://help.kt.com/store/ChatCnslg.do		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
61	ktcom_262	고객지원^대리점고객센터안내^고객센터안내^ARS이용안내	https://help.kt.com/store/ArsUseGuide.do		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
62	ktcom_263	고객지원^대리점고객센터안내^고객센터안내^KT고객센터	https://help.kt.com/store/KtCustCenter.do		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
63	ktcom_266	고객지원^대리점고객센터안내^제조사별AS센터안내	http://help.kt.com/asreq/MobileAsCenterInfo.do	http://m.help.kt.com/asreq/s_MobileAsCenterInfo.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
64	ktcom_267	고객지원^셀프진단및AS신청^간편한셀프해결	https://help.kt.com/servicetip/ServiceTipInfo.do	https://m.help.kt.com/servicetip/s_ServiceTipInfo.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
65	ktcom_268	고객지원^셀프진단및AS신청^서비스가능지역찾기	https://help.kt.com/serviceinfo/SearchHomePhone.do	https://m.help.kt.com/serviceinfo/s_SearchHomePhone.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
66	ktcom_269	고객지원^셀프진단및AS신청^서비스커버리지	https://nqi.kt.com/KTCVRG/ollehIntro		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
67	ktcom_270	고객지원^셀프진단및AS신청^셀프개통^설치가이드	https://help.kt.com/asreq/SelfOpenInstallGuide.do		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
68	ktcom_271	고객지원^셀프진단및AS신청^셀프개통^셀프개통	https://help.kt.com/asreq/SelfOpenInfo.do	https://m.help.kt.com/asreq/s_SelfOpenInfo.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
69	ktcom_273	고객지원^셀프진단및AS신청^인터넷속도측정	http://speed.kt.com/speed/speedtest/introduce.asp		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
70	ktcom_272	고객지원^셀프진단및AS신청^인터넷TV고장진단	https://help.kt.com/asreq/HomeAsReqStatusInfo.do	https://m.help.kt.com/asreq/s_HomeAsReqStatusInfo.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
71	ktcom_274	고객지원^안전한통신생활^스미싱지킴이	https://inside.kt.com/html/safety/smishing.html	https://m.kt.com/html/safety/smishing.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
72	ktcom_275	고객지원^안전한통신생활^스팸차단서비스^내스팸정보	https://spamfilter.mobile.kt.com/safety.do		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
73	ktcom_276	고객지원^안전한통신생활^안심QR서비스	https://inside.kt.com/html/safety/secure_QR.html	https://m.kt.com/html/safety/secure_QR.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
74	ktcom_286	고객지원^안전한통신생활^이용자피해예방가이드	https://inside.kt.com/html/privacy/privacy01.html	https://m.kt.com/html/privacy/privacy_01.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
75	ktcom_278	고객지원^안전한통신생활^이용자피해예방가이드^개인정보보호^개인정보처리방침	https://inside.kt.com/html/privacy/privacy23.html	https://m.kt.com/html/privacy/privacy_23.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
76	ktcom_279	고객지원^안전한통신생활^이용자피해예방가이드^개인정보보호^개인정보처리방침^개인정보처리방침인포그래픽	https://inside.kt.com/html/privacy/privacy12.html	https://m.kt.com/html/privacy/privacy_12.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
77	ktcom_280	고객지원^안전한통신생활^이용자피해예방가이드^개인정보보호^알기쉬운개인정보보호^개인정보란무엇인가요	https://inside.kt.com/html/privacy/privacy15.html	https://m.kt.com/html/privacy/privacy_15.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
78	ktcom_281	고객지원^안전한통신생활^이용자피해예방가이드^개인정보보호^알기쉬운개인정보보호^개인정보보호서비스안내	https://inside.kt.com/html/privacy/privacy17.html	https://m.kt.com/html/privacy/privacy_17.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
79	ktcom_282	고객지원^안전한통신생활^이용자피해예방가이드^개인정보보호^알기쉬운개인정보보호^개인정보유출시대처법	https://inside.kt.com/html/privacy/privacy16.html	https://m.kt.com/html/privacy/privacy_16.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
80	ktcom_283	고객지원^안전한통신생활^이용자피해예방가이드^개인정보보호^알기쉬운개인정보보호^개인정보이용제공내역	https://inside.kt.com/html/privacy/privacy19.html	https://m.kt.com/html/privacy/privacy_19.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
81	ktcom_284	고객지원^안전한통신생활^이용자피해예방가이드^개인정보보호^알기쉬운개인정보보호^주민번호사용제한정책안내	https://inside.kt.com/html/privacy/privacy18.html	https://m.kt.com/html/privacy/privacy_18.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
82	ktcom_286	고객지원^안전한통신생활^이용자피해예방가이드^피해예방가이드^가이드전체	https://inside.kt.com/html/privacy/privacy01.html	https://m.kt.com/html/privacy/privacy_01.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
83	ktcom_287	고객지원^안전한통신생활^이용자피해예방가이드^피해예방가이드^메신저보이스피싱예방법	https://inside.kt.com/html/privacy/privacy03.html	https://m.kt.com/html/privacy/privacy_03.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
84	ktcom_288	고객지원^안전한통신생활^이용자피해예방가이드^피해예방가이드^메신저보이스피싱예방법^메신저보이스피싱대처법	https://inside.kt.com/html/privacy/privacy05.html	https://m.kt.com/html/privacy/privacy_05.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
112	ktcom_378	상품^결합^신혼미리결합	https://product.kt.com/wDic/productDetail.do?ItemCode=1441	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1441	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
85	ktcom_289	고객지원^안전한통신생활^이용자피해예방가이드^피해예방가이드^메신저보이스피싱예방법^보이스피싱이란	https://inside.kt.com/html/privacy/privacy04.html	https://m.kt.com/html/privacy/privacy_04.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
503	ktcom_773	상품^전화^일반전화^카드콜렉트콜	https://product.kt.com/wDic/index.do?CateCode=6014	https://m.product.kt.com/wDic/index.do?CateCode=6014	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
86	ktcom_290	고객지원^안전한통신생활^이용자피해예방가이드^피해예방가이드^불법TM식별및신고방법	https://inside.kt.com/html/privacy/privacy11.html	https://m.kt.com/html/privacy/privacy_11.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
87	ktcom_291	고객지원^안전한통신생활^이용자피해예방가이드^피해예방가이드^비밀번호안전하게사용하기	https://inside.kt.com/html/privacy/privacy10.html	https://m.kt.com/html/privacy/privacy_10.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
88	ktcom_292	고객지원^안전한통신생활^이용자피해예방가이드^피해예방가이드^스마트폰이용시주의사항	https://inside.kt.com/html/privacy/privacy07.html	https://m.kt.com/html/privacy/privacy_07.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
89	ktcom_293	고객지원^안전한통신생활^이용자피해예방가이드^피해예방가이드^스팸메일차단대응방법	https://inside.kt.com/html/privacy/privacy02.html	https://m.kt.com/html/privacy/privacy_02.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
90	ktcom_294	고객지원^안전한통신생활^이용자피해예방가이드^피해예방가이드^악성코드바이러스차단방법	https://inside.kt.com/html/privacy/privacy06.html	https://m.kt.com/html/privacy/privacy_06.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
149	ktcom_418	상품^로밍상품정보^편리한부가기능^로밍 수신사업자선택	https://globalroaming.kt.com/product/free/trader.asp	https://m.globalroaming.kt.com/product/free/trader.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
91	ktcom_295	고객지원^안전한통신생활^이용자피해예방가이드^피해예방가이드^청소년불법알바주의사항	https://inside.kt.com/html/privacy/privacy22.html	https://m.kt.com/html/privacy/privacy_22.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
92	ktcom_296	고객지원^안전한통신생활^이용자피해예방가이드^피해예방가이드^통신사기피해방지안내	https://inside.kt.com/html/privacy/privacy21.html	https://m.kt.com/html/privacy/privacy_21.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
93	ktcom_297	고객지원^안전한통신생활^이용자피해예방가이드^피해예방가이드^파일공유이용시주의사항	https://inside.kt.com/html/privacy/privacy09.html	https://m.kt.com/html/privacy/privacy_09.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
94	ktcom_285	고객지원^안전한통신생활^이용자피해예방가이드^피해예방가이드^SNS이용시주의사항	https://inside.kt.com/html/privacy/privacy08.html	https://m.kt.com/html/privacy/privacy_08.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
95	ktcom_298	고객지원^안전한통신생활^추천AI안심부가서비스	https://inside.kt.com/html/safety/recommended_relax.html	https://m.kt.com/html/safety/recommended_relax.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
96	\N	고객지원^안전한통신생활^통신사기주의보	https://inside.kt.com/html/safety/notice_list.html	https://m.kt.com/html/safety/notice_list.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
97	ktcom_300	고객지원^온라인문의^자주하는질문	https://ermsweb.kt.com/pc/faq/faqList.do	https://m.ermsweb.kt.com/pc/faq/faqList.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
98	ktcom_301	고객지원^휴대폰분실신고해제^단말보험보상받기	https://help.kt.com/lostphone/CompDeviceInsurance.do	https://m.help.kt.com/lostphone/s_CompDeviceInsurance.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
99	ktcom_302	고객지원^휴대폰분실신고해제^분실신고해제	https://help.kt.com/lostphone/LostReportOrCancel.do	https://m.help.kt.com/lostphone/s_LostReportOrCancel.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
100	ktcom_303	고객지원^휴대폰분실신고해제^분실휴대폰위치찾기	https://help.kt.com/lostphone/LocatingLostPhone.do	https://m.help.kt.com/lostphone/s_LocatingLostPhone.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
101	ktcom_304	고객지원^휴대폰분실신고해제^임대폰신청	https://help.kt.com/lostphone/ApplyRentalPhone.do	https://m.help.kt.com/lostphone/s_ApplyRentalPhone.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
103	ktcom_371	상품^결합^결합상품	https://product.kt.com/wDic/index.do?CateCode=6027	https://m.product.kt.com/wDic/index.do?CateCode=6027	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
104	ktcom_369	상품^결합^결합상품^3G 뭉치면올레	https://product.kt.com/wDic/productDetail.do?ItemCode=1&CateCode=6027&filter_code=114&option_code=166&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1&CateCode=6027&filter_code=114&option_code=166&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
105	ktcom_372	상품^결합^결합상품^싱글 인터넷 베이직 tv	https://product.kt.com/wDic/productDetail.do?ItemCode=1383&CateCode=6027&filter_code=114&option_code=166&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1383&CateCode=6027&filter_code=114&option_code=166&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
106	ktcom_373	상품^결합^결합상품^요고뭉치 결합	https://product.kt.com/wDic/productDetail.do?ItemCode=1571&CateCode=6027&filter_code=114&option_code=166&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1571&CateCode=6027&filter_code=114&option_code=166&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
107	ktcom_374	상품^결합^결합상품^우리가족 무선결합	https://product.kt.com/wDic/productDetail.do?ItemCode=977&CateCode=6027&filter_code=114&option_code=166&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=977&CateCode=6027&filter_code=114&option_code=166&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
108	ktcom_375	상품^결합^결합상품^총액 결합할인	https://product.kt.com/wDic/productDetail.do?ItemCode=1133&CateCode=6027&filter_code=114&option_code=166&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1133&CateCode=6027&filter_code=114&option_code=166&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
109	ktcom_376	상품^결합^결합상품^홈 결합상품	https://product.kt.com/wDic/productDetail.do?ItemCode=2&CateCode=6027&filter_code=114&option_code=166&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=2&CateCode=6027&filter_code=114&option_code=166&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
110	ktcom_370	상품^결합^결합상품^Y끼리 무선결합	https://product.kt.com/wDic/productDetail.do?ItemCode=1565&CateCode=6027&filter_code=114&option_code=166&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1565&CateCode=6027&filter_code=114&option_code=166&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
111	ktcom_377	상품^결합^따로살아도가족결합	https://product.kt.com/wDic/productDetail.do?ItemCode=1630	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1630	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
143	ktcom_411	상품^로밍^로밍이용꿀팁^해외장기체류	https://globalroaming.kt.com/info/all1.asp		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
113	ktcom_379	상품^결합^프리미엄가족결합	https://product.kt.com/wDic/productDetail.do?ItemCode=1193	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1193	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
114	ktcom_380	상품^결합^프리미엄싱글결합	https://product.kt.com/wDic/productDetail.do?ItemCode=1267	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1267	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
115	ktcom_381	상품^결합^핸드폰+인터넷+TV가입	https://shop.kt.com/lineCombOrder/lineCombList.do		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
116	ktcom_383	상품^국제전화^부가서비스^국제 콜렉트콜	https://product.kt.com/wDic/productDetail.do?ItemCode=254&CateCode=6017&filter_code=31&option_code=54&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=254&CateCode=6017&filter_code=31&option_code=54&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
117	ktcom_382	상품^국제전화^부가서비스^국제 SMS	https://product.kt.com/wDic/productDetail.do?ItemCode=253&CateCode=6017&filter_code=31&option_code=54&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=253&CateCode=6017&filter_code=31&option_code=54&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
118	ktcom_384	상품^국제전화^부가서비스^요금즉시통보 0071	https://product.kt.com/wDic/productDetail.do?ItemCode=257&CateCode=6017&filter_code=31&option_code=54&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=257&CateCode=6017&filter_code=31&option_code=54&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
119	ktcom_385	상품^국제전화^부가서비스^제3자 요금부담 0073	https://product.kt.com/wDic/productDetail.do?ItemCode=258&CateCode=6017&filter_code=31&option_code=54&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=258&CateCode=6017&filter_code=31&option_code=54&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
120	ktcom_387	상품^국제전화^요금제^001 중소기업 요금제	https://product.kt.com/wDic/productDetail.do?ItemCode=251&CateCode=6016&filter_code=30&option_code=53&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=251&CateCode=6016&filter_code=30&option_code=53&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
121	ktcom_386	상품^국제전화^요금제^001 Free	https://product.kt.com/wDic/productDetail.do?ItemCode=1000&CateCode=6016&filter_code=29&option_code=52&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1000&CateCode=6016&filter_code=29&option_code=52&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
122	ktcom_388	상품^국제전화^요금제^00727	https://product.kt.com/wDic/productDetail.do?ItemCode=256&CateCode=6016&filter_code=28&option_code=51&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=256&CateCode=6016&filter_code=28&option_code=51&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
123	ktcom_389	상품^국제전화^요금제^실속있는 00345	https://product.kt.com/wDic/productDetail.do?ItemCode=259&CateCode=6016&filter_code=28&option_code=51&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=259&CateCode=6016&filter_code=28&option_code=51&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
124	ktcom_390	상품^국제전화^요금제^알짜 요금제	https://product.kt.com/wDic/productDetail.do?ItemCode=245&CateCode=6016&filter_code=30&option_code=53&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=245&CateCode=6016&filter_code=30&option_code=53&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
125	ktcom_391	상품^국제전화^요금제^품질좋은 001	https://product.kt.com/wDic/productDetail.do?ItemCode=1125&CateCode=6016&filter_code=28&option_code=51&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1125&CateCode=6016&filter_code=28&option_code=51&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
126	ktcom_392	상품^로밍^국가별로밍안내	http://globalroaming.kt.com/rate/rate.asp	http://m.globalroaming.kt.com/rate/rate.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
127	ktcom_393	상품^로밍^로밍고객센터	http://globalroaming.kt.com/center/internal.asp	http://m.globalroaming.kt.com/center/internal.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
128	ktcom_396	상품^로밍^로밍상품정보^데이터	http://globalroaming.kt.com/product/data/main.asp	http://m.globalroaming.kt.com/product/data/main.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
129	ktcom_397	상품^로밍^로밍상품정보^데이터^데이터로밍12시간	https://globalroaming.kt.com/product/data/dru_period_12.asp	https://m.globalroaming.kt.com/product/data/dru_period_12.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
130	ktcom_398	상품^로밍^로밍상품정보^데이터^중일로밍2.5GB	https://globalroaming.kt.com/product/data/cjdrg1.asp	https://m.globalroaming.kt.com/product/data/cjdrg1.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
131	ktcom_399	상품^로밍^로밍상품정보^데이터^하루종일로밍베이직	https://globalroaming.kt.com/product/data/dru_period.asp	https://m.globalroaming.kt.com/product/data/dru_period.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
132	ktcom_400	상품^로밍^로밍상품정보^데이터^하루종일로밍베이직투게더	https://globalroaming.kt.com/product/data/dru_two.asp	https://m.globalroaming.kt.com/product/data/dru_two.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
133	ktcom_401	상품^로밍^로밍상품정보^데이터^하루종일로밍톡	https://globalroaming.kt.com/product/data/dru_talk.asp	https://m.globalroaming.kt.com/product/data/dru_talk.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
134	ktcom_402	상품^로밍^로밍상품정보^데이터^하루종일로밍프리미엄	https://globalroaming.kt.com/product/data/dru_unlimit.asp	https://m.globalroaming.kt.com/product/data/dru_unlimit.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
135	ktcom_403	상품^로밍^로밍상품정보^데이터^하루종일로밍플러스	https://globalroaming.kt.com/product/data/dru_lte.asp	https://m.globalroaming.kt.com/product/data/dru_lte.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
136	ktcom_404	상품^로밍^로밍상품정보^데이터^함께쓰는로밍	https://globalroaming.kt.com/product/data/gasam.asp	https://m.globalroaming.kt.com/product/data/gasam.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
137	ktcom_405	상품^로밍^로밍상품정보^데이터^함께쓰는로밍(충전)	https://globalroaming.kt.com/product/data/toacharge.asp	https://m.globalroaming.kt.com/product/data/toacharge.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
138	ktcom_406	상품^로밍^로밍상품정보^로밍에그	https://globalroaming.kt.com/product/data/ore.asp	https://m.globalroaming.kt.com/product/data/ore.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
139	ktcom_407	상품^로밍^로밍상품정보^음성	http://globalroaming.kt.com/product/voice/main.asp	http://m.globalroaming.kt.com/product/voice/main.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
140	ktcom_408	상품^로밍^로밍상품정보^편리한부가기능	http://globalroaming.kt.com/product/free/main.asp	http://m.globalroaming.kt.com/product/free/main.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
141	ktcom_409	상품^로밍^로밍이용꿀팁^요금절약꿀팁	https://globalroaming.kt.com/info/all3.asp	https://m.globalroaming.kt.com/info/all3.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
145	\N	상품^로밍^한눈에보기^공지사항	https://globalroaming.kt.com/news/list.asp	https://m.globalroaming.kt.com/news/list.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
146	ktcom_415	상품^로밍상품정보^편리한부가기능^데이터로밍안심차단	https://globalroaming.kt.com/product/free/dr10block.asp	https://m.globalroaming.kt.com/product/free/dr10block.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
147	ktcom_416	상품^로밍상품정보^편리한부가기능^데이터로밍요금 알림	https://globalroaming.kt.com/product/free/padblock.asp	https://m.globalroaming.kt.com/product/free/padblock.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
148	ktcom_417	상품^로밍상품정보^편리한부가기능^데이터로밍차단	https://globalroaming.kt.com/product/free/drmblock.asp	https://m.globalroaming.kt.com/product/free/drmblock.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
150	ktcom_419	상품^로밍상품정보^편리한부가기능^로밍안내방송	https://globalroaming.kt.com/product/free/announcement.asp	https://m.globalroaming.kt.com/product/free/announcement.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
151	ktcom_420	상품^로밍상품정보^편리한부가기능^로밍요금 안내	https://globalroaming.kt.com/product/free/rfguidance.asp	https://m.globalroaming.kt.com/product/free/rfguidance.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
152	ktcom_421	상품^로밍상품정보^편리한부가기능^음성로밍안심차단	https://globalroaming.kt.com/product/free/vrrblock.asp	https://m.globalroaming.kt.com/product/free/vrrblock.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
153	ktcom_422	상품^로밍상품정보^편리한부가기능^음성로밍차단	https://globalroaming.kt.com/product/free/vrblock.asp	https://m.globalroaming.kt.com/product/free/vrblock.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
154	ktcom_423	상품^로밍상품정보^편리한부가기능^청소년로밍허용	https://globalroaming.kt.com/product/free/teen.asp	https://m.globalroaming.kt.com/product/free/teen.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
155	ktcom_424	상품^로밍상품정보^편리한부가기능^해외 도착알리미	https://globalroaming.kt.com/product/free/landing.asp	https://m.globalroaming.kt.com/product/free/landing.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
156	ktcom_436	상품^모바일^갤럭시브랜드관	https://shop.kt.com/display/olhsPlan.do?plnDispNo=2468	https://m.shop.kt.com/display/olhsPlan.do?plnDispNo=2468	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
157	ktcom_437	상품^모바일^듀얼번호eSIM	https://product.kt.com/wDic/productDetail.do?ItemCode=1545	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1545	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
158	ktcom_438	상품^모바일^링투유벨소리^로밍링투유	https://bellring.mobile.kt.com/web/roamingRing.do	https://m.bellring.mobile.kt.com/web/roamingRing.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
162	ktcom_482	상품^모바일^부가서비스	https://product.kt.com/wDic/index.do?CateCode=6003	https://m.product.kt.com/wDic/index.do?CateCode=6003	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
163	ktcom_442	상품^모바일^부가서비스^(링투유X매달1곡) 링투유 플러스	https://product.kt.com/wDic/productDetail.do?ItemCode=1039&CateCode=6003&filter_code=14&option_code=33&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1039&CateCode=6003&filter_code=14&option_code=33&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
164	ktcom_443	상품^모바일^부가서비스^(안심) 060발신차단서비스	https://product.kt.com/wDic/productDetail.do?ItemCode=686&CateCode=6003&filter_code=11&option_code=30&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=686&CateCode=6003&filter_code=11&option_code=30&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
165	ktcom_444	상품^모바일^부가서비스^(안심) 번호도용문자 차단서비스	https://product.kt.com/wDic/productDetail.do?ItemCode=1047&CateCode=6003&filter_code=11&option_code=30&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1047&CateCode=6003&filter_code=11&option_code=30&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
166	ktcom_445	상품^모바일^부가서비스^(안심) 스팸차단	https://product.kt.com/wDic/productDetail.do?ItemCode=479&CateCode=6003&filter_code=11&option_code=30&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=479&CateCode=6003&filter_code=11&option_code=30&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
167	ktcom_446	상품^모바일^부가서비스^(안심) 익명호수신거부	https://product.kt.com/wDic/productDetail.do?ItemCode=482&CateCode=6003&filter_code=11&option_code=30&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=482&CateCode=6003&filter_code=11&option_code=30&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
168	ktcom_447	상품^모바일^부가서비스^(안심) 정보제공사업자번호차단	https://product.kt.com/wDic/productDetail.do?ItemCode=478&CateCode=6003&filter_code=11&option_code=30&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=478&CateCode=6003&filter_code=11&option_code=30&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
169	ktcom_448	상품^모바일^부가서비스^(안심) 후후스팸알림	https://product.kt.com/wDic/productDetail.do?ItemCode=1075&CateCode=6003&filter_code=11&option_code=30&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1075&CateCode=6003&filter_code=11&option_code=30&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
170	ktcom_449	상품^모바일^부가서비스^050 개인 안심번호	https://product.kt.com/wDic/productDetail.do?ItemCode=1454&CateCode=6003&filter_code=14&option_code=33&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1454&CateCode=6003&filter_code=14&option_code=33&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
171	ktcom_450	상품^모바일^부가서비스^3G 데이터쉐어링	https://product.kt.com/wDic/productDetail.do?ItemCode=647&CateCode=6003&filter_code=8&option_code=27&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=647&CateCode=6003&filter_code=8&option_code=27&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
194	ktcom_503	상품^모바일^부가서비스^링투유 캐치	https://product.kt.com/wDic/productDetail.do?ItemCode=116&CateCode=6003&filter_code=14&option_code=33&pageSize=30	https://m.product.kt.com/wDic/productDetail.do?ItemCode=116&CateCode=6003&filter_code=14&option_code=33&pageSize=30	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
161	ktcom_441	상품^모바일^링투유벨소리^오토체인지(오토링)	https://bellring.mobile.kt.com/web/autoRingMonth.do		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
172	ktcom_451	상품^모바일^부가서비스^5G 데이터쉐어링	https://product.kt.com/wDic/productDetail.do?ItemCode=1325&CateCode=6003&filter_code=8&option_code=27&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1325&CateCode=6003&filter_code=8&option_code=27&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
173	ktcom_452	상품^모바일^부가서비스^5G 데이터충전	https://product.kt.com/wDic/productDetail.do?ItemCode=1287&CateCode=6003&filter_code=8&option_code=27&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1287&CateCode=6003&filter_code=8&option_code=27&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
174	ktcom_483	상품^모바일^부가서비스^간편결제 매니저	https://product.kt.com/wDic/productDetail.do?ItemCode=1156&CateCode=6003&filter_code=12&option_code=31&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1156&CateCode=6003&filter_code=12&option_code=31&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
175	ktcom_484	상품^모바일^부가서비스^건강지키미	https://product.kt.com/wDic/productDetail.do?ItemCode=1594&CateCode=6003&filter_code=13&option_code=32&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1594&CateCode=6003&filter_code=13&option_code=32&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
176	ktcom_485	상품^모바일^부가서비스^국제전화발신제한	https://product.kt.com/wDic/productDetail.do?ItemCode=480&CateCode=6003&filter_code=14&option_code=33&pageSize=40	https://m.product.kt.com/wDic/productDetail.do?ItemCode=480&CateCode=6003&filter_code=14&option_code=33&pageSize=40	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
177	ktcom_486	상품^모바일^부가서비스^국제전화수신차단	https://product.kt.com/wDic/productDetail.do?ItemCode=971&CateCode=6003&filter_code=14&option_code=33&pageSize=40	https://m.product.kt.com/wDic/productDetail.do?ItemCode=971&CateCode=6003&filter_code=14&option_code=33&pageSize=40	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
178	ktcom_487	상품^모바일^부가서비스^내위치전송 서비스	https://product.kt.com/wDic/productDetail.do?ItemCode=463&CateCode=6003&filter_code=13&option_code=32&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=463&CateCode=6003&filter_code=13&option_code=32&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
179	ktcom_488	상품^모바일^부가서비스^넷플릭스	https://product.kt.com/wDic/productDetail.do?ItemCode=1582&CateCode=6003&filter_code=9&option_code=28&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1582&CateCode=6003&filter_code=9&option_code=28&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
180	ktcom_489	상품^모바일^부가서비스^더치트프리미엄	https://product.kt.com/wDic/productDetail.do?ItemCode=1591&CateCode=6003&filter_code=12&option_code=31&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1591&CateCode=6003&filter_code=12&option_code=31&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
181	ktcom_490	상품^모바일^부가서비스^데이터 전용 단말 통보 서비스	https://product.kt.com/wDic/productDetail.do?ItemCode=536&CateCode=6003&filter_code=13&option_code=32&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=536&CateCode=6003&filter_code=13&option_code=32&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
182	ktcom_491	상품^모바일^부가서비스^데이터플러스(3G)	https://product.kt.com/wDic/productDetail.do?ItemCode=642&CateCode=6003&filter_code=8&option_code=27&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=642&CateCode=6003&filter_code=8&option_code=27&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
183	ktcom_492	상품^모바일^부가서비스^데이터플러스(알)	https://product.kt.com/wDic/productDetail.do?ItemCode=645&CateCode=6003&filter_code=8&option_code=27&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=645&CateCode=6003&filter_code=8&option_code=27&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
184	ktcom_493	상품^모바일^부가서비스^듀얼번호 Lite	https://product.kt.com/wDic/productDetail.do?ItemCode=474&CateCode=6003&filter_code=14&option_code=33&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=474&CateCode=6003&filter_code=14&option_code=33&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
185	ktcom_494	상품^모바일^부가서비스^등기문자	https://product.kt.com/wDic/productDetail.do?ItemCode=459&CateCode=6003&filter_code=14&option_code=33&pageSize=50	https://m.product.kt.com/wDic/productDetail.do?ItemCode=459&CateCode=6003&filter_code=14&option_code=33&pageSize=50	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
186	ktcom_495	상품^모바일^부가서비스^등기문자거부	https://product.kt.com/wDic/productDetail.do?ItemCode=483&CateCode=6003&filter_code=14&option_code=33&pageSize=50	https://m.product.kt.com/wDic/productDetail.do?ItemCode=483&CateCode=6003&filter_code=14&option_code=33&pageSize=50	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
187	ktcom_496	상품^모바일^부가서비스^디즈니+	https://product.kt.com/wDic/productDetail.do?ItemCode=1583&CateCode=6003&filter_code=9&option_code=28&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1583&CateCode=6003&filter_code=9&option_code=28&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
188	ktcom_497	상품^모바일^부가서비스^디즈니플러스+스타벅스	https://product.kt.com/wDic/productDetail.do?ItemCode=1610&CateCode=6003&filter_code=9&option_code=28&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1610&CateCode=6003&filter_code=9&option_code=28&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
189	ktcom_498	상품^모바일^부가서비스^로그인 플러스	https://product.kt.com/wDic/productDetail.do?ItemCode=1157&CateCode=6003&filter_code=12&option_code=31&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1157&CateCode=6003&filter_code=12&option_code=31&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
190	ktcom_499	상품^모바일^부가서비스^리얼지니팩	https://product.kt.com/wDic/productDetail.do?ItemCode=1282&CateCode=6003&filter_code=9&option_code=28&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1282&CateCode=6003&filter_code=9&option_code=28&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
191	ktcom_500	상품^모바일^부가서비스^링투유	https://product.kt.com/wDic/productDetail.do?ItemCode=62&CateCode=6003&filter_code=14&option_code=33&pageSize=30	https://m.product.kt.com/wDic/productDetail.do?ItemCode=62&CateCode=6003&filter_code=14&option_code=33&pageSize=30	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
192	ktcom_501	상품^모바일^부가서비스^링투유 오토체인지	https://product.kt.com/wDic/productDetail.do?ItemCode=72&CateCode=6003&filter_code=14&option_code=33&pageSize=30	https://m.product.kt.com/wDic/productDetail.do?ItemCode=72&CateCode=6003&filter_code=14&option_code=33&pageSize=30	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
193	ktcom_502	상품^모바일^부가서비스^링투유 인사말 (청각장애 안내)	https://product.kt.com/wDic/productDetail.do?ItemCode=1357&CateCode=6003&filter_code=14&option_code=33&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1357&CateCode=6003&filter_code=14&option_code=33&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
195	ktcom_504	상품^모바일^부가서비스^마인드케어	https://product.kt.com/wDic/productDetail.do?ItemCode=1605&CateCode=6003&filter_code=13&option_code=32&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1605&CateCode=6003&filter_code=13&option_code=32&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
196	ktcom_505	상품^모바일^부가서비스^모바일 교통카드	https://product.kt.com/wDic/productDetail.do?ItemCode=692&CateCode=6003&filter_code=12&option_code=31&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=692&CateCode=6003&filter_code=12&option_code=31&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
197	ktcom_506	상품^모바일^부가서비스^모바일 안전결제	https://product.kt.com/wDic/productDetail.do?ItemCode=1048&CateCode=6003&filter_code=11&option_code=30&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1048&CateCode=6003&filter_code=11&option_code=30&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
198	ktcom_507	상품^모바일^부가서비스^모바일(USIM) 신용카드	https://product.kt.com/wDic/productDetail.do?ItemCode=690&CateCode=6003&filter_code=12&option_code=31&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=690&CateCode=6003&filter_code=12&option_code=31&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
199	ktcom_508	상품^모바일^부가서비스^모아진	https://product.kt.com/wDic/productDetail.do?ItemCode=1615&CateCode=6003&filter_code=9&option_code=28&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1615&CateCode=6003&filter_code=9&option_code=28&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
200	ktcom_509	상품^모바일^부가서비스^무선데이터 차단서비스	https://product.kt.com/wDic/productDetail.do?ItemCode=486&CateCode=6003&filter_code=8&option_code=27&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=486&CateCode=6003&filter_code=8&option_code=27&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
201	ktcom_510	상품^모바일^부가서비스^문자이월	https://product.kt.com/wDic/productDetail.do?ItemCode=445&CateCode=6003&filter_code=14&option_code=33&pageSize=60	https://m.product.kt.com/wDic/productDetail.do?ItemCode=445&CateCode=6003&filter_code=14&option_code=33&pageSize=60	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
202	ktcom_511	상품^모바일^부가서비스^문자이월100	https://product.kt.com/wDic/productDetail.do?ItemCode=471&CateCode=6003&filter_code=14&option_code=33&pageSize=60	https://m.product.kt.com/wDic/productDetail.do?ItemCode=471&CateCode=6003&filter_code=14&option_code=33&pageSize=60	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
203	ktcom_512	상품^모바일^부가서비스^문자이월1000	https://product.kt.com/wDic/productDetail.do?ItemCode=447&CateCode=6003&filter_code=14&option_code=33&pageSize=60	https://m.product.kt.com/wDic/productDetail.do?ItemCode=447&CateCode=6003&filter_code=14&option_code=33&pageSize=60	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
204	ktcom_513	상품^모바일^부가서비스^밀리의 서재	https://product.kt.com/wDic/productDetail.do?ItemCode=1585&CateCode=6003&filter_code=9&option_code=28&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1585&CateCode=6003&filter_code=9&option_code=28&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
205	ktcom_514	상품^모바일^부가서비스^밀리의 서재+E북 리더기	https://product.kt.com/wDic/productDetail.do?ItemCode=1590&CateCode=6003&filter_code=9&option_code=28&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1590&CateCode=6003&filter_code=9&option_code=28&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
206	ktcom_515	상품^모바일^부가서비스^발신번호표시제한	https://product.kt.com/wDic/productDetail.do?ItemCode=481&CateCode=6003&filter_code=14&option_code=33&pageSize=50	https://m.product.kt.com/wDic/productDetail.do?ItemCode=481&CateCode=6003&filter_code=14&option_code=33&pageSize=50	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
207	ktcom_516	상품^모바일^부가서비스^번호변경안내(모바일)	https://product.kt.com/wDic/productDetail.do?ItemCode=512&CateCode=6003&filter_code=14&option_code=33&pageSize=50	https://m.product.kt.com/wDic/productDetail.do?ItemCode=512&CateCode=6003&filter_code=14&option_code=33&pageSize=50	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
208	ktcom_517	상품^모바일^부가서비스^벨링Big5 벨링Big5플러스	https://product.kt.com/wDic/productDetail.do?ItemCode=105&CateCode=6003&filter_code=14&option_code=33&pageSize=30	https://m.product.kt.com/wDic/productDetail.do?ItemCode=105&CateCode=6003&filter_code=14&option_code=33&pageSize=30	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
209	ktcom_518	상품^모바일^부가서비스^벨소리	https://product.kt.com/wDic/productDetail.do?ItemCode=186&CateCode=6003&filter_code=14&option_code=33&pageSize=30	https://m.product.kt.com/wDic/productDetail.do?ItemCode=186&CateCode=6003&filter_code=14&option_code=33&pageSize=30	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
210	ktcom_519	상품^모바일^부가서비스^불법TM 수신차단	https://product.kt.com/wDic/productDetail.do?ItemCode=957&CateCode=6003&filter_code=11&option_code=30&pageSize=30	https://m.product.kt.com/wDic/productDetail.do?ItemCode=957&CateCode=6003&filter_code=11&option_code=30&pageSize=30	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
211	ktcom_520	상품^모바일^부가서비스^블라이스 셀렉트	https://product.kt.com/wDic/productDetail.do?ItemCode=1586&CateCode=6003&filter_code=9&option_code=28&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1586&CateCode=6003&filter_code=9&option_code=28&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
212	ktcom_521	상품^모바일^부가서비스^블랙박스분석	https://product.kt.com/wDic/productDetail.do?ItemCode=1574&CateCode=6003&filter_code=13&option_code=32&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1574&CateCode=6003&filter_code=13&option_code=32&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
213	ktcom_522	상품^모바일^부가서비스^생활정보	https://product.kt.com/wDic/productDetail.do?ItemCode=1613&CateCode=6003&filter_code=13&option_code=32&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1613&CateCode=6003&filter_code=13&option_code=32&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
214	ktcom_523	상품^모바일^부가서비스^세이프가드	https://product.kt.com/wDic/productDetail.do?ItemCode=1587&CateCode=6003&filter_code=11&option_code=30&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1587&CateCode=6003&filter_code=11&option_code=30&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
215	ktcom_524	상품^모바일^부가서비스^세이프캐시	https://product.kt.com/wDic/productDetail.do?ItemCode=1592&CateCode=6003&filter_code=12&option_code=31&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1592&CateCode=6003&filter_code=12&option_code=31&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
216	ktcom_525	상품^모바일^부가서비스^쇼미	https://product.kt.com/wDic/productDetail.do?ItemCode=558&CateCode=6003&filter_code=14&option_code=33&pageSize=30	https://m.product.kt.com/wDic/productDetail.do?ItemCode=558&CateCode=6003&filter_code=14&option_code=33&pageSize=30	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
217	ktcom_526	상품^모바일^부가서비스^쇼핑로그인	https://product.kt.com/wDic/productDetail.do?ItemCode=1608&CateCode=6003&filter_code=13&option_code=32&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1608&CateCode=6003&filter_code=13&option_code=32&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
218	ktcom_527	상품^모바일^부가서비스^스마트공인인증	https://product.kt.com/wDic/productDetail.do?ItemCode=973&CateCode=6003&filter_code=12&option_code=31&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=973&CateCode=6003&filter_code=12&option_code=31&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
219	ktcom_528	상품^모바일^부가서비스^스마트안티피싱	https://product.kt.com/wDic/productDetail.do?ItemCode=1628&CateCode=6003&filter_code=11&option_code=30&pageSize=30	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1628&CateCode=6003&filter_code=11&option_code=30&pageSize=30	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
220	ktcom_529	상품^모바일^부가서비스^신용지키미	https://product.kt.com/wDic/productDetail.do?ItemCode=1593&CateCode=6003&filter_code=12&option_code=31&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1593&CateCode=6003&filter_code=12&option_code=31&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
221	ktcom_530	상품^모바일^부가서비스^아이서치 서비스 [문자 위치 알림]	https://product.kt.com/wDic/productDetail.do?ItemCode=569&CateCode=6003&filter_code=11&option_code=30&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=569&CateCode=6003&filter_code=11&option_code=30&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
222	ktcom_531	상품^모바일^부가서비스^안심체인지 New 갤럭시 AI 클럽	https://product.kt.com/wDic/productDetail.do?ItemCode=1627&CateCode=6003&filter_code=10&option_code=29&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1627&CateCode=6003&filter_code=10&option_code=29&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
223	ktcom_532	상품^모바일^부가서비스^알파스탁	https://product.kt.com/wDic/productDetail.do?ItemCode=1595&CateCode=6003&filter_code=12&option_code=31&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1595&CateCode=6003&filter_code=12&option_code=31&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
224	ktcom_533	상품^모바일^부가서비스^여가생활안심보호	https://product.kt.com/wDic/productDetail.do?ItemCode=1631&CateCode=6003&filter_code=11&option_code=30&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1631&CateCode=6003&filter_code=11&option_code=30&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
225	ktcom_534	상품^모바일^부가서비스^영문이용요금알리미	https://product.kt.com/wDic/productDetail.do?ItemCode=514&CateCode=6003&filter_code=13&option_code=32&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=514&CateCode=6003&filter_code=13&option_code=32&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
226	ktcom_535	상품^모바일^부가서비스^오토링	https://product.kt.com/wDic/productDetail.do?ItemCode=91&CateCode=6003&filter_code=14&option_code=33&pageSize=30	https://m.product.kt.com/wDic/productDetail.do?ItemCode=91&CateCode=6003&filter_code=14&option_code=33&pageSize=30	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
227	ktcom_536	상품^모바일^부가서비스^요금납부알림서비스	https://product.kt.com/wDic/productDetail.do?ItemCode=535&CateCode=6003&filter_code=13&option_code=32&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=535&CateCode=6003&filter_code=13&option_code=32&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
228	ktcom_537	상품^모바일^부가서비스^우리펫상조	https://product.kt.com/wDic/productDetail.do?ItemCode=1616&CateCode=6003&filter_code=13&option_code=32&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1616&CateCode=6003&filter_code=13&option_code=32&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
229	ktcom_538	상품^모바일^부가서비스^원격제어	https://product.kt.com/wDic/productDetail.do?ItemCode=433&CateCode=6003&filter_code=14&option_code=33&pageSize=40	https://m.product.kt.com/wDic/productDetail.do?ItemCode=433&CateCode=6003&filter_code=14&option_code=33&pageSize=40	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
230	ktcom_539	상품^모바일^부가서비스^원넘버 서비스	https://product.kt.com/wDic/productDetail.do?ItemCode=1143&CateCode=6003&filter_code=14&option_code=33&pageSize=40	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1143&CateCode=6003&filter_code=14&option_code=33&pageSize=40	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
231	ktcom_540	상품^모바일^부가서비스^위치정보자기제어	https://product.kt.com/wDic/productDetail.do?ItemCode=1209&CateCode=6003&filter_code=13&option_code=32&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1209&CateCode=6003&filter_code=13&option_code=32&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
232	ktcom_541	상품^모바일^부가서비스^유심보호서비스	https://product.kt.com/wDic/productDetail.do?ItemCode=1489&CateCode=6003&filter_code=11&option_code=30&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1489&CateCode=6003&filter_code=11&option_code=30&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
233	ktcom_542	상품^모바일^부가서비스^유튜브 프리미엄	https://product.kt.com/wDic/productDetail.do?ItemCode=1581&CateCode=6003&filter_code=9&option_code=28&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1581&CateCode=6003&filter_code=9&option_code=28&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
234	ktcom_543	상품^모바일^부가서비스^유튜브 프리미엄+롯데시네마	https://product.kt.com/wDic/productDetail.do?ItemCode=1614&CateCode=6003&filter_code=9&option_code=28&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1614&CateCode=6003&filter_code=9&option_code=28&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
235	ktcom_544	상품^모바일^부가서비스^유튜브 프리미엄+스타벅스	https://product.kt.com/wDic/productDetail.do?ItemCode=1599&CateCode=6003&filter_code=9&option_code=28&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1599&CateCode=6003&filter_code=9&option_code=28&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
236	ktcom_545	상품^모바일^부가서비스^이용요금알리미	https://product.kt.com/wDic/productDetail.do?ItemCode=516&CateCode=6003&filter_code=13&option_code=32&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=516&CateCode=6003&filter_code=13&option_code=32&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
237	ktcom_546	상품^모바일^부가서비스^자녀정보이용료알리미	https://product.kt.com/wDic/productDetail.do?ItemCode=515&CateCode=6003&filter_code=11&option_code=30&pageSize=30	https://m.product.kt.com/wDic/productDetail.do?ItemCode=515&CateCode=6003&filter_code=11&option_code=30&pageSize=30	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
238	ktcom_547	상품^모바일^부가서비스^자동연결	https://product.kt.com/wDic/productDetail.do?ItemCode=421&CateCode=6003&filter_code=14&option_code=33&pageSize=40	https://m.product.kt.com/wDic/productDetail.do?ItemCode=421&CateCode=6003&filter_code=14&option_code=33&pageSize=40	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
239	ktcom_548	상품^모바일^부가서비스^전국민할인요금	https://product.kt.com/wDic/productDetail.do?ItemCode=212&CateCode=6003&filter_code=14&option_code=33&pageSize=50	https://m.product.kt.com/wDic/productDetail.do?ItemCode=212&CateCode=6003&filter_code=14&option_code=33&pageSize=50	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
240	ktcom_549	상품^모바일^부가서비스^전화번호 안심로그인	https://product.kt.com/wDic/productDetail.do?ItemCode=1165&CateCode=6003&filter_code=11&option_code=30&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1165&CateCode=6003&filter_code=11&option_code=30&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
241	ktcom_550	상품^모바일^부가서비스^정보보호 알림이	https://product.kt.com/wDic/productDetail.do?ItemCode=485&CateCode=6003&filter_code=11&option_code=30&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=485&CateCode=6003&filter_code=11&option_code=30&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
242	ktcom_551	상품^모바일^부가서비스^정보유출안심케어	https://product.kt.com/wDic/productDetail.do?ItemCode=1607&CateCode=6003&filter_code=11&option_code=30&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1607&CateCode=6003&filter_code=11&option_code=30&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
243	ktcom_552	상품^모바일^부가서비스^주식투자노트	https://product.kt.com/wDic/productDetail.do?ItemCode=1158&CateCode=6003&filter_code=12&option_code=31&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1158&CateCode=6003&filter_code=12&option_code=31&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
244	ktcom_553	상품^모바일^부가서비스^지니 스마트 음악감상	https://product.kt.com/wDic/productDetail.do?ItemCode=1584&CateCode=6003&filter_code=9&option_code=28&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1584&CateCode=6003&filter_code=9&option_code=28&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
245	ktcom_554	상품^모바일^부가서비스^지니팩	https://product.kt.com/wDic/productDetail.do?ItemCode=962&CateCode=6003&filter_code=9&option_code=28&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=962&CateCode=6003&filter_code=9&option_code=28&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
246	ktcom_555	상품^모바일^부가서비스^착신거절	https://product.kt.com/wDic/productDetail.do?ItemCode=417&CateCode=6003&filter_code=14&option_code=33&pageSize=50	https://m.product.kt.com/wDic/productDetail.do?ItemCode=417&CateCode=6003&filter_code=14&option_code=33&pageSize=50	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
247	ktcom_556	상품^모바일^부가서비스^착신전환(모바일통화만)	https://product.kt.com/wDic/productDetail.do?ItemCode=411&CateCode=6003&filter_code=14&option_code=33&pageSize=40	https://m.product.kt.com/wDic/productDetail.do?ItemCode=411&CateCode=6003&filter_code=14&option_code=33&pageSize=40	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
248	ktcom_557	상품^모바일^부가서비스^착신전환(모바일통화와문자)	https://product.kt.com/wDic/productDetail.do?ItemCode=410&CateCode=6003&filter_code=14&option_code=33&pageSize=40	https://m.product.kt.com/wDic/productDetail.do?ItemCode=410&CateCode=6003&filter_code=14&option_code=33&pageSize=40	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
249	ktcom_558	상품^모바일^부가서비스^채팅플러스	https://product.kt.com/wDic/productDetail.do?ItemCode=1274&CateCode=6003&filter_code=14&option_code=33&pageSize=50	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1274&CateCode=6003&filter_code=14&option_code=33&pageSize=50	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
250	ktcom_559	상품^모바일^부가서비스^청소년 정보료 상한 서비스	https://product.kt.com/wDic/productDetail.do?ItemCode=1148&CateCode=6003&filter_code=11&option_code=30&pageSize=30	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1148&CateCode=6003&filter_code=11&option_code=30&pageSize=30	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
251	ktcom_560	상품^모바일^부가서비스^캐치콜	https://product.kt.com/wDic/productDetail.do?ItemCode=661&CateCode=6003&filter_code=14&option_code=33&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=661&CateCode=6003&filter_code=14&option_code=33&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
252	ktcom_561	상품^모바일^부가서비스^캐치콜 플러스	https://product.kt.com/wDic/productDetail.do?ItemCode=1034&CateCode=6003&filter_code=14&option_code=33&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1034&CateCode=6003&filter_code=14&option_code=33&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
253	ktcom_562	상품^모바일^부가서비스^캐치콜X링투유(기본팩)	https://product.kt.com/wDic/productDetail.do?ItemCode=576&CateCode=6003&filter_code=14&option_code=33&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=576&CateCode=6003&filter_code=14&option_code=33&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
254	ktcom_563	상품^모바일^부가서비스^캐치콜X링투유X050개인안심	https://product.kt.com/wDic/productDetail.do?ItemCode=1456&CateCode=6003&filter_code=14&option_code=33&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1456&CateCode=6003&filter_code=14&option_code=33&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
255	ktcom_564	상품^모바일^부가서비스^캐치콜X링투유X매달1곡(기본팩 플러스)	https://product.kt.com/wDic/productDetail.do?ItemCode=1001&CateCode=6003&filter_code=14&option_code=33&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1001&CateCode=6003&filter_code=14&option_code=33&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
256	ktcom_565	상품^모바일^부가서비스^콴다	https://product.kt.com/wDic/productDetail.do?ItemCode=1629&CateCode=6003&filter_code=13&option_code=32&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1629&CateCode=6003&filter_code=13&option_code=32&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
257	ktcom_566	상품^모바일^부가서비스^퀀트업-미국주식	https://product.kt.com/wDic/productDetail.do?ItemCode=1575&CateCode=6003&filter_code=12&option_code=31&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1575&CateCode=6003&filter_code=12&option_code=31&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
258	ktcom_567	상품^모바일^부가서비스^통합사서함	https://product.kt.com/wDic/productDetail.do?ItemCode=428&CateCode=6003&filter_code=14&option_code=33&pageSize=50	https://m.product.kt.com/wDic/productDetail.do?ItemCode=428&CateCode=6003&filter_code=14&option_code=33&pageSize=50	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
259	ktcom_568	상품^모바일^부가서비스^통화가능알리미	https://product.kt.com/wDic/productDetail.do?ItemCode=659&CateCode=6003&filter_code=14&option_code=33&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=659&CateCode=6003&filter_code=14&option_code=33&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
260	ktcom_569	상품^모바일^부가서비스^통화가능알리미거부	https://product.kt.com/wDic/productDetail.do?ItemCode=416&CateCode=6003&filter_code=14&option_code=33&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=416&CateCode=6003&filter_code=14&option_code=33&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
261	ktcom_570	상품^모바일^부가서비스^통화요구알리미	https://product.kt.com/wDic/productDetail.do?ItemCode=660&CateCode=6003&filter_code=14&option_code=33&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=660&CateCode=6003&filter_code=14&option_code=33&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
262	ktcom_571	상품^모바일^부가서비스^통화중대기(모바일)	https://product.kt.com/wDic/productDetail.do?ItemCode=432&CateCode=6003&filter_code=14&option_code=33&pageSize=50	https://m.product.kt.com/wDic/productDetail.do?ItemCode=432&CateCode=6003&filter_code=14&option_code=33&pageSize=50	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
263	ktcom_572	상품^모바일^부가서비스^투데이	https://product.kt.com/wDic/productDetail.do?ItemCode=1596&CateCode=6003&filter_code=13&option_code=32&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1596&CateCode=6003&filter_code=13&option_code=32&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
264	ktcom_573	상품^모바일^부가서비스^투폰서비스(3G)	https://product.kt.com/wDic/productDetail.do?ItemCode=475&CateCode=6003&filter_code=14&option_code=33&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=475&CateCode=6003&filter_code=14&option_code=33&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
265	ktcom_574	상품^모바일^부가서비스^특정번호 수신차단	https://product.kt.com/wDic/productDetail.do?ItemCode=477&CateCode=6003&filter_code=14&option_code=33&pageSize=40	https://m.product.kt.com/wDic/productDetail.do?ItemCode=477&CateCode=6003&filter_code=14&option_code=33&pageSize=40	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
266	ktcom_575	상품^모바일^부가서비스^티빙	https://product.kt.com/wDic/productDetail.do?ItemCode=1580&CateCode=6003&filter_code=9&option_code=28&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1580&CateCode=6003&filter_code=9&option_code=28&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
267	ktcom_576	상품^모바일^부가서비스^티빙 라이트베이직	https://product.kt.com/wDic/productDetail.do?ItemCode=1547&CateCode=6003&filter_code=9&option_code=28&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1547&CateCode=6003&filter_code=9&option_code=28&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
268	ktcom_577	상품^모바일^부가서비스^티빙+스타벅스	https://product.kt.com/wDic/productDetail.do?ItemCode=1579&CateCode=6003&filter_code=9&option_code=28&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1579&CateCode=6003&filter_code=9&option_code=28&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
269	ktcom_578	상품^모바일^부가서비스^펫케어	https://product.kt.com/wDic/productDetail.do?ItemCode=1597&CateCode=6003&filter_code=13&option_code=32&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1597&CateCode=6003&filter_code=13&option_code=32&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
270	ktcom_579	상품^모바일^부가서비스^프리미엄 후후	https://product.kt.com/wDic/productDetail.do?ItemCode=1563&CateCode=6003&filter_code=11&option_code=30&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1563&CateCode=6003&filter_code=11&option_code=30&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
271	ktcom_580	상품^모바일^부가서비스^필수팩 L	https://product.kt.com/wDic/productDetail.do?ItemCode=1544&CateCode=6003&filter_code=14&option_code=33&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1544&CateCode=6003&filter_code=14&option_code=33&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
272	ktcom_581	상품^모바일^부가서비스^필수팩 M	https://product.kt.com/wDic/productDetail.do?ItemCode=1600&CateCode=6003&filter_code=14&option_code=33&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1600&CateCode=6003&filter_code=14&option_code=33&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
273	ktcom_582	상품^모바일^부가서비스^필수팩 M0	https://product.kt.com/wDic/productDetail.do?ItemCode=1543&CateCode=6003&filter_code=14&option_code=33&pageSize=30	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1543&CateCode=6003&filter_code=14&option_code=33&pageSize=30	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
274	ktcom_583	상품^모바일^부가서비스^필수팩 S	https://product.kt.com/wDic/productDetail.do?ItemCode=1603&CateCode=6003&filter_code=14&option_code=33&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1603&CateCode=6003&filter_code=14&option_code=33&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
275	ktcom_584	상품^모바일^부가서비스^필수팩 S0	https://product.kt.com/wDic/productDetail.do?ItemCode=1542&CateCode=6003&filter_code=14&option_code=33&pageSize=30	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1542&CateCode=6003&filter_code=14&option_code=33&pageSize=30	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
276	ktcom_585	상품^모바일^부가서비스^한줄인사말	https://product.kt.com/wDic/productDetail.do?ItemCode=946&CateCode=6003&filter_code=14&option_code=33&pageSize=30	https://m.product.kt.com/wDic/productDetail.do?ItemCode=946&CateCode=6003&filter_code=14&option_code=33&pageSize=30	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
277	ktcom_586	상품^모바일^부가서비스^해외문자전송	https://product.kt.com/wDic/productDetail.do?ItemCode=462&CateCode=6003&filter_code=14&option_code=33&pageSize=60	https://m.product.kt.com/wDic/productDetail.do?ItemCode=462&CateCode=6003&filter_code=14&option_code=33&pageSize=60	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
278	ktcom_587	상품^모바일^부가서비스^해외주식정보	https://product.kt.com/wDic/productDetail.do?ItemCode=1598&CateCode=6003&filter_code=12&option_code=31&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1598&CateCode=6003&filter_code=12&option_code=31&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
279	ktcom_588	상품^모바일^부가서비스^호보류	https://product.kt.com/wDic/productDetail.do?ItemCode=418&CateCode=6003&filter_code=14&option_code=33&pageSize=50	https://m.product.kt.com/wDic/productDetail.do?ItemCode=418&CateCode=6003&filter_code=14&option_code=33&pageSize=50	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
280	ktcom_589	상품^모바일^부가서비스^휴대폰 결제	https://product.kt.com/wDic/productDetail.do?ItemCode=967&CateCode=6003&filter_code=12&option_code=31&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=967&CateCode=6003&filter_code=12&option_code=31&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
281	ktcom_590	상품^모바일^부가서비스^휴대폰 공인인증서	https://product.kt.com/wDic/productDetail.do?ItemCode=500&CateCode=6003&filter_code=12&option_code=31&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=500&CateCode=6003&filter_code=12&option_code=31&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
282	ktcom_591	상품^모바일^부가서비스^휴대폰 안심결제	https://product.kt.com/wDic/productDetail.do?ItemCode=968&CateCode=6003&filter_code=11&option_code=30&pageSize=30	https://m.product.kt.com/wDic/productDetail.do?ItemCode=968&CateCode=6003&filter_code=11&option_code=30&pageSize=30	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
406	ktcom_678	상품^소상공인^소상공인부가상품	https://product.kt.com/wDic/soho/index.do?CateCode=7003		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
283	ktcom_592	상품^모바일^부가서비스^휴대폰결제 안심통보 서비스	https://product.kt.com/wDic/productDetail.do?ItemCode=1264&CateCode=6003&filter_code=13&option_code=32&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1264&CateCode=6003&filter_code=13&option_code=32&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
284	ktcom_593	상품^모바일^부가서비스^휴대폰번호 보호서비스	https://product.kt.com/wDic/productDetail.do?ItemCode=1042&CateCode=6003&filter_code=11&option_code=30&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1042&CateCode=6003&filter_code=11&option_code=30&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
285	ktcom_594	상품^모바일^부가서비스^휴대폰쿠폰지갑	https://product.kt.com/wDic/productDetail.do?ItemCode=1606&CateCode=6003&filter_code=13&option_code=32&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1606&CateCode=6003&filter_code=13&option_code=32&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
286	ktcom_453	상품^모바일^부가서비스^ARS안심인증	https://product.kt.com/wDic/productDetail.do?ItemCode=996&CateCode=6003&filter_code=11&option_code=30&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=996&CateCode=6003&filter_code=11&option_code=30&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
287	ktcom_454	상품^모바일^부가서비스^Egg 데이터플러스	https://product.kt.com/wDic/productDetail.do?ItemCode=1054&CateCode=6003&filter_code=8&option_code=27&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1054&CateCode=6003&filter_code=8&option_code=27&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
288	ktcom_455	상품^모바일^부가서비스^HD 보이스 (VoLTE)	https://product.kt.com/wDic/productDetail.do?ItemCode=785&CateCode=6003&filter_code=14&option_code=33&pageSize=40	https://m.product.kt.com/wDic/productDetail.do?ItemCode=785&CateCode=6003&filter_code=14&option_code=33&pageSize=40	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
289	ktcom_456	상품^모바일^부가서비스^HD 영상통화	https://product.kt.com/wDic/productDetail.do?ItemCode=786&CateCode=6003&filter_code=14&option_code=33&pageSize=40	https://m.product.kt.com/wDic/productDetail.do?ItemCode=786&CateCode=6003&filter_code=14&option_code=33&pageSize=40	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
290	ktcom_457	상품^모바일^부가서비스^KT 365 폰케어	https://product.kt.com/wDic/productDetail.do?ItemCode=1604&CateCode=6003&filter_code=10&option_code=29&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1604&CateCode=6003&filter_code=10&option_code=29&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
291	ktcom_459	상품^모바일^부가서비스^KT 갤럭시 프리미엄 Y 에디션 구독 서비스	https://product.kt.com/wDic/productDetail.do?ItemCode=1588&CateCode=6003&filter_code=10&option_code=29&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1588&CateCode=6003&filter_code=10&option_code=29&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
292	ktcom_458	상품^모바일^부가서비스^KT 갤럭시 S23 FE 구독 서비스	https://product.kt.com/wDic/productDetail.do?ItemCode=1572&CateCode=6003&filter_code=10&option_code=29&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1572&CateCode=6003&filter_code=10&option_code=29&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
293	ktcom_460	상품^모바일^부가서비스^KT 안심 폰교체(안심 체인지)	https://product.kt.com/wDic/productDetail.do?ItemCode=1573&CateCode=6003&filter_code=10&option_code=29&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1573&CateCode=6003&filter_code=10&option_code=29&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
294	ktcom_461	상품^모바일^부가서비스^KT 안심박스	https://product.kt.com/wDic/productDetail.do?ItemCode=1426&CateCode=6003&filter_code=11&option_code=30&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1426&CateCode=6003&filter_code=11&option_code=30&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
295	ktcom_462	상품^모바일^부가서비스^KT 안심박스 프리	https://product.kt.com/wDic/productDetail.do?ItemCode=1448&CateCode=6003&filter_code=11&option_code=30&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1448&CateCode=6003&filter_code=11&option_code=30&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
296	ktcom_463	상품^모바일^부가서비스^KT 인증서 관리	https://product.kt.com/wDic/productDetail.do?ItemCode=1170&CateCode=6003&filter_code=12&option_code=31&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1170&CateCode=6003&filter_code=12&option_code=31&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
297	ktcom_464	상품^모바일^부가서비스^KT 콘텐츠박스	https://product.kt.com/wDic/productDetail.do?ItemCode=1032&CateCode=6003&filter_code=13&option_code=32&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1032&CateCode=6003&filter_code=13&option_code=32&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
298	ktcom_465	상품^모바일^부가서비스^KT 투폰	https://product.kt.com/wDic/productDetail.do?ItemCode=1069&CateCode=6003&filter_code=14&option_code=33&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1069&CateCode=6003&filter_code=14&option_code=33&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
299	ktcom_466	상품^모바일^부가서비스^KT 패밀리 50% 할인 요금	https://product.kt.com/wDic/productDetail.do?ItemCode=440&CateCode=6003&filter_code=13&option_code=32&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=440&CateCode=6003&filter_code=13&option_code=32&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
300	ktcom_468	상품^모바일^부가서비스^LTE 데이터쉐어링	https://product.kt.com/wDic/productDetail.do?ItemCode=803&CateCode=6003&filter_code=8&option_code=27&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=803&CateCode=6003&filter_code=8&option_code=27&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
301	ktcom_469	상품^모바일^부가서비스^LTE 데이터충전	https://product.kt.com/wDic/productDetail.do?ItemCode=1068&CateCode=6003&filter_code=8&option_code=27&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1068&CateCode=6003&filter_code=8&option_code=27&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
302	ktcom_470	상품^모바일^부가서비스^LTE 데이터쿠폰	https://product.kt.com/wDic/productDetail.do?ItemCode=984&CateCode=6003&filter_code=8&option_code=27&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=984&CateCode=6003&filter_code=8&option_code=27&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
303	ktcom_467	상품^모바일^부가서비스^LTE SIMple충전데이터플러스	https://product.kt.com/wDic/productDetail.do?ItemCode=992&CateCode=6003&filter_code=8&option_code=27&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=992&CateCode=6003&filter_code=8&option_code=27&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
304	ktcom_471	상품^모바일^부가서비스^LTE안심QoS옵션	https://product.kt.com/wDic/productDetail.do?ItemCode=749&CateCode=6003&filter_code=8&option_code=27&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=749&CateCode=6003&filter_code=8&option_code=27&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
305	ktcom_472	상품^모바일^부가서비스^My time plan(LTE)	https://product.kt.com/wDic/productDetail.do?ItemCode=1041&CateCode=6003&filter_code=8&option_code=27&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1041&CateCode=6003&filter_code=8&option_code=27&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
306	ktcom_473	상품^모바일^부가서비스^MyOTP(마이오티피)	https://product.kt.com/wDic/productDetail.do?ItemCode=1166&CateCode=6003&filter_code=11&option_code=30&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1166&CateCode=6003&filter_code=11&option_code=30&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
307	ktcom_474	상품^모바일^부가서비스^SIMple 충전 데이터플러스	https://product.kt.com/wDic/productDetail.do?ItemCode=784&CateCode=6003&filter_code=8&option_code=27&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=784&CateCode=6003&filter_code=8&option_code=27&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
308	ktcom_475	상품^모바일^부가서비스^Style문자	https://product.kt.com/wDic/productDetail.do?ItemCode=235&CateCode=6003&filter_code=14&option_code=33&pageSize=60	https://m.product.kt.com/wDic/productDetail.do?ItemCode=235&CateCode=6003&filter_code=14&option_code=33&pageSize=60	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
309	ktcom_476	상품^모바일^부가서비스^Style안심데이터	https://product.kt.com/wDic/productDetail.do?ItemCode=236&CateCode=6003&filter_code=8&option_code=27&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=236&CateCode=6003&filter_code=8&option_code=27&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
310	ktcom_477	상품^모바일^부가서비스^USIM 스마트인증	https://product.kt.com/wDic/productDetail.do?ItemCode=1030&CateCode=6003&filter_code=12&option_code=31&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1030&CateCode=6003&filter_code=12&option_code=31&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
311	ktcom_478	상품^모바일^부가서비스^V컬러링	https://product.kt.com/wDic/productDetail.do?ItemCode=1423&CateCode=6003&filter_code=14&option_code=33&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1423&CateCode=6003&filter_code=14&option_code=33&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
312	ktcom_479	상품^모바일^부가서비스^V컬러링X캐치콜	https://product.kt.com/wDic/productDetail.do?ItemCode=1424&CateCode=6003&filter_code=14&option_code=33&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1424&CateCode=6003&filter_code=14&option_code=33&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
313	ktcom_480	상품^모바일^부가서비스^V컬러링X캐치콜X050개인안심	https://product.kt.com/wDic/productDetail.do?ItemCode=1455&CateCode=6003&filter_code=14&option_code=33&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1455&CateCode=6003&filter_code=14&option_code=33&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
314	ktcom_481	상품^모바일^부가서비스^Y군인 혜택	https://product.kt.com/wDic/productDetail.do?ItemCode=1476&CateCode=6003&filter_code=13&option_code=32&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1476&CateCode=6003&filter_code=13&option_code=32&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
315	ktcom_630	상품^모바일^요금제	https://product.kt.com/wDic/index.do?CateCode=6002	https://m.product.kt.com/wDic/index.do?CateCode=6002	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
316	ktcom_595	상품^모바일^요금제^3G 선불	https://product.kt.com/wDic/productDetail.do?ItemCode=1038&CateCode=6002&filter_code=5&option_code=107&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1038&CateCode=6002&filter_code=5&option_code=107&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
317	ktcom_598	상품^모바일^요금제^5G 데이터투게더	https://product.kt.com/wDic/productDetail.do?ItemCode=1369&CateCode=6002&filter_code=4&option_code=122&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1369&CateCode=6002&filter_code=4&option_code=122&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
318	ktcom_599	상품^모바일^요금제^5G 복지​(장애인 전용)	https://product.kt.com/wDic/productDetail.do?ItemCode=1438&CateCode=6002&filter_code=81&option_code=109&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1438&CateCode=6002&filter_code=81&option_code=109&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
319	ktcom_600	상품^모바일^요금제^5G 스마트기기	https://product.kt.com/wDic/productDetail.do?ItemCode=1402&CateCode=6002&filter_code=4&option_code=122&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1402&CateCode=6002&filter_code=4&option_code=122&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
320	ktcom_601	상품^모바일^요금제^5G 스페셜베이직	https://product.kt.com/wDic/productDetail.do?ItemCode=1283&CateCode=6002&filter_code=81&option_code=109&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1283&CateCode=6002&filter_code=81&option_code=109&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
321	ktcom_602	상품^모바일^요금제^5G 슬림	https://product.kt.com/wDic/productDetail.do?ItemCode=1284&CateCode=6002&filter_code=81&option_code=109&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1284&CateCode=6002&filter_code=81&option_code=109&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
322	ktcom_603	상품^모바일^요금제^5G 슬림(이월)	https://product.kt.com/wDic/productDetail.do?ItemCode=1570&CateCode=6002&filter_code=81&option_code=109&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1570&CateCode=6002&filter_code=81&option_code=109&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
323	ktcom_604	상품^모바일^요금제^5G 시니어(만 65세 이상)	https://product.kt.com/wDic/productDetail.do?ItemCode=1558&CateCode=6002&filter_code=81&option_code=109&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1558&CateCode=6002&filter_code=81&option_code=109&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
324	ktcom_605	상품^모바일^요금제^5G 심플	https://product.kt.com/wDic/productDetail.do?ItemCode=1406&CateCode=6002&filter_code=81&option_code=109&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1406&CateCode=6002&filter_code=81&option_code=109&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
325	ktcom_606	상품^모바일^요금제^5G 웰컴(외국인 전용)	https://product.kt.com/wDic/productDetail.do?ItemCode=1577&CateCode=6002&filter_code=81&option_code=109&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1577&CateCode=6002&filter_code=81&option_code=109&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
326	ktcom_607	상품^모바일^요금제^5G 주니어(만 12세 이하)	https://product.kt.com/wDic/productDetail.do?ItemCode=1480&CateCode=6002&filter_code=81&option_code=109&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1480&CateCode=6002&filter_code=81&option_code=109&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
404	ktcom_662	상품^소상공인^부가상품^KT AI 통화비서	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1453&CateCode=7003&filter_code=2&option_code=2&pageSize=10		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
327	ktcom_608	상품^모바일^요금제^5G 초이스	https://product.kt.com/wDic/productDetail.do?ItemCode=1485&CateCode=6002&filter_code=81&option_code=109&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1485&CateCode=6002&filter_code=81&option_code=109&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
328	ktcom_596	상품^모바일^요금제^5G Y(만 34세 이하)	https://product.kt.com/wDic/productDetail.do?ItemCode=1358&CateCode=6002&filter_code=81&option_code=109&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1358&CateCode=6002&filter_code=81&option_code=109&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
329	ktcom_597	상품^모바일^요금제^5G Y틴(만 18세 이하)	https://product.kt.com/wDic/productDetail.do?ItemCode=1360&CateCode=6002&filter_code=81&option_code=109&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1360&CateCode=6002&filter_code=81&option_code=109&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
330	ktcom_631	상품^모바일^요금제^골든스마트 요금제	https://product.kt.com/wDic/productDetail.do?ItemCode=279&CateCode=6002&filter_code=3&option_code=6&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=279&CateCode=6002&filter_code=3&option_code=6&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
331	ktcom_632	상품^모바일^요금제^데이터투게더 Large	https://product.kt.com/wDic/productDetail.do?ItemCode=1134&CateCode=6002&filter_code=4&option_code=11&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1134&CateCode=6002&filter_code=4&option_code=11&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
332	ktcom_633	상품^모바일^요금제^데이터투게더 Medium	https://product.kt.com/wDic/productDetail.do?ItemCode=1191&CateCode=6002&filter_code=4&option_code=11&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1191&CateCode=6002&filter_code=4&option_code=11&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
333	ktcom_634	상품^모바일^요금제^데이터투게더 Watch	https://product.kt.com/wDic/productDetail.do?ItemCode=1257&CateCode=6002&filter_code=4&option_code=11&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1257&CateCode=6002&filter_code=4&option_code=11&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
334	ktcom_635	상품^모바일^요금제^듀얼번호	https://product.kt.com/wDic/productDetail.do?ItemCode=1540&CateCode=6002&filter_code=4&option_code=122&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1540&CateCode=6002&filter_code=4&option_code=122&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
335	ktcom_636	상품^모바일^요금제^복지15000 요금제	https://product.kt.com/wDic/productDetail.do?ItemCode=25&CateCode=6002&filter_code=3&option_code=6&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=25&CateCode=6002&filter_code=3&option_code=6&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
336	ktcom_637	상품^모바일^요금제^손말 요금제	https://product.kt.com/wDic/productDetail.do?ItemCode=31&CateCode=6002&filter_code=3&option_code=6&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=31&CateCode=6002&filter_code=3&option_code=6&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
337	ktcom_639	상품^모바일^요금제^순 골든(3G)	https://product.kt.com/wDic/productDetail.do?ItemCode=1018&CateCode=6002&filter_code=3&option_code=6&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1018&CateCode=6002&filter_code=3&option_code=6&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
338	ktcom_640	상품^모바일^요금제^순 나눔(3G)	https://product.kt.com/wDic/productDetail.do?ItemCode=1016&CateCode=6002&filter_code=3&option_code=6&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1016&CateCode=6002&filter_code=3&option_code=6&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
339	ktcom_641	상품^모바일^요금제^순 데이터(3G)	https://product.kt.com/wDic/productDetail.do?ItemCode=1019&CateCode=6002&filter_code=4&option_code=56&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1019&CateCode=6002&filter_code=4&option_code=56&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
340	ktcom_642	상품^모바일^요금제^순 모두다올레(3G)	https://product.kt.com/wDic/productDetail.do?ItemCode=1014&CateCode=6002&filter_code=3&option_code=6&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1014&CateCode=6002&filter_code=3&option_code=6&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
341	ktcom_643	상품^모바일^요금제^순 완전무한(3G)	https://product.kt.com/wDic/productDetail.do?ItemCode=1013&CateCode=6002&filter_code=3&option_code=6&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1013&CateCode=6002&filter_code=3&option_code=6&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
342	ktcom_644	상품^모바일^요금제^순 청소년(3G)	https://product.kt.com/wDic/productDetail.do?ItemCode=1017&CateCode=6002&filter_code=3&option_code=6&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1017&CateCode=6002&filter_code=3&option_code=6&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
343	ktcom_638	상품^모바일^요금제^순 i(3G)	https://product.kt.com/wDic/productDetail.do?ItemCode=1015&CateCode=6002&filter_code=3&option_code=6&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1015&CateCode=6002&filter_code=3&option_code=6&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
344	ktcom_645	상품^모바일^요금제^스마트 디바이스(LTE)	https://product.kt.com/wDic/productDetail.do?ItemCode=1129&CateCode=6002&filter_code=4&option_code=11&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1129&CateCode=6002&filter_code=4&option_code=11&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
345	ktcom_646	상품^모바일^요금제^슬림	https://product.kt.com/wDic/productDetail.do?ItemCode=35&CateCode=6002&filter_code=3&option_code=6&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=35&CateCode=6002&filter_code=3&option_code=6&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
346	ktcom_647	상품^모바일^요금제^신 표준	https://product.kt.com/wDic/productDetail.do?ItemCode=12&CateCode=6002&filter_code=3&option_code=6&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=12&CateCode=6002&filter_code=3&option_code=6&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
347	ktcom_648	상품^모바일^요금제^알스마트	https://product.kt.com/wDic/productDetail.do?ItemCode=48&CateCode=6002&filter_code=3&option_code=6&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=48&CateCode=6002&filter_code=3&option_code=6&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
348	ktcom_649	상품^모바일^요금제^알캡요금제	https://product.kt.com/wDic/productDetail.do?ItemCode=8&CateCode=6002&filter_code=3&option_code=6&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=8&CateCode=6002&filter_code=3&option_code=6&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
349	ktcom_650	상품^모바일^요금제^요고 다이렉트	https://product.kt.com/wDic/productDetail.do?ItemCode=1567&CateCode=6002&filter_code=81&option_code=109&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1567&CateCode=6002&filter_code=81&option_code=109&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
350	ktcom_651	상품^모바일^요금제^키즈 80	https://product.kt.com/wDic/productDetail.do?ItemCode=1067&CateCode=6002&filter_code=4&option_code=56&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1067&CateCode=6002&filter_code=4&option_code=56&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
351	ktcom_652	상품^모바일^요금제^키즈 알115(3G)	https://product.kt.com/wDic/productDetail.do?ItemCode=955&CateCode=6002&filter_code=3&option_code=6&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=955&CateCode=6002&filter_code=3&option_code=6&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
352	ktcom_653	상품^모바일^요금제^표준 요금제	https://product.kt.com/wDic/productDetail.do?ItemCode=7&CateCode=6002&filter_code=3&option_code=6&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=7&CateCode=6002&filter_code=3&option_code=6&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
353	ktcom_654	상품^모바일^요금제^효 요금제	https://product.kt.com/wDic/productDetail.do?ItemCode=38&CateCode=6002&filter_code=3&option_code=6&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=38&CateCode=6002&filter_code=3&option_code=6&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
354	ktcom_613	상품^모바일^요금제^LTE 다이렉트 45	https://product.kt.com/wDic/productDetail.do?ItemCode=1432&CateCode=6002&filter_code=2&option_code=1&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1432&CateCode=6002&filter_code=2&option_code=1&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
355	ktcom_614	상품^모바일^요금제^LTE 데이터ON	https://product.kt.com/wDic/productDetail.do?ItemCode=1248&CateCode=6002&filter_code=2&option_code=1&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1248&CateCode=6002&filter_code=2&option_code=1&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
356	ktcom_615	상품^모바일^요금제^LTE 복지(장애인 전용)	https://product.kt.com/wDic/productDetail.do?ItemCode=1354&CateCode=6002&filter_code=2&option_code=1&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1354&CateCode=6002&filter_code=2&option_code=1&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
357	ktcom_616	상품^모바일^요금제^LTE 선불	https://product.kt.com/wDic/productDetail.do?ItemCode=1036&CateCode=6002&filter_code=5&option_code=107&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1036&CateCode=6002&filter_code=5&option_code=107&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
358	ktcom_617	상품^모바일^요금제^LTE 순 선택형	https://product.kt.com/wDic/productDetail.do?ItemCode=1192&CateCode=6002&filter_code=2&option_code=1&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1192&CateCode=6002&filter_code=2&option_code=1&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
359	ktcom_618	상품^모바일^요금제^LTE 시니어(만 65세 이상)	https://product.kt.com/wDic/productDetail.do?ItemCode=1356&CateCode=6002&filter_code=2&option_code=1&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1356&CateCode=6002&filter_code=2&option_code=1&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
360	ktcom_619	상품^모바일^요금제^LTE 웰컴 선불(외국인 전용)	https://product.kt.com/wDic/productDetail.do?ItemCode=1612&CateCode=6002&filter_code=2&option_code=1&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1612&CateCode=6002&filter_code=2&option_code=1&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
361	ktcom_620	상품^모바일^요금제^LTE 음성	https://product.kt.com/wDic/productDetail.do?ItemCode=1238&CateCode=6002&filter_code=2&option_code=1&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1238&CateCode=6002&filter_code=2&option_code=1&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
362	ktcom_622	상품^모바일^요금제^LTE 주니어(만 12세 이하)	https://product.kt.com/wDic/productDetail.do?ItemCode=1425&CateCode=6002&filter_code=2&option_code=1&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1425&CateCode=6002&filter_code=2&option_code=1&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
363	ktcom_621	상품^모바일^요금제^LTE 일반	https://product.kt.com/wDic/productDetail.do?ItemCode=1249&CateCode=6002&filter_code=2&option_code=1&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1249&CateCode=6002&filter_code=2&option_code=1&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
364	ktcom_612	상품^모바일^요금제^LTE egg+	https://product.kt.com/wDic/productDetail.do?ItemCode=987&CateCode=6002&filter_code=5&option_code=16&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=987&CateCode=6002&filter_code=5&option_code=16&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
365	ktcom_609	상품^모바일^요금제^LTE Y 군인	https://product.kt.com/wDic/productDetail.do?ItemCode=1379&CateCode=6002&filter_code=2&option_code=1&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1379&CateCode=6002&filter_code=2&option_code=1&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
366	ktcom_610	상품^모바일^요금제^LTE Y(만 34세 이하)	https://product.kt.com/wDic/productDetail.do?ItemCode=1256&CateCode=6002&filter_code=2&option_code=1&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1256&CateCode=6002&filter_code=2&option_code=1&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
367	ktcom_611	상품^모바일^요금제^LTE Y틴(만 18세 이하)	https://product.kt.com/wDic/productDetail.do?ItemCode=1128&CateCode=6002&filter_code=2&option_code=1&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1128&CateCode=6002&filter_code=2&option_code=1&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
368	ktcom_665	상품^모바일^요금제^NB-IoT	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1411&CateCode=7003&filter_code=2&option_code=2&pageSize=10		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
369	ktcom_624	상품^모바일^요금제^Style 요금제	https://product.kt.com/wDic/productDetail.do?ItemCode=36&CateCode=6002&filter_code=3&option_code=6&pageSize=20	https://m.product.kt.com/wDic/productDetail.do?ItemCode=36&CateCode=6002&filter_code=3&option_code=6&pageSize=20	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
370	ktcom_626	상품^모바일^요금제^Wearable(LTE)	https://product.kt.com/wDic/productDetail.do?ItemCode=1097&CateCode=6002&filter_code=4&option_code=11&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1097&CateCode=6002&filter_code=4&option_code=11&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
371	ktcom_625	상품^모바일^요금제^Wearable(3G)	https://product.kt.com/wDic/productDetail.do?ItemCode=988&CateCode=6002&filter_code=4&option_code=56&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=988&CateCode=6002&filter_code=4&option_code=56&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
372	ktcom_627	상품^모바일^요금제^WiFi 멀티	https://product.kt.com/wDic/productDetail.do?ItemCode=175&CateCode=6002&filter_code=5&option_code=62&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=175&CateCode=6002&filter_code=5&option_code=62&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
373	ktcom_628	상품^모바일^요금제^WiFi 싱글	https://product.kt.com/wDic/productDetail.do?ItemCode=177&CateCode=6002&filter_code=5&option_code=62&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=177&CateCode=6002&filter_code=5&option_code=62&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
374	ktcom_629	상품^모바일^요금제^Y주니어 워치	https://product.kt.com/wDic/productDetail.do?ItemCode=1230&CateCode=6002&filter_code=4&option_code=11&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1230&CateCode=6002&filter_code=4&option_code=11&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
376	ktcom_425	상품^모바일^OTT구독	https://my.kt.com/product/OttSubscribeView.do	https://m.my.kt.com/product/OttSubscribeView.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
378	ktcom_426	상품^모바일^WiFi이용안내^MACID등록^MAC 주소 확인 방법	https://wifi.kt.com/kt/kt_wifi_macid2.html#checkmac		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
379	ktcom_427	상품^모바일^WiFi이용안내^MACID등록^MACID 등록(수정) 방법	https://wifi.kt.com/kt/kt_wifi_macid2.html#modifymac		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
380	ktcom_428	상품^모바일^WiFi이용안내^MACID등록^MACID 등록안내	https://wifi.kt.com/kt/kt_wifi_macid2.html#registmac		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
381	ktcom_429	상품^모바일^WiFi이용안내^MACID등록^WiFi 초기화 방법	https://wifi.kt.com/kt/kt_wifi_macid2.html#initwifi		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
383	ktcom_431	상품^모바일^WiFi이용안내^WiFi설정안내^WiFi2.0이란^GiGA WiFi 2.0이란	https://wifi.kt.com/kt/showktwifi01.html		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
384	ktcom_433	상품^모바일^WiFi이용안내^WiFi설정안내^WiFi2.0이란^GiGA WiFi 이용방법	https://wifi.kt.com/kt/showktwifi05.html		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
385	ktcom_434	상품^모바일^WiFi이용안내^WiFi설정안내^WiFi2.0이란^GiGA WiFi 지원단말	https://wifi.kt.com/kt/showktwifi03.html		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
386	ktcom_432	상품^모바일^WiFi이용안내^WiFi설정안내^WiFi2.0이란^GiGA WiFi zone 보기	https://wifi.kt.com/kt/showktwifi04.html		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
387	ktcom_658	상품^소상공인^기가아이즈	https://product.kt.com/wDic/soho/marketing.do?ItemCode=gigaeyes	https://m.product.kt.com/wDic/soho/marketing.do?ItemCode=gigaeyes	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
388	ktcom_659	상품^소상공인^부가상품^0502평생번호	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=181&CateCode=7003&filter_code=2&option_code=2&pageSize=10	https://m.product.kt.com/wDic/soho/productDetail.do?ItemCode=181&CateCode=7003&filter_code=2&option_code=2&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
389	ktcom_663	상품^소상공인^부가상품^가게정보알림메시지 (소상공인형)	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1451&CateCode=7003&filter_code=3&option_code=3&pageSize=10	https://m.product.kt.com/wDic/soho/productDetail.do?ItemCode=1451&CateCode=7003&filter_code=3&option_code=3&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
390	ktcom_664	상품^소상공인^부가상품^링고비즈	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1410&CateCode=7003&filter_code=3&option_code=3&pageSize=10	https://m.product.kt.com/wDic/soho/productDetail.do?ItemCode=1410&CateCode=7003&filter_code=3&option_code=3&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
391	ktcom_665	상품^소상공인^부가상품^발신정보알리미 오피스형	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1411&CateCode=7003&filter_code=2&option_code=2&pageSize=10		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
392	ktcom_667	상품^소상공인^부가상품^사장님 배달POS	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1539&CateCode=7003&filter_code=4&option_code=4&pageSize=10	https://m.product.kt.com/wDic/soho/productDetail.do?ItemCode=1539&CateCode=7003&filter_code=4&option_code=4&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
393	ktcom_668	상품^소상공인^부가상품^사장님 배달POS 인터넷전화	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1536&CateCode=7003&filter_code=4&option_code=4&pageSize=10	https://m.product.kt.com/wDic/soho/productDetail.do?ItemCode=1536&CateCode=7003&filter_code=4&option_code=4&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
394	ktcom_669	상품^소상공인^부가상품^사장님 배달POS 전화	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1522&CateCode=7003&filter_code=4&option_code=4&pageSize=10	https://m.product.kt.com/wDic/soho/productDetail.do?ItemCode=1522&CateCode=7003&filter_code=4&option_code=4&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
395	ktcom_666	상품^소상공인^부가상품^사장님 AI비서팩	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1488&CateCode=7003&filter_code=1&option_code=1&pageSize=10		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
396	ktcom_670	상품^소상공인^부가상품^사장님TV	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1602&CateCode=7003&filter_code=3&option_code=3&pageSize=10		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
397	ktcom_671	상품^소상공인^부가상품^우리동네TV	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1617&CateCode=7003&filter_code=3&option_code=3&pageSize=10	https://m.product.kt.com/wDic/soho/productDetail.do?ItemCode=1617&CateCode=7003&filter_code=3&option_code=3&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
398	ktcom_672	상품^소상공인^부가상품^착신통화전환	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=152&CateCode=7003&filter_code=2&option_code=2&pageSize=10		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
399	ktcom_673	상품^소상공인^부가상품^추가단말서비스	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=753&CateCode=7003&filter_code=4&option_code=4&pageSize=10		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
400	ktcom_674	상품^소상공인^부가상품^통화매니저 PC	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=376&CateCode=7003&filter_code=2&option_code=2&pageSize=10	https://m.product.kt.com/wDic/soho/productDetail.do?ItemCode=376&CateCode=7003&filter_code=2&option_code=2&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
401	ktcom_675	상품^소상공인^부가상품^통화중대기(집전화)	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=155&CateCode=7003&filter_code=2&option_code=2&pageSize=10		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
402	ktcom_660	상품^소상공인^부가상품^AI링고	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1566&CateCode=7003&filter_code=3&option_code=3&pageSize=10		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
403	ktcom_661	상품^소상공인^부가상품^AI전화	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1553&CateCode=7003&filter_code=2&option_code=2&pageSize=10		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
405	ktcom_676	상품^소상공인^사장님혜택존	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1513	https://m.product.kt.com/wDic/soho/productDetail.do?ItemCode=1513	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
407	ktcom_679	상품^소상공인^소상공인통신상품	https://product.kt.com/wDic/soho/index.do?CateCode=7002	https://m.product.kt.com/wDic/soho/index.do?CateCode=7002	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
408	ktcom_680	상품^소상공인^으랏차차패키지	https://product.kt.com/wDic/soho/marketing.do?ItemCode=main	https://m.product.kt.com/wDic/soho/marketing.do?ItemCode=main	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
409	ktcom_686	상품^소상공인^통신상품^결제안심 인터넷	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1506&CateCode=7002&filter_code=5&option_code=5&pageSize=10	https://m.product.kt.com/wDic/soho/productDetail.do?ItemCode=1506&CateCode=7002&filter_code=5&option_code=5&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
410	ktcom_687	상품^소상공인^통신상품^인터넷	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1505&CateCode=7002&filter_code=5&option_code=5&pageSize=10	https://m.product.kt.com/wDic/soho/productDetail.do?ItemCode=1505&CateCode=7002&filter_code=5&option_code=5&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
411	ktcom_688	상품^소상공인^통신상품^인터넷 와이드	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1496&CateCode=7002&filter_code=5&option_code=5&pageSize=10	https://m.product.kt.com/wDic/soho/productDetail.do?ItemCode=1496&CateCode=7002&filter_code=5&option_code=5&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
412	ktcom_689	상품^소상공인^통신상품^인터넷 와이파이	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1503&CateCode=7002&filter_code=5&option_code=5&pageSize=10	https://m.product.kt.com/wDic/soho/productDetail.do?ItemCode=1503&CateCode=7002&filter_code=5&option_code=5&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
413	ktcom_690	상품^소상공인^통신상품^인터넷전화 3000	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1021&CateCode=7002&filter_code=7&option_code=7&pageSize=10	https://m.product.kt.com/wDic/soho/productDetail.do?ItemCode=1021&CateCode=7002&filter_code=7&option_code=7&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
414	ktcom_691	상품^소상공인^통신상품^지니 TV 사장님 초이스	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1519&CateCode=7002&filter_code=6&option_code=6&pageSize=10	https://m.product.kt.com/wDic/soho/productDetail.do?ItemCode=1519&CateCode=7002&filter_code=6&option_code=6&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
415	ktcom_692	상품^소상공인^통신상품^집전화 3000	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=974&CateCode=7002&filter_code=7&option_code=7&pageSize=10	https://m.product.kt.com/wDic/soho/productDetail.do?ItemCode=974&CateCode=7002&filter_code=7&option_code=7&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
416	ktcom_681	상품^소상공인^통신상품^AI전화	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1553&CateCode=7002&filter_code=7&option_code=7&pageSize=10		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
417	ktcom_682	상품^소상공인^통신상품^TV 일반	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1518&CateCode=7002&filter_code=6&option_code=6&pageSize=10	https://m.product.kt.com/wDic/soho/productDetail.do?ItemCode=1518&CateCode=7002&filter_code=6&option_code=6&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
418	ktcom_683	상품^소상공인^통신상품^TV 초이스 스페셜	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1516&CateCode=7002&filter_code=6&option_code=6&pageSize=10	https://m.product.kt.com/wDic/soho/productDetail.do?ItemCode=1516&CateCode=7002&filter_code=6&option_code=6&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
419	ktcom_684	상품^소상공인^통신상품^TV 초이스 프리미엄	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1515&CateCode=7002&filter_code=6&option_code=6&pageSize=10	https://m.product.kt.com/wDic/soho/productDetail.do?ItemCode=1515&CateCode=7002&filter_code=6&option_code=6&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
420	ktcom_685	상품^소상공인^통신상품^TV 초이스 플러스	https://product.kt.com/wDic/soho/productDetail.do?ItemCode=1517&CateCode=7002&filter_code=6&option_code=6&pageSize=10	https://m.product.kt.com/wDic/soho/productDetail.do?ItemCode=1517&CateCode=7002&filter_code=6&option_code=6&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
421	ktcom_693	상품^소상공인^하이오더	https://product.kt.com/wDic/soho/marketing.do?ItemCode=highorder	https://m.product.kt.com/wDic/soho/marketing.do?ItemCode=highorder	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
422	ktcom_656	상품^소상공인^AI링고전화	https://product.kt.com/wDic/soho/marketing.do?ItemCode=lingophone		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
423	ktcom_657	상품^소상공인^KT서빙로봇	https://product.kt.com/wDic/soho/marketing.do?ItemCode=airobot	https://m.product.kt.com/wDic/soho/marketing.do?ItemCode=airobot	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
424	ktcom_696	상품^와이파이(WiFi)^요금제^기가 와이파이 프리미엄	https://product.kt.com/wDic/productDetail.do?ItemCode=1546&CateCode=6042&filter_code=99&option_code=151&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1546&CateCode=6042&filter_code=99&option_code=151&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
425	ktcom_697	상품^와이파이(WiFi)^요금제^기가 와이파이 홈	https://product.kt.com/wDic/productDetail.do?ItemCode=1401&CateCode=6042&filter_code=99&option_code=151&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1401&CateCode=6042&filter_code=99&option_code=151&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
426	ktcom_694	상품^와이파이(WiFi)^요금제^KT WiFi 6D	https://product.kt.com/wDic/productDetail.do?ItemCode=1568&CateCode=6042&filter_code=99&option_code=151&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1568&CateCode=6042&filter_code=99&option_code=151&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
427	ktcom_695	상품^와이파이(WiFi)^요금제^KT WiFi 7D	https://product.kt.com/wDic/productDetail.do?ItemCode=1633&CateCode=6042&filter_code=99&option_code=151&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1633&CateCode=6042&filter_code=99&option_code=151&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
428	ktcom_703	상품^인터넷^부가서비스	https://product.kt.com/wDic/index.do?CateCode=6006	https://m.product.kt.com/wDic/index.do?CateCode=6006	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
429	ktcom_704	상품^인터넷^부가서비스^가족 안심	https://product.kt.com/wDic/productDetail.do?ItemCode=1080&CateCode=6006&filter_code=18&option_code=37&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1080&CateCode=6006&filter_code=18&option_code=37&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
430	ktcom_705	상품^인터넷^부가서비스^사장님 배달POS	https://product.kt.com/wDic/productDetail.do?ItemCode=1539&CateCode=6006&filter_code=19&option_code=38&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1539&CateCode=6006&filter_code=19&option_code=38&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
501	ktcom_771	상품^전화^일반전화^인터넷전화	https://product.kt.com/wDic/index.do?CateCode=6012	https://m.product.kt.com/wDic/index.do?CateCode=6012	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
431	ktcom_706	상품^인터넷^부가서비스^사장님 장부비서	https://product.kt.com/wDic/productDetail.do?ItemCode=1440&CateCode=6006&filter_code=19&option_code=38&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1440&CateCode=6006&filter_code=19&option_code=38&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
432	ktcom_707	상품^인터넷^부가서비스^안심플러스	https://product.kt.com/wDic/productDetail.do?ItemCode=1472&CateCode=6006&filter_code=18&option_code=37&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1472&CateCode=6006&filter_code=18&option_code=37&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
433	ktcom_708	상품^인터넷^부가서비스^인터넷 놀e터	https://product.kt.com/wDic/productDetail.do?ItemCode=144&CateCode=6006&filter_code=18&option_code=37&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=144&CateCode=6006&filter_code=18&option_code=37&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
434	ktcom_709	상품^인터넷^부가서비스^추가단말서비스	https://product.kt.com/wDic/productDetail.do?ItemCode=753&CateCode=6006&filter_code=19&option_code=38&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=753&CateCode=6006&filter_code=19&option_code=38&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
435	ktcom_710	상품^인터넷^부가서비스^토탈안심	https://product.kt.com/wDic/productDetail.do?ItemCode=1624&CateCode=6006&filter_code=18&option_code=37&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1624&CateCode=6006&filter_code=18&option_code=37&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
436	ktcom_711	상품^인터넷^부가서비스^홈캠 안심 서비스	https://product.kt.com/wDic/productDetail.do?ItemCode=1632&CateCode=6006&filter_code=18&option_code=37&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1632&CateCode=6006&filter_code=18&option_code=37&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
437	ktcom_701	상품^인터넷^부가서비스^KT 인터넷지킴이	https://product.kt.com/wDic/productDetail.do?ItemCode=1458&CateCode=6006&filter_code=18&option_code=37&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1458&CateCode=6006&filter_code=18&option_code=37&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
438	ktcom_702	상품^인터넷^부가서비스^PC 안심 2.0	https://product.kt.com/wDic/productDetail.do?ItemCode=1306&CateCode=6006&filter_code=18&option_code=37&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1306&CateCode=6006&filter_code=18&option_code=37&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
439	ktcom_712	상품^인터넷^와이파이(WiFi)^소개	https://product.kt.com/wDic/productDetail.do?ItemCode=1533	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1533	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
440	ktcom_713	상품^인터넷^와이파이(WiFi)^요금제	https://product.kt.com/wDic/index.do?CateCode=6042	https://m.product.kt.com/wDic/index.do?CateCode=6042	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
441	ktcom_714	상품^인터넷^요금제	https://product.kt.com/wDic/index.do?CateCode=6005	https://m.product.kt.com/wDic/index.do?CateCode=6005	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
442	ktcom_715	상품^인터넷^요금제^선불 인터넷	https://product.kt.com/wDic/productDetail.do?ItemCode=1535&CateCode=6005&filter_code=119&option_code=171&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1535&CateCode=6005&filter_code=119&option_code=171&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
443	ktcom_716	상품^인터넷^요금제^선불 인터넷 와이파이	https://product.kt.com/wDic/productDetail.do?ItemCode=1534&CateCode=6005&filter_code=119&option_code=171&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1534&CateCode=6005&filter_code=119&option_code=171&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
444	ktcom_717	상품^인터넷^요금제^인터넷	https://product.kt.com/wDic/productDetail.do?ItemCode=1505&CateCode=6005&filter_code=118&option_code=170&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1505&CateCode=6005&filter_code=118&option_code=170&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
445	ktcom_718	상품^인터넷^요금제^인터넷 와이드	https://product.kt.com/wDic/productDetail.do?ItemCode=1496&CateCode=6005&filter_code=118&option_code=170&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1496&CateCode=6005&filter_code=118&option_code=170&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
446	ktcom_719	상품^인터넷^요금제^인터넷 와이파이	https://product.kt.com/wDic/productDetail.do?ItemCode=1503&CateCode=6005&filter_code=118&option_code=170&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1503&CateCode=6005&filter_code=118&option_code=170&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
447	ktcom_720	상품^인터넷^요금제^인터넷팩M(토탈안심 인터넷 와이드(7D))	https://product.kt.com/wDic/productDetail.do?ItemCode=1497&CateCode=6005&filter_code=117&option_code=169&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1497&CateCode=6005&filter_code=117&option_code=169&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
448	ktcom_721	상품^인터넷^요금제^인터넷팩S(토탈안심 인터넷 와이파이(7D))	https://product.kt.com/wDic/productDetail.do?ItemCode=1502&CateCode=6005&filter_code=117&option_code=169&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1502&CateCode=6005&filter_code=117&option_code=169&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
449	ktcom_722	상품^인터넷^요금제^토탈안심 인터넷	https://product.kt.com/wDic/productDetail.do?ItemCode=1625&CateCode=6005&filter_code=117&option_code=169&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1625&CateCode=6005&filter_code=117&option_code=169&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
450	ktcom_723	상품^인터넷^요금제^프리미엄급 인터넷	https://product.kt.com/wDic/productDetail.do?ItemCode=1504&CateCode=6005&filter_code=118&option_code=170&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1504&CateCode=6005&filter_code=118&option_code=170&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
451	ktcom_698	상품^인터넷^WhyKT인터넷^소개	https://product.kt.com/wDic/productDetail.do?ItemCode=1452	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1452	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
452	ktcom_699	상품^인터넷^WhyKT인터넷^프리미엄급인터넷	https://product.kt.com/wDic/productDetail.do?ItemCode=1262	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1262	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
453	ktcom_700	상품^인터넷^WhyKT인터넷^프리미엄급인터넷체험존	https://product.kt.com/wDic/testZoneList.do	https://m.product.kt.com/wDic/testZoneList.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
454	ktcom_724	상품^일반전화^부가서비스^0502평생번호	https://product.kt.com/wDic/productDetail.do?ItemCode=181&CateCode=6013&filter_code=37&option_code=64&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=181&CateCode=6013&filter_code=37&option_code=64&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
455	ktcom_725	상품^일반전화^부가서비스^114 번호안내	https://product.kt.com/wDic/productDetail.do?ItemCode=1207&CateCode=6013&filter_code=37&option_code=64&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1207&CateCode=6013&filter_code=37&option_code=64&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
456	ktcom_729	상품^일반전화^부가서비스^링고	https://product.kt.com/wDic/productDetail.do?ItemCode=1322&CateCode=6013&filter_code=37&option_code=64&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1322&CateCode=6013&filter_code=37&option_code=64&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
457	ktcom_730	상품^일반전화^부가서비스^주소연락처 일괄변경서비스(ktmoving)	https://product.kt.com/wDic/productDetail.do?ItemCode=853&CateCode=6013&filter_code=37&option_code=64&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=853&CateCode=6013&filter_code=37&option_code=64&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
458	ktcom_731	상품^일반전화^부가서비스^통화매니저 APP	https://product.kt.com/wDic/productDetail.do?ItemCode=985&CateCode=6013&filter_code=37&option_code=64&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=985&CateCode=6013&filter_code=37&option_code=64&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
459	ktcom_732	상품^일반전화^부가서비스^통화매니저 PC	https://product.kt.com/wDic/productDetail.do?ItemCode=376&CateCode=6013&filter_code=37&option_code=64&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=376&CateCode=6013&filter_code=37&option_code=64&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
460	ktcom_726	상품^일반전화^부가서비스^AI링고	https://product.kt.com/wDic/productDetail.do?ItemCode=1566&CateCode=6013&filter_code=37&option_code=64&pageSize=10		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
461	ktcom_727	상품^일반전화^부가서비스^KT AI 통화비서	https://product.kt.com/wDic/productDetail.do?ItemCode=1453&CateCode=6013&filter_code=37&option_code=64&pageSize=10		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
462	ktcom_728	상품^일반전화^부가서비스^V링고	https://product.kt.com/wDic/productDetail.do?ItemCode=1475&CateCode=6013&filter_code=37&option_code=64&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1475&CateCode=6013&filter_code=37&option_code=64&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
463	ktcom_733	상품^일반전화^인터넷전화^3인통화	https://product.kt.com/wDic/productDetail.do?ItemCode=388&CateCode=6012&filter_code=27&option_code=49&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=388&CateCode=6012&filter_code=27&option_code=49&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
464	ktcom_735	상품^일반전화^인터넷전화^발신번호표시(인터넷전화)	https://product.kt.com/wDic/productDetail.do?ItemCode=390&CateCode=6012&filter_code=27&option_code=49&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=390&CateCode=6012&filter_code=27&option_code=49&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
465	ktcom_736	상품^일반전화^인터넷전화^번호변경안내(인터넷전화)	https://product.kt.com/wDic/productDetail.do?ItemCode=396&CateCode=6012&filter_code=27&option_code=50&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=396&CateCode=6012&filter_code=27&option_code=50&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
466	ktcom_737	상품^일반전화^인터넷전화^사장님 배달POS 인터넷전화	https://product.kt.com/wDic/productDetail.do?ItemCode=1536&CateCode=6012&filter_code=26&option_code=47&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1536&CateCode=6012&filter_code=26&option_code=47&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
467	ktcom_738	상품^일반전화^인터넷전화^인터넷전화 3000	https://product.kt.com/wDic/productDetail.do?ItemCode=1021&CateCode=6012&filter_code=26&option_code=47&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1021&CateCode=6012&filter_code=26&option_code=47&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
468	ktcom_739	상품^일반전화^인터넷전화^인터넷전화 기본요금제	https://product.kt.com/wDic/productDetail.do?ItemCode=187&CateCode=6012&filter_code=26&option_code=48&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=187&CateCode=6012&filter_code=26&option_code=48&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
469	ktcom_740	상품^일반전화^인터넷전화^인터넷전화 표준+	https://product.kt.com/wDic/productDetail.do?ItemCode=1151&CateCode=6012&filter_code=26&option_code=48&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1151&CateCode=6012&filter_code=26&option_code=48&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
470	ktcom_741	상품^일반전화^인터넷전화^인터넷전화 표준영상	https://product.kt.com/wDic/productDetail.do?ItemCode=1150&CateCode=6012&filter_code=26&option_code=48&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1150&CateCode=6012&filter_code=26&option_code=48&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
471	ktcom_742	상품^일반전화^인터넷전화^지정번호 착신금지	https://product.kt.com/wDic/productDetail.do?ItemCode=391&CateCode=6012&filter_code=27&option_code=50&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=391&CateCode=6012&filter_code=27&option_code=50&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
472	ktcom_743	상품^일반전화^인터넷전화^착신전환(인터넷전화)	https://product.kt.com/wDic/productDetail.do?ItemCode=387&CateCode=6012&filter_code=27&option_code=49&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=387&CateCode=6012&filter_code=27&option_code=49&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
473	ktcom_744	상품^일반전화^인터넷전화^통화중대기(인터넷전화)	https://product.kt.com/wDic/productDetail.do?ItemCode=389&CateCode=6012&filter_code=27&option_code=49&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=389&CateCode=6012&filter_code=27&option_code=49&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
474	ktcom_734	상품^일반전화^인터넷전화^SMSMMS	https://product.kt.com/wDic/productDetail.do?ItemCode=398&CateCode=6012&filter_code=27&option_code=50&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=398&CateCode=6012&filter_code=27&option_code=50&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
475	ktcom_745	상품^일반전화^집전화매장전화^3인통화	https://product.kt.com/wDic/productDetail.do?ItemCode=388&CateCode=6011&filter_code=25&option_code=45&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=388&CateCode=6011&filter_code=25&option_code=45&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
498	ktcom_768	상품^전화^국제전화^부가서비스	https://product.kt.com/wDic/index.do?CateCode=6017	https://m.product.kt.com/wDic/index.do?CateCode=6017	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
476	ktcom_747	상품^일반전화^집전화매장전화^멀티넘버서비스	https://product.kt.com/wDic/productDetail.do?ItemCode=1090&CateCode=6011&filter_code=25&option_code=45&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1090&CateCode=6011&filter_code=25&option_code=45&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
477	ktcom_748	상품^일반전화^집전화매장전화^발신번호표시(집전화)	https://product.kt.com/wDic/productDetail.do?ItemCode=172&CateCode=6011&filter_code=25&option_code=45&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=172&CateCode=6011&filter_code=25&option_code=45&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
478	ktcom_749	상품^일반전화^집전화매장전화^번호변경안내	https://product.kt.com/wDic/productDetail.do?ItemCode=184&CateCode=6011&filter_code=25&option_code=46&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=184&CateCode=6011&filter_code=25&option_code=46&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
479	ktcom_750	상품^일반전화^집전화매장전화^사장님 배달POS 전화	https://product.kt.com/wDic/productDetail.do?ItemCode=1522&CateCode=6011&filter_code=24&option_code=43&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1522&CateCode=6011&filter_code=24&option_code=43&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
480	ktcom_751	상품^일반전화^집전화매장전화^수신차단서비스	https://product.kt.com/wDic/productDetail.do?ItemCode=1430&CateCode=6011&filter_code=25&option_code=45&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1430&CateCode=6011&filter_code=25&option_code=45&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
481	ktcom_752	상품^일반전화^집전화매장전화^신 효 요금제	https://product.kt.com/wDic/productDetail.do?ItemCode=142&CateCode=6011&filter_code=24&option_code=44&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=142&CateCode=6011&filter_code=24&option_code=44&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
482	ktcom_753	상품^일반전화^집전화매장전화^알림콜	https://product.kt.com/wDic/productDetail.do?ItemCode=178&CateCode=6011&filter_code=25&option_code=45&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=178&CateCode=6011&filter_code=25&option_code=45&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
483	ktcom_754	상품^일반전화^집전화매장전화^지정시간통보	https://product.kt.com/wDic/productDetail.do?ItemCode=157&CateCode=6011&filter_code=25&option_code=46&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=157&CateCode=6011&filter_code=25&option_code=46&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
484	ktcom_755	상품^일반전화^집전화매장전화^직통전화	https://product.kt.com/wDic/productDetail.do?ItemCode=160&CateCode=6011&filter_code=25&option_code=45&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=160&CateCode=6011&filter_code=25&option_code=45&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
485	ktcom_756	상품^일반전화^집전화매장전화^집전화	https://product.kt.com/wDic/productDetail.do?ItemCode=192&CateCode=6011&filter_code=24&option_code=44&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=192&CateCode=6011&filter_code=24&option_code=44&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
486	ktcom_757	상품^일반전화^집전화매장전화^집전화 3000	https://product.kt.com/wDic/productDetail.do?ItemCode=974&CateCode=6011&filter_code=24&option_code=43&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=974&CateCode=6011&filter_code=24&option_code=43&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
487	ktcom_758	상품^일반전화^집전화매장전화^집전화 단기전화	https://product.kt.com/wDic/productDetail.do?ItemCode=203&CateCode=6011&filter_code=24&option_code=44&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=203&CateCode=6011&filter_code=24&option_code=44&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
488	ktcom_759	상품^일반전화^집전화매장전화^집전화 복지전화	https://product.kt.com/wDic/productDetail.do?ItemCode=202&CateCode=6011&filter_code=24&option_code=44&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=202&CateCode=6011&filter_code=24&option_code=44&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
489	ktcom_760	상품^일반전화^집전화매장전화^집전화결제 이용동의	https://product.kt.com/wDic/productDetail.do?ItemCode=373&CateCode=6011&filter_code=25&option_code=46&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=373&CateCode=6011&filter_code=25&option_code=46&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
490	ktcom_761	상품^일반전화^집전화매장전화^착신통화전환	https://product.kt.com/wDic/productDetail.do?ItemCode=152&CateCode=6011&filter_code=25&option_code=45&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=152&CateCode=6011&filter_code=25&option_code=45&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
491	ktcom_762	상품^일반전화^집전화매장전화^통화중대기(집전화)	https://product.kt.com/wDic/productDetail.do?ItemCode=155&CateCode=6011&filter_code=25&option_code=45&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=155&CateCode=6011&filter_code=25&option_code=45&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
492	ktcom_763	상품^일반전화^집전화매장전화^패스콜	https://product.kt.com/wDic/productDetail.do?ItemCode=176&CateCode=6011&filter_code=25&option_code=45&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=176&CateCode=6011&filter_code=25&option_code=45&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
493	ktcom_746	상품^일반전화^집전화매장전화^AI전화	https://product.kt.com/wDic/productDetail.do?ItemCode=1553&CateCode=6011&filter_code=24&option_code=43&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1553&CateCode=6011&filter_code=24&option_code=43&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
494	ktcom_764	상품^일반전화^카드콜렉트콜^1541 콜렉트콜	https://product.kt.com/wDic/productDetail.do?ItemCode=370&CateCode=6014&filter_code=55&option_code=82&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=370&CateCode=6014&filter_code=55&option_code=82&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
495	ktcom_765	상품^일반전화^카드콜렉트콜^선불전화카드	https://product.kt.com/wDic/productDetail.do?ItemCode=380&CateCode=6014&filter_code=54&option_code=81&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=380&CateCode=6014&filter_code=54&option_code=81&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
496	ktcom_766	상품^일반전화^카드콜렉트콜^후불전화카드	https://product.kt.com/wDic/productDetail.do?ItemCode=379&CateCode=6014&filter_code=54&option_code=81&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=379&CateCode=6014&filter_code=54&option_code=81&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
497	ktcom_767	상품^전화^국제전화^국제전화이용방법	https://product.kt.com/wDic/productDetail.do?ItemCode=1212	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1212	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
499	ktcom_769	상품^전화^국제전화^요금제	https://product.kt.com/wDic/index.do?CateCode=6016	https://m.product.kt.com/wDic/index.do?CateCode=6016	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
500	ktcom_770	상품^전화^일반전화^부가서비스	https://product.kt.com/wDic/index.do?CateCode=6013		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
502	ktcom_772	상품^전화^일반전화^집전화매장전화	https://product.kt.com/wDic/index.do?CateCode=6011	https://m.product.kt.com/wDic/index.do?CateCode=6011	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
504	ktcom_312	상품^AI^디바이스^기가지니버디	https://gigagenie.kt.com/buddy/main.do	https://m.gigagenie.kt.com/buddy/main.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
505	ktcom_310	상품^AI^디바이스^기가지니LTE	https://gigagenie.kt.com/ltemain.do	https://m.gigagenie.kt.com/ltemain.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
506	ktcom_311	상품^AI^디바이스^기가지니MINI	https://gigagenie.kt.com/mini/main.do		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
507	ktcom_313	상품^AI^디바이스^지니TV셋톱박스	https://gigagenie.kt.com/main.do	https://m.gigagenie.kt.com/main.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
508	ktcom_314	상품^AI^디바이스^지니TV테이블	https://gigagenie.kt.com/tatv/main.do	https://m.gigagenie.kt.com/tatv/main.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
509	ktcom_315	상품^AI^디바이스^홈IoT	https://gigagenie.kt.com/partner/genieHomeIot.do	https://m.gigagenie.kt.com/partner/genieHomeIot.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
510	ktcom_316	상품^AI^서비스	http://gigagenie.kt.com/whyGenieService.do		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
511	ktcom_318	상품^AI^서비스^서비스안내^개인비서	https://gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=secretary	https://m.gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=secretary	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
512	ktcom_319	상품^AI^서비스^서비스안내^게임	https://gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=homeEnt	https://m.gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=homeEnt	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
513	ktcom_320	상품^AI^서비스^서비스안내^금융커머스	https://gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=finance	https://m.gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=finance	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
514	ktcom_321	상품^AI^서비스^서비스안내^라이프스타일	https://gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=lifestyle	https://m.gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=lifestyle	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
515	ktcom_322	상품^AI^서비스^서비스안내^미디어	https://gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=media	https://m.gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=media	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
516	ktcom_323	상품^AI^서비스^서비스안내^생활정보	https://gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=livingInfo	https://m.gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=livingInfo	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
517	ktcom_324	상품^AI^서비스^서비스안내^키즈	https://gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=kids	https://m.gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=kids	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
518	ktcom_325	상품^AI^서비스^서비스안내^편리한기능	https://gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=useful	https://m.gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=useful	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
519	ktcom_317	상품^AI^서비스^서비스안내^multi-agent	https://gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=alexa	https://m.gigagenie.kt.com/whyGenieServiceDetail.do?serviceCate=alexa	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
520	ktcom_333	상품^AI^솔루션^기가지니인사이드	https://gigagenie.kt.com/business/genieInside.do	https://m.gigagenie.kt.com/business/genieInside.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
521	ktcom_326	상품^AI^솔루션^AIAPI	https://gigagenie.kt.com/business/genieAiAPI.do	https://m.gigagenie.kt.com/business/genieAiAPI.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
522	ktcom_328	상품^AI^솔루션^AICare	https://gigagenie.kt.com/business/genieAiCare.do	https://m.gigagenie.kt.com/business/genieAiCare.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
523	ktcom_327	상품^AI^솔루션^AICC	https://gigagenie.kt.com/business/genieAICC.do	https://m.gigagenie.kt.com/business/genieAICC.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
524	ktcom_329	상품^AI^솔루션^AICodiny	https://gigagenie.kt.com/business/genieAiCodiny.do	https://m.gigagenie.kt.com/business/genieAiCodiny.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
525	ktcom_330	상품^AI^솔루션^AIPartner	https://gigagenie.kt.com/partner/geniePartner.do	https://m.gigagenie.kt.com/partner/geniePartner.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
526	ktcom_331	상품^AI^솔루션^AIRobot	https://gigagenie.kt.com/business/genieRobot.do		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
527	ktcom_332	상품^AI^솔루션^AISpace	https://gigagenie.kt.com/business/genieAiSpace.do	https://m.gigagenie.kt.com/business/genieAiSpace.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
528	ktcom_305	상품^AI^AI통화서비스^링고	https://gigagenie.kt.com/aiCallLingo.do	https://m.gigagenie.kt.com/aiCallLingo.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
529	ktcom_306	상품^AI^AI통화서비스^통화매니저	https://gigagenie.kt.com/aiCallManager.do	https://m.gigagenie.kt.com/aiCallManager.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
530	ktcom_307	상품^AI^AI통화서비스^통화비서	https://gigagenie.kt.com/aiCallSecretary.do	https://m.gigagenie.kt.com/aiCallSecretary.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
531	ktcom_308	상품^AI^Why기가지니^소개	https://gigagenie.kt.com/whyGenie.do	https://m.gigagenie.kt.com/whyGenie.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
532	ktcom_309	상품^AI^Why기가지니^자주하는질문	https://gigagenie.kt.com/whyGenieFaq.do	https://m.gigagenie.kt.com/whyGenieFaq.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
533	ktcom_341	상품^TV^부가서비스	https://product.kt.com/wDic/index.do?CateCode=6009	https://m.product.kt.com/wDic/index.do?CateCode=6009	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
534	ktcom_342	상품^TV^부가서비스^넷플릭스	https://product.kt.com/wDic/productDetail.do?ItemCode=1398&CateCode=6009&filter_code=22&option_code=41&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1398&CateCode=6009&filter_code=22&option_code=41&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
535	ktcom_343	상품^TV^부가서비스^디즈니+	https://product.kt.com/wDic/productDetail.do?ItemCode=1555&CateCode=6009&filter_code=22&option_code=41&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1555&CateCode=6009&filter_code=22&option_code=41&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
536	ktcom_344	상품^TV^부가서비스^반려견 TV	https://product.kt.com/wDic/productDetail.do?ItemCode=1318&CateCode=6009&filter_code=88&option_code=120&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1318&CateCode=6009&filter_code=88&option_code=120&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
537	ktcom_345	상품^TV^부가서비스^뽀로로핑크퐁BBC Kids캐리 TV 월정액	https://product.kt.com/wDic/productDetail.do?ItemCode=1317&CateCode=6009&filter_code=23&option_code=42&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1317&CateCode=6009&filter_code=23&option_code=42&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
538	ktcom_346	상품^TV^부가서비스^성인 19+ 영화 즐기기	https://product.kt.com/wDic/productDetail.do?ItemCode=1314&CateCode=6009&filter_code=22&option_code=41&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1314&CateCode=6009&filter_code=22&option_code=41&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
539	ktcom_347	상품^TV^부가서비스^영화 무제한 즐기기	https://product.kt.com/wDic/productDetail.do?ItemCode=1315&CateCode=6009&filter_code=22&option_code=41&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1315&CateCode=6009&filter_code=22&option_code=41&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
540	ktcom_348	상품^TV^부가서비스^운세방	https://product.kt.com/wDic/productDetail.do?ItemCode=1320&CateCode=6009&filter_code=88&option_code=120&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1320&CateCode=6009&filter_code=88&option_code=120&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
541	ktcom_349	상품^TV^부가서비스^종편 무제한 즐기기	https://product.kt.com/wDic/productDetail.do?ItemCode=1308&CateCode=6009&filter_code=21&option_code=40&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1308&CateCode=6009&filter_code=21&option_code=40&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
542	ktcom_350	상품^TV^부가서비스^지상파 무제한 즐기기	https://product.kt.com/wDic/productDetail.do?ItemCode=1307&CateCode=6009&filter_code=21&option_code=40&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1307&CateCode=6009&filter_code=21&option_code=40&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
543	ktcom_351	상품^TV^부가서비스^지상파+JTBC 무제한 즐기기	https://product.kt.com/wDic/productDetail.do?ItemCode=1463&CateCode=6009&filter_code=21&option_code=40&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1463&CateCode=6009&filter_code=21&option_code=40&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
544	ktcom_352	상품^TV^부가서비스^투니버스 월정액	https://product.kt.com/wDic/productDetail.do?ItemCode=1442&CateCode=6009&filter_code=23&option_code=42&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1442&CateCode=6009&filter_code=23&option_code=42&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
545	ktcom_353	상품^TV^부가서비스^티빙	https://product.kt.com/wDic/productDetail.do?ItemCode=1561&CateCode=6009&filter_code=22&option_code=41&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1561&CateCode=6009&filter_code=22&option_code=41&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
546	ktcom_354	상품^TV^부가서비스^프라임 키즈랜드팩	https://product.kt.com/wDic/productDetail.do?ItemCode=1311&CateCode=6009&filter_code=23&option_code=42&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1311&CateCode=6009&filter_code=22&option_code=41&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
547	ktcom_355	상품^TV^부가서비스^프라임무비 익스프레스	https://product.kt.com/wDic/productDetail.do?ItemCode=1461&CateCode=6009&filter_code=22&option_code=41&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1461&CateCode=6009&filter_code=22&option_code=41&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
548	ktcom_356	상품^TV^부가서비스^프라임무비팩	https://product.kt.com/wDic/productDetail.do?ItemCode=1309&CateCode=6009&filter_code=22&option_code=41&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1309&CateCode=6009&filter_code=22&option_code=41&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
549	ktcom_358	상품^TV^부가서비스^프라임슈퍼팩	https://product.kt.com/wDic/productDetail.do?ItemCode=1429&CateCode=6009&filter_code=22&option_code=41&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1429&CateCode=6009&filter_code=22&option_code=41&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
550	ktcom_357	상품^TV^부가서비스^프라임슈퍼CJENM팩	https://product.kt.com/wDic/productDetail.do?ItemCode=1552&CateCode=6009&filter_code=22&option_code=41&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1552&CateCode=6009&filter_code=22&option_code=41&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
551	ktcom_359	상품^TV^부가서비스^프라임아시아팩	https://product.kt.com/wDic/productDetail.do?ItemCode=1313&CateCode=6009&filter_code=22&option_code=41&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1313&CateCode=6009&filter_code=23&option_code=42&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
552	ktcom_360	상품^TV^부가서비스^프라임애니팩	https://product.kt.com/wDic/productDetail.do?ItemCode=1310&CateCode=6009&filter_code=23&option_code=42&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1310&CateCode=6009&filter_code=23&option_code=42&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
553	ktcom_336	상품^TV^부가서비스^CJ ENM + JTBC 같이즐기기	https://product.kt.com/wDic/productDetail.do?ItemCode=1374&CateCode=6009&filter_code=21&option_code=40&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1374&CateCode=6009&filter_code=21&option_code=40&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
554	ktcom_337	상품^TV^부가서비스^CJ ENM 무제한 즐기기	https://product.kt.com/wDic/productDetail.do?ItemCode=1312&CateCode=6009&filter_code=21&option_code=40&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1312&CateCode=6009&filter_code=21&option_code=40&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
555	ktcom_338	상품^TV^부가서비스^EBS키즈지니키즈	https://product.kt.com/wDic/productDetail.do?ItemCode=1316&CateCode=6009&filter_code=23&option_code=42&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1316&CateCode=6009&filter_code=23&option_code=42&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
556	ktcom_339	상품^TV^부가서비스^SPOTV Prime NOW	https://product.kt.com/wDic/productDetail.do?ItemCode=1609&CateCode=6009&filter_code=88&option_code=120&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1609&CateCode=6009&filter_code=88&option_code=120&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
557	ktcom_340	상품^TV^부가서비스^TJ노래방	https://product.kt.com/wDic/productDetail.do?ItemCode=1319&CateCode=6009&filter_code=88&option_code=120&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1319&CateCode=6009&filter_code=88&option_code=120&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
595	ktcom_841	혜택^이용혜택^장기고객감사드림프로그램	https://product.kt.com/benefit/membership/web/long_customer.html	https://m.product.kt.com/benefit/membership/mobile/long_customer.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
559	ktcom_366	상품^TV^요금제^지니 TV 탭 3	https://product.kt.com/wDic/productDetail.do?ItemCode=1443&CateCode=6008&filter_code=115&option_code=167&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1443&CateCode=6008&filter_code=115&option_code=167&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
560	ktcom_361	상품^TV^요금제^TV 일반	https://product.kt.com/wDic/productDetail.do?ItemCode=1518&CateCode=6008&filter_code=115&option_code=167&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1518&CateCode=6008&filter_code=115&option_code=167&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
561	ktcom_362	상품^TV^요금제^TV 초이스 스페셜	https://product.kt.com/wDic/productDetail.do?ItemCode=1516&CateCode=6008&filter_code=115&option_code=167&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1516&CateCode=6008&filter_code=115&option_code=167&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
562	ktcom_363	상품^TV^요금제^TV 초이스 프리미엄	https://product.kt.com/wDic/productDetail.do?ItemCode=1515&CateCode=6008&filter_code=115&option_code=167&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1515&CateCode=6008&filter_code=115&option_code=167&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
563	ktcom_364	상품^TV^요금제^TV 초이스 플러스	https://product.kt.com/wDic/productDetail.do?ItemCode=1517&CateCode=6008&filter_code=115&option_code=167&pageSize=10	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1517&CateCode=6008&filter_code=115&option_code=167&pageSize=10	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
564	ktcom_367	상품^TV^키즈초등서비스^키즈랜드	https://product.kt.com/wDic/productDetail.do?ItemCode=1243	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1243	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
565	ktcom_335	상품^TV^WhyGenieTV^소개	https://product.kt.com/wDic/productDetail.do?ItemCode=1163	https://m.product.kt.com/wDic/productDetail.do?ItemCode=1163	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
566	ktcom_334	상품^TV^WhyGenieTV^VOD	http://tv.kt.com/tv/vod/pVodInfo.asp		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
567	\N	혜택^이벤트/핫딜^진행중인 이벤트	https://event.kt.com/html/event/ongoing_event_list.html		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
568	ktcom_776	혜택^구매혜택^핸드폰가입쿠폰혜택^악세서리쿠폰	https://shop.kt.com/display/olhsPlan.do?plnDispNo=1424	https://m.shop.kt.com/display/olhsPlan.do?plnDispNo=1424	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
569	ktcom_777	혜택^구매혜택^핸드폰가입쿠폰혜택^쿠폰팩	https://shop.kt.com/display/olhsPlan.do?plnDispNo=1662	https://m.shop.kt.com/display/olhsPlan.do?plnDispNo=1662	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
570	ktcom_778	혜택^더보기^(구)멤버십마일리지	http://membership.kt.com/more/MembershipMileageInfo.do	http://m.membership.kt.com/more/MembershipMileageInfo.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
571	ktcom_779	혜택^더보기^비즈멤버십	http://membership.kt.com/more/BizMembershipInfo.do	http://m.membership.kt.com/more/BizMembershipInfo.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
572	ktcom_781	혜택^멤버십안내	https://membership.kt.com/guide/join/JoinForm.do		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
573	ktcom_782	혜택^멤버십안내^멤버십등급	https://membership.kt.com/guide/system/SystemInfo.do		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
574	ktcom_780	혜택^멤버십안내^FAQ	https://membership.kt.com/guide/faq/FAQList.do	https://m.membership.kt.com/guide/faq/FAQList.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
575	ktcom_783	혜택^멤버십할인^제휴브랜드	https://membership.kt.com/discount/partner/PartnerList.do	https://m.membership.kt.com/discount/partner/PartnerList.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
576	ktcom_784	혜택^멤버십할인^통신미디어	http://membership.kt.com/discount/comm/CommInfo.do	http://m.membership.kt.com/discount/comm/CommInfo.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
577	ktcom_785	혜택^영화공연^공연예매^공연예매메인	http://membership.kt.com/culture/show/ShowInfo.do	http://m.membership.kt.com/culture/show/ShowInfo.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
578	\N	혜택^영화공연^공연예매^공연예매메인^공지사항	https://kt.interpark.com/Partner/KT/Event/NoticeList.asp		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
579	ktcom_792	혜택^영화공연^공연예매^공연예매메인^서비스안내	https://kt.interpark.com/Partner/KT/MyTicket/TicketServiceInfo.asp		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
580	ktcom_793	혜택^영화공연^공연예매^공연예매메인^티켓예매가이드	https://kt.interpark.com/Partner/KT/MyTicket/TicketGuide.asp		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
581	ktcom_794	혜택^영화공연^영화예매^고객센터	https://membership.kt.com/culture/movie/CustomerCenterInfo.do	https://m.membership.kt.com/culture/movie/CustomerCenterInfo.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
582	ktcom_795	혜택^영화공연^영화예매^영화메인	https://membership.kt.com/culture/movie/MovieInfo.do	https://m.membership.kt.com/culture/movie/MovieInfo.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
583	ktcom_796	혜택^영화공연^영화예매^혜택이용안내	https://membership.kt.com/culture/movie/BenefitUseInfo.do	https://m.membership.kt.com/culture/movie/BenefitUseInfo.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
585	ktcom_831	혜택^이용안내^제휴혜택^전체	https://product.kt.com/benefit/membership/web/card.html?cardTab=1	https://m.product.kt.com/benefit/membership/mobile/card.html?cardTab=1	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
587	ktcom_829	혜택^이용안내^제휴혜택^NEW	https://product.kt.com/benefit/membership/web/card.html?cardTab=2	https://m.product.kt.com/benefit/membership/mobile/card.html?cardTab=2	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
588	ktcom_834	혜택^이용혜택^데이터혜택^데이터룰렛	https://product.kt.com/benefit/membership/web/membership03.html	https://m.product.kt.com/benefit/membership/mobile/membership03.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
589	ktcom_835	혜택^이용혜택^데이터혜택^데이터밀당	https://product.kt.com/benefit/membership/web/membership05.html	https://m.product.kt.com/benefit/membership/mobile/membership05.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
590	ktcom_836	혜택^이용혜택^데이터혜택^패밀리박스	https://product.kt.com/benefit/membership/web/membership06.html	https://m.product.kt.com/benefit/membership/mobile/membership06.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
593	ktcom_839	혜택^이용혜택^복지할인	https://product.kt.com/benefit/membership/web/welfare_sale.html	https://m.product.kt.com/benefit/membership/mobile/welfare_sale.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
599	ktcom_847	혜택^이용혜택^해외여행혜택	http://globalroaming.kt.com/benefit/main.asp		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
600	ktcom_848	혜택^이용혜택^해외여행혜택^굿럭	https://globalroaming.kt.com/benefit/reward.asp?bmode=golk		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
601	ktcom_849	혜택^이용혜택^해외여행혜택^롯데면세점	https://s.lottedfs.com/IExDE7cNK		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
602	ktcom_850	혜택^이용혜택^해외여행혜택^마이리얼트립	https://globalroaming.kt.com/benefit/reward.asp?bmode=ticket		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
603	ktcom_851	혜택^이용혜택^해외여행혜택^신세계면세점	https://benefit.kt.com/roaming/event/sdf/landing.asp		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
604	ktcom_852	혜택^이용혜택^해외여행혜택^아고다	https://globalroaming.kt.com/benefit/reward.asp?bmode=hotel3		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
605	ktcom_853	혜택^이용혜택^해외여행혜택^아껴드림	https://globalroaming.kt.com/benefit/reward.asp?bmode=svm		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
606	ktcom_854	혜택^이용혜택^해외여행혜택^우리은행	https://globalroaming.kt.com/benefit/reward.asp?bmode=exchange2		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
607	ktcom_855	혜택^이용혜택^해외여행혜택^익스피디아	https://globalroaming.kt.com/benefit/reward.asp?bmode=hotel		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
608	ktcom_856	혜택^이용혜택^해외여행혜택^현대면세점	https://globalroaming.kt.com/benefit/free.asp?bmode=dfree2		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
609	ktcom_857	혜택^이용혜택^해외여행혜택^호텔스닷컴	https://globalroaming.kt.com/benefit/reward.asp?bmode=hotel2		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
610	ktcom_845	혜택^이용혜택^해외여행혜택^Hertz	https://globalroaming.kt.com/benefit/reward.asp?bmode=rent		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
611	ktcom_846	혜택^이용혜택^해외여행혜택^KB국민은행	https://globalroaming.kt.com/benefit/reward.asp?bmode=exchange3		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
612	ktcom_858	혜택^이용혜택^홈코노미캠페인	https://product.kt.com/benefit/membership/web/homeco.html		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
613	ktcom_833	혜택^이용혜택^TV장기혜택	https://product.kt.com/benefit/membership/web/ollehtv_yonks.html		admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
614	ktcom_774	혜택^VIP멤버십^VIP초이스	http://membership.kt.com/vip/choice/ChoiceInfo.do	http://m.membership.kt.com/vip/choice/ChoiceInfo.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
615	ktcom_775	혜택^VIP멤버십^VVIP초이스	https://membership.kt.com/vip/choice/VvipChoiceInfo.do	https://m.membership.kt.com/vip/choice/VvipChoiceInfo.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
617	ktcom_13	Shop^마이샵이용안내^이용안내^핸드폰구매이용안내	https://shop.kt.com/support/shopMobileGuide.do	https://m.shop.kt.com/support/shopMobileGuide.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
618	ktcom_777	Shop^모바일가입^핸드폰가입혜택	https://shop.kt.com/display/olhsPlan.do?plnDispNo=1662	https://m.shop.kt.com/display/olhsPlan.do?plnDispNo=1662	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
619	ktcom_776	Shop^모바일가입^핸드폰가입혜택^KT닷컴 액세서리 쿠폰	https://shop.kt.com/display/olhsPlan.do?plnDispNo=1424	https://m.shop.kt.com/display/olhsPlan.do?plnDispNo=1424	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
620	ktcom_10	Shop^요고다이렉트^핸드폰등록및요금제변경	https://shop.kt.com/direct/directChangeRate.do	https://m.shop.kt.com/direct/directChangeRate.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
621	ktcom_2	Shop^USIMeSIM가입^데이터쉐어링가입	https://shop.kt.com/direct/directSharing.do	https://m.shop.kt.com/direct/directSharing.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
622	ktcom_3	Shop^USIMeSIM가입^듀얼번호가입	https://shop.kt.com/direct/directDual.do	https://m.shop.kt.com/direct/directDual.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
623	ktcom_4	Shop^USIMeSIM가입^선불USIM구매충전	https://shop.kt.com/unify/mobile.do?&category=usim	https://m.shop.kt.com/unify/mobile.do?&category=usim	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
624	ktcom_5	Shop^USIMeSIM가입^스마트기기요금제가입	https://shop.kt.com/direct/directSmart.do	https://m.shop.kt.com/direct/directSmart.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
625	ktcom_1	Shop^USIMeSIM가입^eSIM이동	https://shop.kt.com/direct/directEsimMove.do	https://m.shop.kt.com/direct/directEsimMove.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
626	ktcom_677	상품^소상공인^사장이지	https://product.kt.com/wDic/soho/marketing.do?itemCode=sajangeasy	https://m.product.kt.com/mDic/soho/marketing.do?itemCode=sajangeasy	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
627	ktcom_394	상품^로밍^로밍상품정보^데이터^Y함께쓰는로밍	https://globalroaming.kt.com/product/data/geu.asp	https://m.globalroaming.kt.com/product/data/geu.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
628	ktcom_395	상품^로밍^로밍상품정보^데이터^Y함께쓰는로밍(충전)	https://globalroaming.kt.com/product/data/togcharge.asp	https://m.globalroaming.kt.com/product/data/togcharge.asp	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
591	ktcom_837	혜택^이용혜택^만34세이하Y혜택^Y덤	https://product.kt.com/benefit/membership/web/y-bonus.html	https://m.product.kt.com/benefit/membership/mobile/y-bonus.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
584	ktcom_830	혜택^이용안내^제휴혜택^장기할부	https://product.kt.com/benefit/membership/web/card.html?cardTab=3	https://m.product.kt.com/benefit/membership/mobile/card.html?cardTab=3	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
586	ktcom_832	혜택^이용안내^제휴혜택^청구할인	https://product.kt.com/benefit/membership/web/card.html?cardTab=4	https://m.product.kt.com/benefit/membership/mobile/card.html?cardTab=4	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
592	ktcom_838	혜택^이용혜택^만34세이하Y혜택^Y박스	https://product.kt.com/benefit/membership/web/membership21.html	https://m.product.kt.com/benefit/membership/mobile/membership21.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
594	ktcom_840	혜택^이용혜택^인터넷할인혜택	https://product.kt.com/benefit/membership/web/membership09.html	https://m.product.kt.com/benefit/membership/mobile/membership09.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
597	ktcom_843	혜택^이용혜택^제휴혜택^제휴카드	https://product.kt.com/benefit/membership/web/card.html	https://m.product.kt.com/benefit/membership/mobile/card.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
598	ktcom_844	혜택^이용혜택^제휴혜택^포인트혜택	https://product.kt.com/benefit/membership/web/point.html	https://m.product.kt.com/benefit/membership/mobile/point.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
596	ktcom_842	혜택^이용혜택^제휴혜택^제휴상조	https://product.kt.com/benefit/membership/web/etc.html	https://m.product.kt.com/benefit/membership/mobile/etc.html	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
159	ktcom_439	상품^모바일^링투유벨소리^링투유벨소리설정	https://bellring.mobile.kt.com/web/index.do	https://m.bellring.mobile.kt.com/mobile/index.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
160	ktcom_440	상품^모바일^링투유벨소리^링투유인사말	https://bellring.mobile.kt.com/web/mentIndex.do	https://m.bellring.mobile.kt.com/mobile/mentIndex.do	admin	2025-09-01 15:03:53.419048+09	\N	2025-09-01 15:03:53.419048+09
\.


--
-- Data for Name: menu_manager_info; Type: TABLE DATA; Schema: crawler_mind; Owner: admin
--

COPY crawler_mind.menu_manager_info (id, menu_id, team_name, manager_names, created_by, created_at, updated_by, updated_at) FROM stdin;
29	31	수납기획팀	조복금	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
1	2	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
3	3	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
505	527	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
506	528	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
507	529	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
4	5	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
5	6	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
6	7	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
7	8	대면채널기획팀	조선희	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
8	9	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
9	10	대면채널기획팀	조선희	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
10	11	대면채널기획팀	조선희	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
11	12	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
12	13	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
13	14	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
14	15	대면채널기획팀	조선희	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
15	16	대면채널기획팀	조선희	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
16	17	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
17	18	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
18	19	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
19	20	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
20	21	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
21	22	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
22	23	대면채널기획팀	조선희	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
23	24	대면채널기획팀	조선희	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
24	25	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
25	26	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
26	27	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
27	28	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
28	29	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
30	32	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
31	33	수납가치팀	기희정	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
32	34	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
33	35	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
34	37	수납기획팀	조복금	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
35	38	수납기획팀	조복금	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
36	39	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
37	40	Billing기획팀	김대룡	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
38	41	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
39	42	디지털채널기획팀	장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
40	43	디지털채널기획팀	장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
41	44	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
42	45	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
43	46	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
44	47	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
45	48	대면채널관리팀	조선희	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
46	49	대면채널관리팀	조선희	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
47	50	무선요금혁신팀	김영옥/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
48	51	디지털채널기획팀	장은지/문지영	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
49	52	고객센터혁신팀	김한주	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
50	53	Billing기획팀	김대룡	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
51	54	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
52	55	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
54	617	디지털채널세일즈팀	김지범/박희지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
55	58	대면채널기획팀	고아란	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
56	59	고객센터혁신팀	김한주	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
57	60	디지털채널기획팀	장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
58	61	고객센터혁신팀	김한주	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
59	62	고객센터혁신팀	김지연	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
60	63	무선단말마케팅팀	오신택	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
61	64	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
62	65	기술지원팀	임재창	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
63	66	기술지원팀	임재창	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
64	67	미디어&통화사업지원팀	조미영	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
65	68	디지털채널기획팀 미디어&통화사업지원팀	문지영/장은지(TV) 오재규(WiFi)/오유진(인터넷전화)	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
66	69	기술지원팀	윤광열	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
67	70	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
68	71	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
69	72	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
70	73	디지털채널기획팀	최나리/안석/이우빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
72	75	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
73	76	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
155	161	성장서비스팀	강성환	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
153	159	성장서비스팀	강성환	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
601	624	디지털채널세일즈팀	김지범/박희지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
74	77	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
75	78	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
76	79	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
77	80	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
78	81	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
79	82	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
80	83	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
81	84	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
82	85	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
83	86	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
84	87	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
85	88	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
86	89	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
87	90	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
88	91	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
89	92	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
90	93	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
91	94	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
92	95	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
93	96	디지털채널기획팀	이한솔/안석	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
94	98	상품제휴팀	유지희/박정은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
95	99	무선요금혁신팀	강신제	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
96	100	고객인식개선팀	김영진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
97	101	대면채널기획팀	조선희	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
98	102	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
99	103	무선요금혁신팀	박현수/홍수아	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
100	104	무선요금혁신팀	박현수/홍수아	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
101	105	무선요금혁신팀	박현수/홍수아	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
102	106	무선요금혁신팀	박현수/홍수아	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
103	107	무선요금혁신팀	박현수/홍수아	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
104	108	무선요금혁신팀	박현수/홍수아	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
105	109	무선요금혁신팀	박현수/홍수아	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
106	110	무선요금혁신팀	박현수/홍수아	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
107	111	무선요금혁신팀	박현수/홍수아	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
108	112	무선요금혁신팀	박현수/홍수아	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
109	113	무선요금혁신팀	박현수/홍수아	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
110	114	무선요금혁신팀	박현수/홍수아	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
111	116	미디어&통화사업지원팀	김경지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
112	117	미디어&통화사업지원팀	김경지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
113	118	미디어&통화사업지원팀	김경지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
114	119	미디어&통화사업지원팀	김경지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
115	120	미디어&통화사업지원팀	김경지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
116	121	미디어&통화사업지원팀	김경지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
117	122	미디어&통화사업지원팀	김경지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
118	123	미디어&통화사업지원팀	김경지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
119	124	미디어&통화사업지원팀	김경지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
120	125	미디어&통화사업지원팀	김경지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
121	126	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
122	127	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
123	128	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
124	129	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
125	130	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
126	131	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
127	132	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
128	133	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
129	134	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
130	135	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
131	136	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
132	137	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
133	138	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
134	139	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
135	140	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
136	141	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
137	142	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
138	144	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
139	145	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
140	146	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
141	147	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
142	148	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
143	149	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
144	150	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
145	151	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
146	152	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
147	153	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
148	154	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
149	155	로밍사업팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
150	156	디지털채널세일즈팀	김준식/김유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
151	157	무선요금혁신팀	강신제	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
152	158	로밍서비스팀	최경향	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
154	160	성장서비스팀	강성환	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
156	162	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
157	163	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
158	164	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
159	165	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
160	166	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
161	167	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
162	168	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
163	169	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
164	170	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
165	171	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
166	172	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
167	173	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
168	174	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
169	175	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
170	176	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
171	177	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
172	178	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
173	179	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
174	180	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
175	181	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
176	182	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
177	183	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
178	184	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
179	185	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
180	186	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
181	187	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
182	188	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
183	189	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
184	190	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
185	191	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
186	192	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
187	193	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
188	194	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
189	195	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
190	196	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
191	197	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
192	198	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
193	199	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
194	200	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
195	201	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
196	202	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
197	203	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
198	204	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
199	205	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
200	206	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
201	207	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
202	208	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
203	209	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
204	210	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
205	211	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
206	212	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
207	213	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
208	214	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
209	215	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
210	216	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
211	217	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
212	218	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
213	219	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
214	220	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
215	221	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
216	222	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
217	223	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
218	224	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
219	225	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
220	226	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
421	440	인터넷사업지원팀	김한나	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
221	227	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
222	228	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
223	229	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
224	230	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
225	231	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
226	232	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
227	233	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
228	234	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
229	235	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
230	236	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
231	237	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
232	238	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
233	239	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
234	240	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
235	241	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
236	242	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
237	243	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
238	244	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
239	245	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
240	246	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
241	247	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
242	248	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
243	249	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
244	250	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
245	251	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
246	252	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
247	253	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
248	254	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
249	255	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
250	256	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
251	257	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
252	258	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
253	259	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
254	260	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
255	261	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
256	262	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
257	263	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
258	264	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
259	265	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
260	266	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
261	267	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
262	268	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
263	269	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
264	270	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
265	271	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
266	272	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
267	273	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
268	274	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
269	275	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
270	276	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
271	277	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
272	278	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
273	279	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
274	280	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
275	281	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
276	282	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
277	283	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
278	284	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
279	285	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
280	286	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
281	287	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
282	288	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
283	289	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
284	290	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
285	291	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
422	441	인터넷사업지원팀	김한나	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
286	292	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
287	293	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
288	294	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
289	295	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
290	296	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
291	297	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
292	298	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
293	299	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
294	300	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
295	301	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
296	302	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
297	303	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
298	304	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
299	305	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
300	306	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
301	307	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
302	308	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
303	309	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
304	310	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
305	311	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
306	312	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
307	313	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
308	314	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
309	315	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
310	316	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
311	317	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
312	318	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
313	319	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
314	320	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
315	321	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
316	322	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
317	323	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
318	324	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
319	325	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
320	326	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
321	327	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
322	328	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
323	329	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
324	330	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
325	331	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
326	332	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
327	333	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
328	334	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
329	335	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
330	336	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
410	429	유선요금혁신팀	최태식	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
331	337	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
332	338	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
333	339	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
334	340	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
335	341	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
336	342	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
337	343	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
338	344	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
339	345	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
340	346	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
341	347	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
342	348	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
343	349	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
344	350	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
345	351	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
346	352	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
347	353	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
348	354	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
349	355	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
350	356	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
351	357	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
352	358	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
353	359	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
354	360	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
355	361	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
356	362	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
357	363	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
358	364	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
359	365	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
360	366	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
361	367	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
362	369	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
363	370	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
364	371	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
365	372	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
366	373	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
367	374	무선요금혁신팀	이재상/김영옥/정태인/최상균/이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
368	375	디지털채널기획팀	문지영/장은지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
369	376	성장서비스팀	김세희/김주용/한주형/최상빈	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
370	377	기술지원팀	서현창	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
371	378	기술지원팀	서현창	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
372	379	기술지원팀	서현창	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
373	380	기술지원팀	서현창	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
374	381	기술지원팀	서현창	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
375	382	기술지원팀	서현창	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
376	383	기술지원팀	서현창	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
377	384	기술지원팀	서현창	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
378	385	기술지원팀	서현창	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
379	386	기술지원팀	서현창	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
380	387	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
381	388	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
382	389	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
383	390	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
384	392	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
385	393	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
386	394	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
387	397	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
388	400	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
389	405	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
390	407	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
391	408	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
392	409	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
393	410	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
394	411	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
395	412	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
396	413	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
397	414	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
398	415	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
399	417	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
400	418	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
401	419	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
402	420	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
403	421	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
404	423	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
405	424	인터넷사업지원팀	김한나	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
406	425	인터넷사업지원팀	김한나	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
407	426	인터넷사업지원팀	김한나	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
408	427	인터넷사업지원팀	김한나	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
409	428	유선요금혁신팀	최태식	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
411	430	유선요금혁신팀	최태식	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
412	431	유선요금혁신팀	최태식	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
413	432	유선요금혁신팀	최태식	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
414	433	유선요금혁신팀	최태식	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
415	434	유선요금혁신팀	최태식	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
416	435	유선요금혁신팀	최태식	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
417	436	유선요금혁신팀	최태식	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
418	437	유선요금혁신팀	최태식	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
419	438	유선요금혁신팀	최태식	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
420	439	인터넷사업지원팀	김한나	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
423	442	인터넷사업지원팀	김한나	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
424	443	인터넷사업지원팀	김한나	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
425	444	인터넷사업지원팀	김한나	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
426	445	인터넷사업지원팀	김한나	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
427	446	인터넷사업지원팀	김한나	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
428	447	인터넷사업지원팀	김한나	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
429	448	인터넷사업지원팀	김한나	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
430	449	인터넷사업지원팀	김한나	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
431	450	인터넷사업지원팀	김한나	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
432	451	인터넷사업지원팀	김한나	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
433	452	인터넷사업지원팀	김한나	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
434	453	인터넷사업지원팀	김한나	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
435	454	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
436	455	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
437	456	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
438	457	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
439	458	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
440	459	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
441	462	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
442	463	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
443	464	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
444	465	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
445	466	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
446	467	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
447	468	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
448	469	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
449	470	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
450	471	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
451	472	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
452	473	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
453	474	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
454	475	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
455	476	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
456	477	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
457	478	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
458	479	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
459	480	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
460	481	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
461	482	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
462	483	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
463	484	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
464	485	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
465	486	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
466	487	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
467	488	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
468	489	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
469	490	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
470	491	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
471	492	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
472	493	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
473	494	소상공인통화상품팀	이국희	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
474	495	소상공인통화상품팀	이국희	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
475	496	소상공인통화상품팀	이국희	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
476	497	미디어&통화사업지원팀	김경지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
477	498	미디어&통화사업지원팀	김경지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
478	499	미디어&통화사업지원팀	김경지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
479	501	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
480	502	미디어&통화사업지원팀	오유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
481	503	소상공인통화상품팀	이국희	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
482	504	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
483	505	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
484	506	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
485	507	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
486	508	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
487	509	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
488	510	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
489	511	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
490	512	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
491	513	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
492	514	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
493	515	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
494	516	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
495	517	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
496	518	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
497	519	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
498	520	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
499	521	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
500	522	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
501	523	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
502	524	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
503	525	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
504	526	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
508	530	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
509	531	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
510	532	미디어Agent기획팀	이미애	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
511	533	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
512	534	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
513	535	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
514	536	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
515	537	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
516	538	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
517	539	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
518	540	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
519	541	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
520	542	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
521	543	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
522	544	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
523	545	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
524	546	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
525	547	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
526	548	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
527	549	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
528	550	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
529	551	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
530	552	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
531	553	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
532	554	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
533	555	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
534	556	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
535	557	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
536	558	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
537	559	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
538	560	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
539	561	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
540	562	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
541	563	유선요금혁신팀	김민화/유해진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
542	564	키즈콘텐츠사업팀	윤은경/김은진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
543	565	콘텐츠사업팀	조승제	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
544	566	콘텐츠사업팀	조승제	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
547	570	멤버십서비스팀	이지선	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
548	571	멤버십서비스팀	이지선	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
549	572	멤버십서비스팀	이지선	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
550	573	멤버십서비스팀	이지선	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
551	574	멤버십서비스팀	이지선	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
552	575	멤버십서비스팀	이지선	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
553	576	멤버십서비스팀	이지선	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
554	577	멤버십서비스팀	이지선	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
555	578	멤버십서비스팀	이지선	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
556	579	멤버십서비스팀	이지선	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
557	580	멤버십서비스팀	이지선	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
558	581	멤버십서비스팀	이지선	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
559	582	멤버십서비스팀	이지선	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
560	583	멤버십서비스팀	이지선	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
561	584	상품제휴팀	김새봄이/김영휘	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
562	585	상품제휴팀	김새봄이/김영휘	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
563	586	상품제휴팀	김새봄이/김영휘	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
564	587	상품제휴팀	김새봄이/김영휘	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
565	588	무선요금혁신팀	이재상	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
566	589	무선요금혁신팀	이재상	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
567	590	통합마케팅팀	정기웅/ 라지선	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
568	591	무선요금혁신팀	이지은	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
569	592	Seg.마케팅팀	박희열	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
570	593	대면채널관리팀	조선희	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
571	594	인터넷사업지원팀	김한나	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
572	595	무선사업지원팀	이상희	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
573	596	상품제휴팀	김새봄이/김영휘	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
574	597	상품제휴팀	김새봄이/김영휘	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
575	598	상품제휴팀	김새봄이/김영휘	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
576	599	로밍서비스팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
577	600	로밍서비스팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
578	601	로밍서비스팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
579	602	로밍서비스팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
580	603	로밍서비스팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
581	604	로밍서비스팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
582	605	로밍서비스팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
583	606	로밍서비스팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
584	607	로밍서비스팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
585	608	로밍서비스팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
586	609	로밍서비스팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
587	610	로밍서비스팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
588	611	로밍서비스팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
589	612	무선요금혁신팀	박현수	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
590	613	미디어&통화사업지원팀	조미영	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
591	614	멤버십서비스팀	이지선	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
592	615	멤버십서비스팀	이지선	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
593	616	고객센터혁신팀	구나영	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
595	618	디지털채널세일즈팀	김준식/김유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
596	619	디지털채널세일즈팀	김준식/김유진	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
597	620	디지털채널세일즈팀	김지범/박희지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
598	621	디지털채널세일즈팀	김지범/박희지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
599	622	디지털채널세일즈팀	김지범/박희지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
600	623	디지털채널세일즈팀	김지범/박희지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
602	625	디지털채널세일즈팀	김지범/박희지	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
603	626	하이오더사업팀	이진석/정지영/정하윤	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
604	627	로밍서비스팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
605	628	로밍서비스팀	김민혜	admin	2025-09-02 18:54:40.082122+09	\N	2025-09-02 18:54:40.082122+09
606	1	디지털채널기획	문지영/장은지	admin	2025-09-02 19:04:13.332036+09	\N	2025-09-02 19:04:13.332036+09
607	56	고객센터혁신팀	구나영	admin	2025-09-02 19:33:50.784032+09	\N	2025-09-02 19:33:50.784032+09
608	57	디지털채널세일즈팀	김지범/박희지	admin	2025-09-02 19:35:04.264921+09	\N	2025-09-02 19:35:04.264921+09
609	74	디지털채널기획팀	이한솔/안석	admin	2025-09-02 19:35:53.923556+09	\N	2025-09-02 19:35:53.923556+09
\.


--
-- Data for Name: menu_permissions; Type: TABLE DATA; Schema: crawler_mind; Owner: admin
--

COPY crawler_mind.menu_permissions (menu_id, permission_id) FROM stdin;
1	1
2	4
2	7
4	8
5	9
6	8
7	11
\.


--
-- Data for Name: menus; Type: TABLE DATA; Schema: crawler_mind; Owner: admin
--

COPY crawler_mind.menus (id, parent_id, name, path, icon, order_index, is_active, is_visible, description, created_at) FROM stdin;
1	\N	홈	/	home	1	t	t	크롤링 메인 페이지	2025-09-16 14:44:56.862306
2	\N	RAG 시스템	/rag	document	2	t	t	RAG 데이터 관리 시스템	2025-09-16 14:44:56.862306
3	\N	메뉴 관리	\N	menu	3	t	t	메뉴 관리 시스템	2025-09-16 14:44:56.862306
4	3	메뉴 링크 관리	/menu-links	link	1	t	t	메뉴 링크 관리	2025-09-16 14:44:56.862306
5	3	메뉴 매니저 관리	/menu-managers	user	2	t	t	메뉴 매니저 관리	2025-09-16 14:44:56.862306
6	3	메뉴 트리뷰	/menu-links/tree	tree	3	t	t	메뉴 트리 구조 보기	2025-09-16 14:44:56.862306
7	\N	JSON 비교	/json-compare	compare	4	t	t	JSON 데이터 비교 도구	2025-09-16 14:44:56.862306
\.


--
-- Data for Name: permissions; Type: TABLE DATA; Schema: crawler_mind; Owner: admin
--

COPY crawler_mind.permissions (id, name, resource, action, description, is_active, created_at) FROM stdin;
1	crawler:read	crawler	read	크롤링 결과 조회	t	2025-09-16 14:44:56.710586
2	crawler:write	crawler	write	크롤링 실행	t	2025-09-16 14:44:56.710586
3	crawler:delete	crawler	delete	크롤링 결과 삭제	t	2025-09-16 14:44:56.710586
4	rag:read	rag	read	RAG 데이터 조회	t	2025-09-16 14:44:56.710586
5	rag:write	rag	write	RAG 데이터 업로드	t	2025-09-16 14:44:56.710586
6	rag:delete	rag	delete	RAG 데이터 삭제	t	2025-09-16 14:44:56.710586
7	rag:search	rag	search	RAG 검색 실행	t	2025-09-16 14:44:56.710586
8	menu:read	menu	read	메뉴 조회	t	2025-09-16 14:44:56.710586
9	menu:write	menu	write	메뉴 수정	t	2025-09-16 14:44:56.710586
10	menu:delete	menu	delete	메뉴 삭제	t	2025-09-16 14:44:56.710586
11	json:read	json	read	JSON 비교 조회	t	2025-09-16 14:44:56.710586
12	json:write	json	write	JSON 비교 실행	t	2025-09-16 14:44:56.710586
13	system:admin	system	admin	시스템 관리	t	2025-09-16 14:44:56.710586
14	system:monitor	system	monitor	시스템 모니터링	t	2025-09-16 14:44:56.710586
15	system:config	system	config	시스템 설정	t	2025-09-16 14:44:56.710586
\.


--
-- Data for Name: role_permissions; Type: TABLE DATA; Schema: crawler_mind; Owner: admin
--

COPY crawler_mind.role_permissions (role_name, permission_id, assigned_at) FROM stdin;
admin	1	2025-09-16 14:44:56.98078
admin	2	2025-09-16 14:44:56.98078
admin	3	2025-09-16 14:44:56.98078
admin	4	2025-09-16 14:44:56.98078
admin	5	2025-09-16 14:44:56.98078
admin	6	2025-09-16 14:44:56.98078
admin	7	2025-09-16 14:44:56.98078
admin	8	2025-09-16 14:44:56.98078
admin	9	2025-09-16 14:44:56.98078
admin	10	2025-09-16 14:44:56.98078
admin	11	2025-09-16 14:44:56.98078
admin	12	2025-09-16 14:44:56.98078
admin	13	2025-09-16 14:44:56.98078
admin	14	2025-09-16 14:44:56.98078
admin	15	2025-09-16 14:44:56.98078
user	1	2025-09-16 14:44:57.143078
user	4	2025-09-16 14:44:57.143078
user	7	2025-09-16 14:44:57.143078
user	8	2025-09-16 14:44:57.143078
user	11	2025-09-16 14:44:57.143078
manager	1	2025-09-16 14:44:57.174388
manager	2	2025-09-16 14:44:57.174388
manager	4	2025-09-16 14:44:57.174388
manager	5	2025-09-16 14:44:57.174388
manager	8	2025-09-16 14:44:57.174388
manager	9	2025-09-16 14:44:57.174388
manager	11	2025-09-16 14:44:57.174388
manager	12	2025-09-16 14:44:57.174388
manager	14	2025-09-16 14:44:57.174388
viewer	1	2025-09-16 14:44:57.264082
viewer	4	2025-09-16 14:44:57.264082
viewer	8	2025-09-16 14:44:57.264082
viewer	11	2025-09-16 14:44:57.264082
guest	1	2025-09-16 14:44:57.625609
guest	7	2025-09-16 14:44:57.625609
guest	11	2025-09-16 14:44:57.625609
analyst	1	2025-09-16 14:44:57.887617
analyst	4	2025-09-16 14:44:57.887617
analyst	7	2025-09-16 14:44:57.887617
analyst	11	2025-09-16 14:44:57.887617
analyst	12	2025-09-16 14:44:57.887617
analyst	14	2025-09-16 14:44:57.887617
\.


--
-- Name: menu_links_id_seq; Type: SEQUENCE SET; Schema: crawler_mind; Owner: admin
--

SELECT pg_catalog.setval('crawler_mind.menu_links_id_seq', 638, true);


--
-- Name: menu_manager_info_id_seq; Type: SEQUENCE SET; Schema: crawler_mind; Owner: admin
--

SELECT pg_catalog.setval('crawler_mind.menu_manager_info_id_seq', 617, true);


--
-- Name: menus_id_seq; Type: SEQUENCE SET; Schema: crawler_mind; Owner: admin
--

SELECT pg_catalog.setval('crawler_mind.menus_id_seq', 7, true);


--
-- Name: permissions_id_seq; Type: SEQUENCE SET; Schema: crawler_mind; Owner: admin
--

SELECT pg_catalog.setval('crawler_mind.permissions_id_seq', 15, true);


--
-- Name: menu_links menu_links_pkey; Type: CONSTRAINT; Schema: crawler_mind; Owner: admin
--

ALTER TABLE ONLY crawler_mind.menu_links
    ADD CONSTRAINT menu_links_pkey PRIMARY KEY (id);


--
-- Name: menu_manager_info menu_manager_info_menu_id_key; Type: CONSTRAINT; Schema: crawler_mind; Owner: admin
--

ALTER TABLE ONLY crawler_mind.menu_manager_info
    ADD CONSTRAINT menu_manager_info_menu_id_key UNIQUE (menu_id);


--
-- Name: menu_manager_info menu_manager_info_pkey; Type: CONSTRAINT; Schema: crawler_mind; Owner: admin
--

ALTER TABLE ONLY crawler_mind.menu_manager_info
    ADD CONSTRAINT menu_manager_info_pkey PRIMARY KEY (id);


--
-- Name: menu_permissions menu_permissions_pkey; Type: CONSTRAINT; Schema: crawler_mind; Owner: admin
--

ALTER TABLE ONLY crawler_mind.menu_permissions
    ADD CONSTRAINT menu_permissions_pkey PRIMARY KEY (menu_id, permission_id);


--
-- Name: menus menus_pkey; Type: CONSTRAINT; Schema: crawler_mind; Owner: admin
--

ALTER TABLE ONLY crawler_mind.menus
    ADD CONSTRAINT menus_pkey PRIMARY KEY (id);


--
-- Name: permissions permissions_name_key; Type: CONSTRAINT; Schema: crawler_mind; Owner: admin
--

ALTER TABLE ONLY crawler_mind.permissions
    ADD CONSTRAINT permissions_name_key UNIQUE (name);


--
-- Name: permissions permissions_pkey; Type: CONSTRAINT; Schema: crawler_mind; Owner: admin
--

ALTER TABLE ONLY crawler_mind.permissions
    ADD CONSTRAINT permissions_pkey PRIMARY KEY (id);


--
-- Name: role_permissions role_permissions_pkey; Type: CONSTRAINT; Schema: crawler_mind; Owner: admin
--

ALTER TABLE ONLY crawler_mind.role_permissions
    ADD CONSTRAINT role_permissions_pkey PRIMARY KEY (role_name, permission_id);


--
-- Name: idx_menu_permissions_menu_id; Type: INDEX; Schema: crawler_mind; Owner: admin
--

CREATE INDEX idx_menu_permissions_menu_id ON crawler_mind.menu_permissions USING btree (menu_id);


--
-- Name: idx_menu_permissions_permission_id; Type: INDEX; Schema: crawler_mind; Owner: admin
--

CREATE INDEX idx_menu_permissions_permission_id ON crawler_mind.menu_permissions USING btree (permission_id);


--
-- Name: idx_menus_active; Type: INDEX; Schema: crawler_mind; Owner: admin
--

CREATE INDEX idx_menus_active ON crawler_mind.menus USING btree (is_active);


--
-- Name: idx_menus_order_index; Type: INDEX; Schema: crawler_mind; Owner: admin
--

CREATE INDEX idx_menus_order_index ON crawler_mind.menus USING btree (order_index);


--
-- Name: idx_menus_parent_id; Type: INDEX; Schema: crawler_mind; Owner: admin
--

CREATE INDEX idx_menus_parent_id ON crawler_mind.menus USING btree (parent_id);


--
-- Name: idx_menus_path; Type: INDEX; Schema: crawler_mind; Owner: admin
--

CREATE INDEX idx_menus_path ON crawler_mind.menus USING btree (path) WHERE (path IS NOT NULL);


--
-- Name: idx_menus_visible; Type: INDEX; Schema: crawler_mind; Owner: admin
--

CREATE INDEX idx_menus_visible ON crawler_mind.menus USING btree (is_visible);


--
-- Name: idx_permissions_active; Type: INDEX; Schema: crawler_mind; Owner: admin
--

CREATE INDEX idx_permissions_active ON crawler_mind.permissions USING btree (is_active);


--
-- Name: idx_permissions_name; Type: INDEX; Schema: crawler_mind; Owner: admin
--

CREATE INDEX idx_permissions_name ON crawler_mind.permissions USING btree (name);


--
-- Name: idx_permissions_resource_action; Type: INDEX; Schema: crawler_mind; Owner: admin
--

CREATE INDEX idx_permissions_resource_action ON crawler_mind.permissions USING btree (resource, action);


--
-- Name: idx_role_permissions_permission_id; Type: INDEX; Schema: crawler_mind; Owner: admin
--

CREATE INDEX idx_role_permissions_permission_id ON crawler_mind.role_permissions USING btree (permission_id);


--
-- Name: idx_role_permissions_role_name; Type: INDEX; Schema: crawler_mind; Owner: admin
--

CREATE INDEX idx_role_permissions_role_name ON crawler_mind.role_permissions USING btree (role_name);


--
-- Name: menu_manager_info menu_manager_info_menu_id_fkey; Type: FK CONSTRAINT; Schema: crawler_mind; Owner: admin
--

ALTER TABLE ONLY crawler_mind.menu_manager_info
    ADD CONSTRAINT menu_manager_info_menu_id_fkey FOREIGN KEY (menu_id) REFERENCES crawler_mind.menu_links(id) ON DELETE CASCADE;


--
-- Name: menu_permissions menu_permissions_menu_id_fkey; Type: FK CONSTRAINT; Schema: crawler_mind; Owner: admin
--

ALTER TABLE ONLY crawler_mind.menu_permissions
    ADD CONSTRAINT menu_permissions_menu_id_fkey FOREIGN KEY (menu_id) REFERENCES crawler_mind.menus(id) ON DELETE CASCADE;


--
-- Name: menu_permissions menu_permissions_permission_id_fkey; Type: FK CONSTRAINT; Schema: crawler_mind; Owner: admin
--

ALTER TABLE ONLY crawler_mind.menu_permissions
    ADD CONSTRAINT menu_permissions_permission_id_fkey FOREIGN KEY (permission_id) REFERENCES crawler_mind.permissions(id) ON DELETE CASCADE;


--
-- Name: menus menus_parent_id_fkey; Type: FK CONSTRAINT; Schema: crawler_mind; Owner: admin
--

ALTER TABLE ONLY crawler_mind.menus
    ADD CONSTRAINT menus_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES crawler_mind.menus(id) ON DELETE CASCADE;


--
-- Name: role_permissions role_permissions_permission_id_fkey; Type: FK CONSTRAINT; Schema: crawler_mind; Owner: admin
--

ALTER TABLE ONLY crawler_mind.role_permissions
    ADD CONSTRAINT role_permissions_permission_id_fkey FOREIGN KEY (permission_id) REFERENCES crawler_mind.permissions(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict s05W6zfdVqFNmpMP0rGVSQn3xm3zbbCCpeu9FFCLz8LFniIYuiXC0OLSDGj3TM5

