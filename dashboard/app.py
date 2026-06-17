import streamlit as st
import pandas as pd
import boto3
import io
import os
import requests
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="NYC Taxi Platform", page_icon="🚕", layout="wide")

BUCKET = "nyc-taxi-platform"
API_URL = "https://thg365gege.execute-api.eu-west-3.amazonaws.com/prod"
AWS_REGION = "eu-west-3"

AWS_KEY = st.secrets.get("AWS_ACCESS_KEY_ID", os.environ.get("AWS_ACCESS_KEY_ID"))
AWS_SECRET = st.secrets.get("AWS_SECRET_ACCESS_KEY", os.environ.get("AWS_SECRET_ACCESS_KEY"))

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

@st.cache_data(ttl=30)
def load_realtime():
    try:
        r = requests.get(f"{API_URL}/realtime", timeout=5)
        return r.json()
    except:
        return {"events_count": 0, "latest_events": []}

st.title("🚕 NYC Taxi Data Platform")
st.divider()

tab1, tab2, tab3 = st.tabs(["📊 KPIs Batch", "🌤️ Météo & Corrélations", "⚡ Streaming Temps Réel"])

# --- TAB 1 ---
with tab1:
    st.subheader("KPIs Journaliers — Janvier 2024")
    with st.spinner("Chargement Gold S3..."):
        df_daily = load_s3_parquet("gold/kpi_daily/")
        df_zone = load_s3_parquet("gold/kpi_zone/")

    if not df_daily.empty:
        df_daily["day"] = pd.to_datetime(df_daily["day"])
        df_daily = df_daily.sort_values("day")
        df_daily = df_daily[(df_daily["day"] >= "2024-01-01") & (df_daily["day"] <= "2024-01-31")]

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🚗 Total Courses", f"{int(df_daily['nb_trips'].sum()):,}")
        col2.metric("💰 Tarif Moyen", f"${df_daily['avg_fare_usd'].mean():.2f}")
        col3.metric("📏 Distance Moy.", f"{df_daily['avg_distance_km'].mean():.2f} km")
        col4.metric("💵 Revenus Totaux", f"${df_daily['total_revenue_usd'].sum():,.0f}")

        st.plotly_chart(px.line(df_daily, x="day", y="nb_trips",
            title="📈 Courses par jour — Janvier 2024",
            color_discrete_sequence=["#F6C90E"]), use_container_width=True)

        c1, c2 = st.columns(2)
        c1.plotly_chart(px.bar(df_daily, x="day", y="total_revenue_usd",
            title="💵 Revenus journaliers ($)",
            color_discrete_sequence=["#3D9970"]), use_container_width=True)
        c2.plotly_chart(px.line(df_daily, x="day", y="avg_fare_usd",
            title="💰 Tarif moyen ($)",
            color_discrete_sequence=["#FF4136"]), use_container_width=True)

        if not df_zone.empty:
            st.subheader("🗺️ Top 20 Zones de départ")
            df_top = df_zone.sort_values("nb_trips", ascending=False).head(20)
            label_col = "zone_name" if "zone_name" in df_top.columns else "zone_id"
            color_col = "borough" if "borough" in df_top.columns else None
            df_top["label"] = df_top[label_col].astype(str)

            st.plotly_chart(px.bar(df_top, x="label", y="nb_trips",
                title="Courses par zone (Top 20)", color=color_col,
                labels={"label": "Zone", "nb_trips": "Courses"},
                color_discrete_sequence=px.colors.qualitative.Set2),
                use_container_width=True)

            display_cols = [c for c in ["zone_name", "borough", "nb_trips", "avg_fare_usd", "total_revenue_usd"] if c in df_top.columns]
            st.dataframe(df_top[display_cols], use_container_width=True)
    else:
        st.warning("Aucune donnée Gold. Lance le Glue Pipeline.")

