import json
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# 1. 스트림릿 페이지 기본 설정 (와이드 레이아웃 사용)
st.set_page_config(
    page_title="전국 고령화 지도", page_icon="🗺️", layout="wide"
)

st.title("🗺️ 대한민국 시군구 고령화율 지도")
st.markdown(
    "가장 최신 연도 데이터를 바탕으로 전국 시군구별 65세 이상 인구 비율을"
    " 시각화한 앱입니다."
)


# 2. 데이터 로드 함수 (속도 향상을 위해 캐싱 적용)
@st.cache_data
def load_data():
  # 인구 데이터 URL (gzip 압축된 CSV)
  pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
  df_pop = pd.read_csv(pop_url, dtype={"코드": str})

  # 지도 경계 GeoJSON 데이터 URL
  geo_url = (
      "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
  )
  response = requests.get(geo_url)
  geojson_data = response.json()

  return df_pop, geojson_data


# 데이터 불러오기 실행
with st.spinner("데이터를 불러오는 중입니다... 잠시만 기다려주세요."):
  df_pop, sigungu_geojson = load_data()

# 3. 데이터 전처리
# 가장 최신 연도 추출
latest_year = df_pop["연도"].max()
st.info(f"📅 적용된 데이터 기준 연도: **{latest_year}년**")

df_latest = df_pop[df_pop["연도"] == latest_year].copy()

# 행정동 코드(10자리) 중 앞 5자리를 잘라내어 시군구 코드로 지정
df_latest["sigungu_code"] = df_latest["코드"].str.slice(0, 5)

# '계_'로 시작하고 '세'가 포함된 연령별 인구 컬럼 추출
age_columns = [
    col for col in df_latest.columns if col.startswith("계_") and "세" in col
]


# 65세 이상 여부를 판단하는 함수
def is_over_65(col_name):
  import re

  nums = re.findall(r"\d+", col_name)
  if nums:
    return int(nums[0]) >= 65
  return False


# 65세 이상 컬럼만 골라내기
cols_65_plus = [col for col in age_columns if is_over_65(col)]

# 시군구별 총인구 및 65세 이상 인구 합산
df_latest["총인구"] = df_latest[age_columns].sum(axis=1)
df_latest["65세이상_인구"] = df_latest[cols_65_plus].sum(axis=1)

sigungu_df = (
    df_latest.groupby("sigungu_code")
    .agg({"시도": "first", "시군구": "first", "총인구": "sum", "65세이상_인구": "sum"})
    .reset_index()
)

# 고령화율(%) 계산
sigungu_df["고령화율"] = (
    sigungu_df["65세이상_인구"] / sigungu_df["총인구"]
) * 100


# 4. 5단계 구간 분류 함수 (경계값: 19%, 23%, 28%, 38%)
def categorize_aging(rate):
  if rate < 19:
    return "19% 미만"
  elif rate < 23:
    return "19% ~ 23%"
  elif rate < 28:
    return "23% ~ 28%"
  elif rate < 38:
    return "28% ~ 38%"
  else:
    return "38% 이상"


sigungu_df["고령화구간"] = sigungu_df["고령화율"].apply(categorize_aging)

# 범례 순서 정렬을 위한 카테고리 지정
bin_order = [
    "19% 미만",
    "19% ~ 23%",
    "23% ~ 28%",
    "28% ~ 38%",
    "38% 이상",
]
sigungu_df["고령화구간"] = pd.Categorical(
    sigungu_df["고령화구간"], categories=bin_order, ordered=True
)

# 5. Plotly 단계구분도(Choropleth Map) 생성
fig = px.choropleth(
    sigungu_df,
    geojson=sigungu_geojson,
    locations="sigungu_code",
    featureidkey="properties.코드",
    color="고령화구간",
    color_discrete_sequence=px.colors.sequential.YlOrRd,  # 옅은색에서 진한색으로
    hover_name="시군구",
    hover_data={"시도": True, "고령화율": ":.2f", "sigungu_code": False},
    labels={"고령화구간": "고령화율 구간", "시도": "시도", "고령화율": "고령화율(%)"},
)

# 지도 배경 타일 없이 경계선만 깔끔하게 표시
fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(
    margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=600, legend_title="고령화율"
)

# 스트림릿 화면에 지도 출력
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.subheader("📊 시군구 고령화율 순위 (Top 10 & Bottom 10)")

# 6. 지도 아래 표 두 개를 나란히 배치
col1, col2 = st.columns(2)

with col1:
  st.markdown("### 🔴 고령화율 높은 곳 Top 10")
  top_10 = (
      sigungu_df.sort_values(by="고령화율", ascending=False)
      .head(10)[["시도", "시군구", "고령화율"]]
      .reset_index(drop=True)
  )
  top_10["고령화율"] = top_10["고령화율"].round(2).astype(str) + "%"
  st.dataframe(top_10, use_container_width=True)

with col2:
  st.markdown("### 🔵 고령화율 낮은 곳 Top 10")
  bottom_10 = (
      sigungu_df.sort_values(by="고령화율", ascending=True)
      .head(10)[["시도", "시군구", "고령화율"]]
      .reset_index(drop=True)
  )
  bottom_10["고령화율"] = bottom_10["고령화율"].round(2).astype(str) + "%"
  st.dataframe(bottom_10, use_container_width=True)
