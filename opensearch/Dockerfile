FROM opensearchproject/opensearch:2.13.0

# analysis-nori 플러그인 설치 (한국어 형태소 분석기)
RUN /usr/share/opensearch/bin/opensearch-plugin install --batch analysis-nori

# 플러그인 설치 확인
RUN /usr/share/opensearch/bin/opensearch-plugin list

# 기본 설정은 베이스 이미지와 동일하게 유지
USER 1000
EXPOSE 9200 9300
WORKDIR /usr/share/opensearch
CMD ["./opensearch-docker-entrypoint.sh"]
