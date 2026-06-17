import streamlit as st
import pandas as pd
import boto3
import io
import requests
import plotly.express as px
from datetime import datetime

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="NYC Taxi Platform",
    page_icon="🚕",
    layout="wide"
)

BUCKET = "nyc-taxi-platform"
API_URL = "https://thg365gege.execute-api.eu-west-3.amazonaws.com/prod"
AWS_REGION = "eu-west-3"

# =========================
# HELPERS
# =========================
@st.cache_data(ttl=300)
def load_s3_parquet(prefix):
    s3 = boto3.client("s3", region_name=AWS_REGION)
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=BUCKET, Prefix=prefix)
    dfs = []
    for page in pages:
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".parquet"):
                r = s3.get_object(Bucket=BUCKET, Key=obj["Key"])
                dfs.append(pd.read_parquet(io.BytesIO(r["Body"].read())))
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

@st.cache_data(ttl=30)
def load_realtime():
    try:
        r = requests.get(f"{API_URL}/realtime", timeout=5)
        return r.json()
    except:
        return {"events_count": 0, "latest_events": []}

# =========================
# HEADER
# =========================
st.title("🚕 NYC Taxi Data Platform")
st.caption(f"Architecture Médaillon AWS · Mise à jour: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
st.divider()

# =========================
# TABS
# =========================
tab1, tab2, tab3 = st.tabs(["📊 KPIs Batch", "🌤️ Météo", "⚡ Streaming Temps Réel"])

# --- TAB 1 ---
with tab1:
    st.subheader("KPIs Journaliers — Janvier 2024")
    with st.spinner("Chargement Gold S3..."):
        df_daily = load_s3_parquet("gold/kpi_daily/")
        df_zone = load_s3_parquet("gold/kpi_zone/")

    if not df_daily.empty:
        df_daily["day"] = pd.to_datetime(df_daily["day"])
        df_daily = df_daily.sort_values("day")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🚗 Total Courses", f"{int(df_daily['nb_trips'].sum()):,}")
        col2.metric("💰 Tarif Moyen", f"${df_daily['avg_fare_usd'].mean():.2f}")
        col3.metric("📏 Distance Moy.", f"{df_daily['avg_distance_km'].mean():.2f} km")
        col4.metric("💵 Revenus Totaux", f"${df_daily['total_revenue_usd'].sum():,.0f}")

        st.plotly_chart(px.line(df_daily, x="day", y="nb_trips",
            title="Courses par jour", color_discrete_sequence=["#F6C90E"]),
            use_container_width=True)

        c1, c2 = st.columns(2)
        c1.plotly_chart(px.bar(df_daily, x="day", y="total_revenue_usd",
            title="Revenus journaliers ($)", color_discrete_sequence=["#3D9970"]),
            use_container_width=True)
        c2.plotly_chart(px.line(df_daily, x="day", y="avg_fare_usd",
            title="Tarif moyen ($)", color_discrete_sequence=["#FF4136"]),
            use_container_width=True)

        if not df_zone.empty:
            st.subheader("Top 20 Zones")
            df_top = df_zone.sort_values("nb_trips", ascending=False).head(20)
            st.plotly_chart(px.bar(df_top, x="zone_id", y="nb_trips",
                title="Courses par zone", color="nb_trips",
                color_continuous_scale="Viridis"), use_container_width=True)
    else:
        st.warning("Aucune donnée Gold. Lance le Glue Pipeline.")

# --- TAB 2 ---
with tab2:
    st.subheader("Données Météo NYC")
    with st.spinner("Chargement Silver S3..."):
        df_weather = load_s3_parquet("silver/weather_clean/")

    if not df_weather.empty:
        st.write(f"**{len(df_weather):,} enregistrements**")
        if "temperature_2m" in df_weather.columns:
            c1, c2, c3 = st.columns(3)
            c1.metric("🌡️ Moy.", f"{df_weather['temperature_2m'].mean():.1f}°C")
            c2.metric("🔴 Max.", f"{df_weather['temperature_2m'].max():.1f}°C")
            c3.metric("🔵 Min.", f"{df_weather['temperature_2m'].min():.1f}°C")
            st.plotly_chart(px.line(df_weather.reset_index(), y="temperature_2m",
                title="Température (°C)", color_discrete_sequence=["#FF851B"]),
                use_container_width=True)
        if "precipitation" in df_weather.columns:
            st.metric("🌧️ Précipitations totales", f"{df_weather['precipitation'].sum():.1f} mm")
    else:
        st.warning("Aucune donnée météo.")

# --- TAB 3 ---
with tab3:
    st.subheader("⚡ Événements Streaming Kafka → DynamoDB")
    if st.button("🔄 Rafraîchir"):
        st.cache_data.clear()

    realtime = load_realtime()
    st.metric("📡 Événements en base", realtime.get("events_count", 0))

    events = realtime.get("latest_events", [])
    if events:
        df_rt = pd.DataFrame(events)
        for col in ["fare", "speed", "pickup_lat", "pickup_lon"]:
            if col in df_rt.columns:
                df_rt[col] = pd.to_numeric(df_rt[col], errors="coerce")

        st.dataframe(df_rt[["taxi_id", "fare", "speed", "pickup_lat", "pickup_lon", "ingested_at"]],
            use_container_width=True)

        c1, c2 = st.columns(2)
        c1.plotly_chart(px.histogram(df_rt, x="fare", title="Distribution des tarifs",
            color_discrete_sequence=["#F6C90E"], nbins=20), use_container_width=True)
        c2.plotly_chart(px.scatter(df_rt, x="pickup_lon", y="pickup_lat",
            size="fare", color="speed", title="Positions départ (Manhattan)",
            color_continuous_scale="RdYlGn"), use_container_width=True)
    else:
        st.info("Lance le streaming Kafka sur l'EC2 pour voir les données.")
