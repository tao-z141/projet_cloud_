import streamlit as st
import pandas as pd
import boto3
import io
import os
import requests
import plotly.express as px
from datetime import datetime

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="NYC Taxi Platform", page_icon="🚕", layout="wide")

BUCKET = "nyc-taxi-platform"
API_URL = "https://thg365gege.execute-api.eu-west-3.amazonaws.com/prod"
AWS_REGION = "eu-west-3"

AWS_KEY = st.secrets.get("AWS_ACCESS_KEY_ID", os.environ.get("AWS_ACCESS_KEY_ID"))
AWS_SECRET = st.secrets.get("AWS_SECRET_ACCESS_KEY", os.environ.get("AWS_SECRET_ACCESS_KEY"))

# =========================
# HELPERS
# =========================
@st.cache_data(ttl=300)
def load_s3_parquet(prefix):
    s3 = boto3.client("s3", region_name=AWS_REGION,
        aws_access_key_id=AWS_KEY, aws_secret_access_key=AWS_SECRET)
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=BUCKET, Prefix=prefix)
    dfs = []
    for page in pages:
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".parquet"):
                r = s3.get_object(Bucket=BUCKET, Key=obj["Key"])
                dfs.append(pd.read_parquet(io.BytesIO(r["Body"].read())))
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

@st.cache_data(ttl=3600)
def load_zone_lookup():
    """Fichier de référence NYC TLC — noms des zones"""
    url = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
    return pd.read_csv(url)

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

tab1, tab2, tab3 = st.tabs(["📊 KPIs Batch", "🌤️ Météo & Corrélations", "⚡ Streaming Temps Réel"])

# =========================
# TAB 1 — KPIs BATCH
# =========================
with tab1:
    st.subheader("KPIs Journaliers — Janvier 2024")

    with st.spinner("Chargement Gold S3..."):
        df_daily = load_s3_parquet("gold/kpi_daily/")
        df_zone = load_s3_parquet("gold/kpi_zone/")
        zones = load_zone_lookup()

    if not df_daily.empty:
        df_daily["day"] = pd.to_datetime(df_daily["day"])
        df_daily = df_daily.sort_values("day")

        # Filtrer dates aberrantes (garder janvier 2024)
        df_daily = df_daily[
            (df_daily["day"] >= "2024-01-01") &
            (df_daily["day"] <= "2024-01-31")
        ]

        # KPI Cards
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🚗 Total Courses", f"{int(df_daily['nb_trips'].sum()):,}")
        col2.metric("💰 Tarif Moyen", f"${df_daily['avg_fare_usd'].mean():.2f}")
        col3.metric("📏 Distance Moy.", f"{df_daily['avg_distance_km'].mean():.2f} km")
        col4.metric("💵 Revenus Totaux", f"${df_daily['total_revenue_usd'].sum():,.0f}")

        # Courbe courses par jour
        st.plotly_chart(px.line(df_daily, x="day", y="nb_trips",
            title="📈 Nombre de courses par jour — Janvier 2024",
            labels={"day": "Date", "nb_trips": "Courses"},
            color_discrete_sequence=["#F6C90E"]), use_container_width=True)

        c1, c2 = st.columns(2)
        c1.plotly_chart(px.bar(df_daily, x="day", y="total_revenue_usd",
            title="💵 Revenus journaliers ($)",
            labels={"day": "Date", "total_revenue_usd": "Revenus ($)"},
            color_discrete_sequence=["#3D9970"]), use_container_width=True)
        c2.plotly_chart(px.line(df_daily, x="day", y="avg_fare_usd",
            title="💰 Tarif moyen par jour ($)",
            labels={"day": "Date", "avg_fare_usd": "Tarif ($)"},
            color_discrete_sequence=["#FF4136"]), use_container_width=True)

        # Top zones avec noms
        if not df_zone.empty and not zones.empty:
            st.subheader("🗺️ Top 20 Zones de départ — NYC")

            # Jointure avec les noms de zones
            df_zone_named = df_zone.merge(
                zones[["LocationID", "Zone", "Borough"]],
                left_on="zone_id",
                right_on="LocationID",
                how="left"
            )
            df_zone_named["label"] = df_zone_named["Zone"].fillna(
                df_zone_named["zone_id"].astype(str)
            )

            df_top = df_zone_named.sort_values("nb_trips", ascending=False).head(20)

            st.plotly_chart(px.bar(df_top, x="label", y="nb_trips",
                title="Courses par zone (Top 20)",
                color="Borough",
                labels={"label": "Zone", "nb_trips": "Nombre de courses"},
                color_discrete_sequence=px.colors.qualitative.Set2),
                use_container_width=True)

            # Tableau détaillé
            st.dataframe(
                df_top[["Zone", "Borough", "nb_trips", "avg_fare_usd", "total_revenue_usd"]]
                .rename(columns={
                    "Zone": "Zone", "Borough": "Arrondissement",
                    "nb_trips": "Courses", "avg_fare_usd": "Tarif moy. ($)",
                    "total_revenue_usd": "Revenus ($)"
                }),
                use_container_width=True
            )
    else:
        st.warning("Aucune donnée Gold. Lance le Glue Pipeline.")