# --- TAB 2 ---
with tab2:
    with st.spinner("Chargement données météo..."):
        df_weather = load_s3_parquet("silver/weather_clean/")
        df_daily_corr = load_s3_parquet("gold/kpi_daily/")

    if not df_weather.empty:
        st.write(f"**{len(df_weather):,} enregistrements horaires — Janvier 2024**")

        if "temperature_2m" in df_weather.columns:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🌡️ Moy.", f"{df_weather['temperature_2m'].mean():.1f}°C")
            c2.metric("🔴 Max.", f"{df_weather['temperature_2m'].max():.1f}°C")
            c3.metric("🔵 Min.", f"{df_weather['temperature_2m'].min():.1f}°C")
            if "precipitation" in df_weather.columns:
                c4.metric("🌧️ Précipitations", f"{df_weather['precipitation'].sum():.1f} mm")

            st.plotly_chart(px.line(df_weather, x="datetime", y="temperature_2m",
                title="🌡️ Température horaire NYC — Janvier 2024",
                color_discrete_sequence=["#FF851B"]), use_container_width=True)

        if not df_daily_corr.empty and "date" in df_weather.columns:
            df_daily_corr["day"] = pd.to_datetime(df_daily_corr["day"])
            df_daily_corr = df_daily_corr[(df_daily_corr["day"] >= "2024-01-01") & (df_daily_corr["day"] <= "2024-01-31")]
            df_weather["date"] = pd.to_datetime(df_weather["date"])
            df_weather_daily = df_weather.groupby("date").agg(
                avg_temp=("temperature_2m", "mean"),
                total_precip=("precipitation", "sum")
            ).reset_index()
            df_corr = df_daily_corr.merge(df_weather_daily, left_on="day", right_on="date", how="inner")

            if not df_corr.empty:
                st.subheader("📊 Corrélation Météo / Courses")
                c1, c2 = st.columns(2)
                c1.plotly_chart(px.scatter(df_corr, x="avg_temp", y="nb_trips",
                    title="🌡️ Température vs Courses", trendline="ols",
                    color_discrete_sequence=["#0074D9"]), use_container_width=True)
                c2.plotly_chart(px.scatter(df_corr, x="total_precip", y="nb_trips",
                    title="🌧️ Précipitations vs Courses", trendline="ols",
                    color_discrete_sequence=["#7FDBFF"]), use_container_width=True)
    else:
        st.warning("Aucune donnée météo.")

# --- TAB 3 ---
with tab3:
    if st.button("🔄 Rafraîchir"):
        st.cache_data.clear()

    realtime = load_realtime()
    total_events = realtime.get("events_count", 0)
    events = realtime.get("latest_events", [])

    if events:
        df_rt = pd.DataFrame(events)

        # Convertir colonnes numériques
        for c in ["total_amount", "trip_distance", "passenger_count"]:
            if c in df_rt.columns:
                df_rt[c] = pd.to_numeric(df_rt[c], errors="coerce")

        # KPIs temps réel
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("📡 Événements", f"{total_events:,}")
        if "total_amount" in df_rt.columns:
            k2.metric("💰 Montant moyen", f"${df_rt['total_amount'].mean():.2f}")
            k3.metric("💵 Revenu estimé", f"${df_rt['total_amount'].sum():.0f}")
        if "trip_distance" in df_rt.columns:
            k4.metric("📏 Distance moy.", f"{df_rt['trip_distance'].mean():.2f} km")

        st.divider()

        # Anomalies — montant élevé
        if "total_amount" in df_rt.columns:
            df_rt["anomalie"] = df_rt["total_amount"] > 55
            nb_anomalies = int(df_rt["anomalie"].sum())
            if nb_anomalies > 0:
                st.warning(f"⚠️ {nb_anomalies} course(s) à montant élevé (> $55)")
                anomaly_cols = [c for c in ["event_id", "total_amount", "trip_distance", "pickup_borough", "payment_type"] if c in df_rt.columns]
                st.dataframe(df_rt[df_rt["anomalie"]][anomaly_cols], use_container_width=True)
            else:
                st.success("✅ Aucune anomalie détectée")

        st.divider()

        c1, c2 = st.columns(2)

        # Distribution montants
        if "total_amount" in df_rt.columns:
            fig_fare = px.histogram(df_rt.dropna(subset=["total_amount"]),
                x="total_amount", title="💰 Distribution des montants ($)",
                color_discrete_sequence=["#F6C90E"], nbins=15)
            fig_fare.add_vline(x=55, line_dash="dash", line_color="red", annotation_text="Seuil $55")
            c1.plotly_chart(fig_fare, use_container_width=True)

        # Courses par arrondissement
        if "pickup_borough" in df_rt.columns:
            borough_counts = df_rt["pickup_borough"].value_counts().reset_index()
            borough_counts.columns = ["borough", "nb_courses"]
            c2.plotly_chart(px.bar(borough_counts, x="borough", y="nb_courses",
                title="🗺️ Courses par arrondissement",
                color="borough",
                color_discrete_sequence=px.colors.qualitative.Set2),
                use_container_width=True)

        # Paiement cash vs carte
        if "payment_type" in df_rt.columns:
            payment_counts = df_rt["payment_type"].value_counts().reset_index()
            payment_counts.columns = ["payment_type", "count"]
            st.plotly_chart(px.pie(payment_counts, names="payment_type", values="count",
                title="💳 Mode de paiement (streaming)",
                color_discrete_sequence=["#3D9970", "#FF4136"]),
                use_container_width=True)

        # Tableau
        st.subheader("📋 Derniers événements")
        display_cols = [c for c in ["event_id", "total_amount", "trip_distance", "passenger_count", "pickup_borough", "payment_type", "event_timestamp"] if c in df_rt.columns]
        st.dataframe(df_rt[display_cols], use_container_width=True)

    else:
        st.info("Lance le streaming Kafka sur l'EC2 pour voir les données.")