# =========================
# TAB 2 — MÉTÉO & CORRÉLATIONS
# =========================
with tab2:
    st.subheader("🌤️ Météo NYC — Janvier 2024 (Historique Open-Meteo)")

    with st.spinner("Chargement données météo..."):
        df_weather = load_s3_parquet("silver/weather_clean/")
        df_daily_corr = load_s3_parquet("gold/kpi_daily/")

    if not df_weather.empty:
        st.success(f"✅ {len(df_weather):,} enregistrements horaires chargés")

        if "temperature_2m" in df_weather.columns:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🌡️ Température moy.", f"{df_weather['temperature_2m'].mean():.1f}°C")
            c2.metric("🔴 Température max.", f"{df_weather['temperature_2m'].max():.1f}°C")
            c3.metric("🔵 Température min.", f"{df_weather['temperature_2m'].min():.1f}°C")
            if "precipitation" in df_weather.columns:
                c4.metric("🌧️ Précipitations", f"{df_weather['precipitation'].sum():.1f} mm")

            # Courbe température horaire
            st.plotly_chart(px.line(df_weather, x="datetime", y="temperature_2m",
                title="🌡️ Température horaire NYC — Janvier 2024 (°C)",
                labels={"datetime": "Date", "temperature_2m": "Température (°C)"},
                color_discrete_sequence=["#FF851B"]), use_container_width=True)

            # Corrélation météo / courses
            if not df_daily_corr.empty and "date" in df_weather.columns:
                df_daily_corr["day"] = pd.to_datetime(df_daily_corr["day"])
                df_daily_corr = df_daily_corr[
                    (df_daily_corr["day"] >= "2024-01-01") &
                    (df_daily_corr["day"] <= "2024-01-31")
                ]

                # Agréger météo par jour
                df_weather["date"] = pd.to_datetime(df_weather["date"])
                df_weather_daily = df_weather.groupby("date").agg(
                    avg_temp=("temperature_2m", "mean"),
                    total_precip=("precipitation", "sum")
                ).reset_index()

                df_corr = df_daily_corr.merge(
                    df_weather_daily,
                    left_on="day", right_on="date", how="inner"
                )

                if not df_corr.empty:
                    st.subheader("📊 Corrélation Météo / Courses")

                    c1, c2 = st.columns(2)
                    c1.plotly_chart(px.scatter(df_corr,
                        x="avg_temp", y="nb_trips",
                        title="🌡️ Température vs Nombre de courses",
                        labels={"avg_temp": "Température moy. (°C)", "nb_trips": "Courses"},
                        trendline="ols",
                        color_discrete_sequence=["#0074D9"]), use_container_width=True)

                    c2.plotly_chart(px.scatter(df_corr,
                        x="total_precip", y="nb_trips",
                        title="🌧️ Précipitations vs Nombre de courses",
                        labels={"total_precip": "Précipitations (mm)", "nb_trips": "Courses"},
                        trendline="ols",
                        color_discrete_sequence=["#7FDBFF"]), use_container_width=True)
    else:
        st.warning("Aucune donnée météo. Relance l'ingestion météo puis le Glue Pipeline.")
        st.info("💡 L'ingestion météo récupère maintenant l'historique janvier 2024 (744 heures)")

# =========================
# TAB 3 — STREAMING
# =========================
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

        st.dataframe(
            df_rt[[c for c in ["taxi_id", "fare", "speed", "pickup_lat", "pickup_lon", "ingested_at"] if c in df_rt.columns]],
            use_container_width=True
        )

        c1, c2 = st.columns(2)
        c1.plotly_chart(px.histogram(df_rt, x="fare",
            title="Distribution des tarifs (streaming)",
            color_discrete_sequence=["#F6C90E"], nbins=20), use_container_width=True)
        c2.plotly_chart(px.scatter(df_rt, x="pickup_lon", y="pickup_lat",
            size="fare", color="speed",
            title="🗺️ Positions de départ — Manhattan",
            color_continuous_scale="RdYlGn"), use_container_width=True)
    else:
        st.info("Lance le streaming Kafka sur l'EC2 pour voir les données en temps réel.")
