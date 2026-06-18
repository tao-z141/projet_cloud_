import streamlit as st
import pandas as pd
import boto3
import io
import os
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# =========================
# NYC STYLE CONFIG
# =========================
st.set_page_config(
    page_title="NYC Taxi Platform",
    page_icon="🚕",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# NYC Style CSS — jaune taxi, noir, urbain
st.markdown("""
<style>
    /* Fond noir urbain */
    .stApp { background-color: #0D0D0D; color: #F5F5F5; }
    .main .block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 1400px; }

    /* Header titre */
    .nyc-header {
        background: linear-gradient(135deg, #F6C90E 0%, #E5B800 50%, #F6C90E 100%);
        padding: 2rem 2.5rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .nyc-header h1 {
        color: #0D0D0D !important;
        font-size: 2.2rem !important;
        font-weight: 900 !important;
        margin: 0 !important;
        letter-spacing: -1px;
        font-family: 'Arial Black', sans-serif !important;
    }
    .nyc-header p {
        color: #333 !important;
        margin: 0.3rem 0 0 0 !important;
        font-size: 0.95rem !important;
        font-weight: 500;
    }

    /* KPI Cards */
    .kpi-card {
        background: #1A1A1A;
        border: 1px solid #2A2A2A;
        border-left: 4px solid #F6C90E;
        border-radius: 10px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 0.5rem;
        transition: transform 0.2s;
    }
    .kpi-card:hover { transform: translateY(-2px); border-left-color: #FFD700; }
    .kpi-label {
        color: #888;
        font-size: 0.78rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 0.4rem;
    }
    .kpi-value {
        color: #F6C90E;
        font-size: 2rem;
        font-weight: 900;
        font-family: 'Arial Black', sans-serif;
        line-height: 1;
    }
    .kpi-sub {
        color: #666;
        font-size: 0.78rem;
        margin-top: 0.3rem;
    }

    /* Section titles */
    .section-title {
        color: #F6C90E;
        font-size: 1.1rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 2px;
        border-bottom: 2px solid #F6C90E;
        padding-bottom: 0.5rem;
        margin: 1.5rem 0 1rem 0;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: #1A1A1A;
        border-radius: 10px;
        padding: 0.3rem;
        gap: 0.3rem;
        border: 1px solid #2A2A2A;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: #888;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.9rem;
        padding: 0.6rem 1.5rem;
    }
    .stTabs [aria-selected="true"] {
        background: #F6C90E !important;
        color: #0D0D0D !important;
    }

    /* Alert box */
    .alert-box {
        background: #1A0A0A;
        border: 1px solid #CC3333;
        border-left: 4px solid #FF4444;
        border-radius: 8px;
        padding: 1rem 1.5rem;
        margin: 1rem 0;
        color: #FF8888;
    }
    .ok-box {
        background: #0A1A0A;
        border: 1px solid #33CC33;
        border-left: 4px solid #44FF44;
        border-radius: 8px;
        padding: 1rem 1.5rem;
        margin: 1rem 0;
        color: #88FF88;
    }

    /* Divider */
    hr { border-color: #2A2A2A; }

    /* Hide streamlit branding */
    #MainMenu, footer, header { visibility: hidden; }
    .stDeployButton { display: none; }

    /* Metric override */
    [data-testid="metric-container"] {
        background: #1A1A1A;
        border: 1px solid #2A2A2A;
        border-left: 4px solid #F6C90E;
        border-radius: 10px;
        padding: 1rem;
    }
    [data-testid="metric-container"] label { color: #888 !important; font-size: 0.78rem !important; text-transform: uppercase; letter-spacing: 1px; }
    [data-testid="metric-container"] [data-testid="stMetricValue"] { color: #F6C90E !important; font-size: 1.8rem !important; font-weight: 900 !important; }

    /* Plotly chart background */
    .js-plotly-plot { border-radius: 10px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# NYC Plotly theme
NYC_THEME = dict(
    paper_bgcolor="#1A1A1A",
    plot_bgcolor="#111111",
    font=dict(color="#CCCCCC", family="Arial"),
    xaxis=dict(gridcolor="#222222", linecolor="#333333", tickcolor="#555"),
    yaxis=dict(gridcolor="#222222", linecolor="#333333", tickcolor="#555"),
    margin=dict(t=50, b=40, l=50, r=20)
)
YELLOW = "#F6C90E"
ORANGE = "#FF6B35"
TEAL = "#00D4AA"
RED = "#FF4444"
BLUE = "#4A9EFF"

# =========================
# CONFIG
# =========================
BUCKET = "nyc-taxi-platform"
API_URL = "https://thg365gege.execute-api.eu-west-3.amazonaws.com/prod"
AWS_REGION = "eu-west-3"
AWS_KEY = st.secrets.get("AWS_ACCESS_KEY_ID", os.environ.get("AWS_ACCESS_KEY_ID"))
AWS_SECRET = st.secrets.get("AWS_SECRET_ACCESS_KEY", os.environ.get("AWS_SECRET_ACCESS_KEY"))

# =========================
# DATA LOADERS
# =========================
@st.cache_data(ttl=300)
def load_s3_parquet(prefix):
    s3 = boto3.client("s3", region_name=AWS_REGION,
        aws_access_key_id=AWS_KEY, aws_secret_access_key=AWS_SECRET)
    paginator = s3.get_paginator("list_objects_v2")
    dfs = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".parquet"):
                r = s3.get_object(Bucket=BUCKET, Key=obj["Key"])
                dfs.append(pd.read_parquet(io.BytesIO(r["Body"].read())))
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

@st.cache_data(ttl=30)
def load_realtime():
    try:
        return requests.get(f"{API_URL}/realtime", timeout=5).json()
    except:
        return {"events_count": 0, "latest_events": []}

# =========================
# HEADER NYC STYLE
# =========================
st.markdown("""
<div class="nyc-header">
    <div style="font-size:3rem">🚕</div>
    <div>
        <h1>NYC TAXI DATA PLATFORM</h1>
        <p>Pipeline Médaillon AWS · Bronze → Silver → Gold · Janvier 2024</p>
    </div>
    <div style="margin-left:auto; text-align:right;">
        <div style="color:#333; font-size:0.8rem; font-weight:600;">LAST UPDATE</div>
        <div style="color:#0D0D0D; font-size:1rem; font-weight:700;">""" + datetime.now().strftime('%d %b %Y · %H:%M') + """</div>
    </div>
</div>
""", unsafe_allow_html=True)

# =========================
# TABS
# =========================
tab1, tab2, tab3 = st.tabs([
    "🏙️  Performance Opérationnelle",
    "🌧️  Impact Météo",
    "⚡  Supervision Temps Réel"
])

# ============================================================
# TAB 1 — PERFORMANCE OPÉRATIONNELLE
# ============================================================
with tab1:
    with st.spinner(""):
        df_daily = load_s3_parquet("gold/kpi_daily/")
        df_zone = load_s3_parquet("gold/kpi_zone/")

    if not df_daily.empty:
        df_daily["day"] = pd.to_datetime(df_daily["day"])
        df_daily = df_daily[(df_daily["day"] >= "2024-01-01") & (df_daily["day"] <= "2024-01-31")].sort_values("day")

        # --- KPIs ---
        st.markdown('<div class="section-title">📊 KPIs Janvier 2024</div>', unsafe_allow_html=True)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🚗 Total Courses", f"{int(df_daily['nb_trips'].sum()):,}")
        k2.metric("💰 Tarif Moyen", f"${df_daily['avg_fare_usd'].mean():.2f}")
        k3.metric("📏 Distance Moy.", f"{df_daily['avg_distance_km'].mean():.2f} km")
        k4.metric("💵 Revenus Totaux", f"${df_daily['total_revenue_usd'].sum()/1e6:.2f}M")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- Courbe courses + revenus ---
        c1, c2 = st.columns(2)

        with c1:
            st.markdown('<div class="section-title">📈 Volume de courses / jour</div>', unsafe_allow_html=True)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_daily["day"], y=df_daily["nb_trips"],
                fill="tozeroy", fillcolor="rgba(246,201,14,0.15)",
                line=dict(color=YELLOW, width=2.5),
                mode="lines", name="Courses"
            ))
            fig.update_layout(**NYC_THEME, title="", showlegend=False, height=280)
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.markdown('<div class="section-title">💵 Revenus journaliers ($)</div>', unsafe_allow_html=True)
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=df_daily["day"], y=df_daily["total_revenue_usd"],
                marker_color=YELLOW, marker_line_width=0,
                name="Revenus"
            ))
            fig2.update_layout(**NYC_THEME, title="", showlegend=False, height=280)
            st.plotly_chart(fig2, use_container_width=True)

        # --- Tarif moyen + zones ---
        c3, c4 = st.columns([1, 1])

        with c3:
            st.markdown('<div class="section-title">💰 Évolution du tarif moyen</div>', unsafe_allow_html=True)
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(
                x=df_daily["day"], y=df_daily["avg_fare_usd"],
                mode="lines+markers",
                line=dict(color=TEAL, width=2),
                marker=dict(color=TEAL, size=5),
                fill="tozeroy", fillcolor="rgba(0,212,170,0.08)"
            ))
            fig3.add_hline(y=df_daily["avg_fare_usd"].mean(), line_dash="dash",
                line_color="#555", annotation_text=f"Moy. ${df_daily['avg_fare_usd'].mean():.2f}",
                annotation_font_color="#888")
            fig3.update_layout(**NYC_THEME, title="", showlegend=False, height=280)
            st.plotly_chart(fig3, use_container_width=True)

        with c4:
            st.markdown('<div class="section-title">🗺️ Top 15 Zones — Revenus</div>', unsafe_allow_html=True)
            if not df_zone.empty:
                df_top = df_zone.sort_values("total_revenue_usd", ascending=False).head(15)
                label = "zone_name" if "zone_name" in df_top.columns else "zone_id"
                df_top["label"] = df_top[label].astype(str).str[:22]

                fig4 = go.Figure(go.Bar(
                    x=df_top["total_revenue_usd"] / 1000,
                    y=df_top["label"],
                    orientation="h",
                    marker=dict(
                        color=df_top["total_revenue_usd"],
                        colorscale=[[0, "#333300"], [0.5, "#997700"], [1, YELLOW]],
                        line_width=0
                    )
                ))
                fig4.update_layout(**NYC_THEME, title="", showlegend=False,
                    height=280, xaxis_title="Revenus ($K)",
                    yaxis=dict(gridcolor="#1A1A1A", linecolor="#333333", tickcolor="#555", tickfont=dict(size=10)))
                st.plotly_chart(fig4, use_container_width=True)

        # --- Distribution distance ---
        st.markdown('<div class="section-title">📊 Analyse Journalière — Passagers & Distance</div>', unsafe_allow_html=True)
        c5, c6 = st.columns(2)

        with c5:
            fig5 = go.Figure()
            fig5.add_trace(go.Scatter(
                x=df_daily["day"], y=df_daily["avg_passengers"],
                mode="lines", line=dict(color=ORANGE, width=2),
                fill="tozeroy", fillcolor="rgba(255,107,53,0.1)"
            ))
            fig5.update_layout(**NYC_THEME, title="Passagers moyens / course", height=220, showlegend=False)
            st.plotly_chart(fig5, use_container_width=True)

        with c6:
            fig6 = go.Figure()
            fig6.add_trace(go.Scatter(
                x=df_daily["day"], y=df_daily["avg_distance_km"],
                mode="lines", line=dict(color=BLUE, width=2),
                fill="tozeroy", fillcolor="rgba(74,158,255,0.1)"
            ))
            fig6.update_layout(**NYC_THEME, title="Distance moyenne / course (km)", height=220, showlegend=False)
            st.plotly_chart(fig6, use_container_width=True)

    else:
        st.warning("Aucune donnée Gold disponible.")

# ============================================================
# TAB 2 — IMPACT MÉTÉO
# ============================================================
with tab2:
    with st.spinner(""):
        df_weather = load_s3_parquet("silver/weather_clean/")
        df_daily2 = load_s3_parquet("gold/kpi_daily/")

    if not df_weather.empty and "temperature_2m" in df_weather.columns:
        # KPIs météo
        st.markdown('<div class="section-title">🌡️ Météo NYC — Janvier 2024</div>', unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🌡️ Température moy.", f"{df_weather['temperature_2m'].mean():.1f}°C")
        m2.metric("🔴 Température max.", f"{df_weather['temperature_2m'].max():.1f}°C")
        m3.metric("🔵 Température min.", f"{df_weather['temperature_2m'].min():.1f}°C")
        if "precipitation" in df_weather.columns:
            m4.metric("🌧️ Précipitations tot.", f"{df_weather['precipitation'].sum():.0f} mm")

        st.markdown("<br>", unsafe_allow_html=True)

        # Courbe température
        st.markdown('<div class="section-title">🌡️ Température horaire — Janvier 2024</div>', unsafe_allow_html=True)
        fig_t = go.Figure()
        fig_t.add_trace(go.Scatter(
            x=df_weather["datetime"], y=df_weather["temperature_2m"],
            mode="lines", line=dict(color=ORANGE, width=1.5),
            fill="tozeroy", fillcolor="rgba(255,107,53,0.08)",
            name="Température"
        ))
        fig_t.add_hline(y=0, line_color="#444", line_dash="dash",
            annotation_text="0°C", annotation_font_color="#666")
        fig_t.update_layout(**NYC_THEME, height=220, showlegend=False, yaxis_title="°C")
        st.plotly_chart(fig_t, use_container_width=True)

        # Corrélations
        if not df_daily2.empty and "date" in df_weather.columns:
            df_daily2["day"] = pd.to_datetime(df_daily2["day"])
            df_daily2 = df_daily2[(df_daily2["day"] >= "2024-01-01") & (df_daily2["day"] <= "2024-01-31")]
            df_weather["date"] = pd.to_datetime(df_weather["date"])
            df_w_daily = df_weather.groupby("date").agg(
                avg_temp=("temperature_2m", "mean"),
                total_precip=("precipitation", "sum") if "precipitation" in df_weather.columns else ("temperature_2m", "count")
            ).reset_index()
            df_corr = df_daily2.merge(df_w_daily, left_on="day", right_on="date", how="inner")

            if not df_corr.empty:
                st.markdown('<div class="section-title">📊 Corrélations Météo → Demande de Taxis</div>', unsafe_allow_html=True)
                c1, c2 = st.columns(2)

                with c1:
                    fig_c1 = px.scatter(df_corr, x="avg_temp", y="nb_trips",
                        trendline="ols",
                        labels={"avg_temp": "Température moy. (°C)", "nb_trips": "Nb courses"},
                        color_discrete_sequence=[YELLOW])
                    fig_c1.update_traces(marker=dict(size=10, opacity=0.8))
                    fig_c1.update_layout(**NYC_THEME, title="🌡️ Température vs Courses", height=300)
                    st.plotly_chart(fig_c1, use_container_width=True)

                with c2:
                    fig_c2 = px.scatter(df_corr, x="total_precip", y="nb_trips",
                        trendline="ols",
                        labels={"total_precip": "Précipitations (mm)", "nb_trips": "Nb courses"},
                        color_discrete_sequence=[TEAL])
                    fig_c2.update_traces(marker=dict(size=10, opacity=0.8))
                    fig_c2.update_layout(**NYC_THEME, title="🌧️ Précipitations vs Courses", height=300)
                    st.plotly_chart(fig_c2, use_container_width=True)

                # Revenus par catégorie météo
                if "weather_condition" in df_corr.columns:
                    st.markdown('<div class="section-title">☁️ Revenus moyens par condition météo</div>', unsafe_allow_html=True)
                    df_weather_group = df_corr.groupby("weather_condition")["total_revenue_usd"].mean().reset_index()
                    fig_wg = go.Figure(go.Bar(
                        x=df_weather_group["weather_condition"],
                        y=df_weather_group["total_revenue_usd"] / 1000,
                        marker_color=[YELLOW, TEAL, BLUE],
                        marker_line_width=0
                    ))
                    fig_wg.update_layout(**NYC_THEME, title="", height=220,
                        yaxis_title="Revenus moy. ($K)", showlegend=False)
                    st.plotly_chart(fig_wg, use_container_width=True)
    else:
        st.warning("Aucune donnée météo. Relance l'ingestion puis le pipeline Glue.")

# ============================================================
# TAB 3 — STREAMING TEMPS RÉEL
# ============================================================
with tab3:
    col_refresh, _ = st.columns([1, 5])
    with col_refresh:
        if st.button("🔄 Rafraîchir", use_container_width=True):
            st.cache_data.clear()

    realtime = load_realtime()
    total_events = realtime.get("events_count", 0)
    events = realtime.get("latest_events", [])

    if events:
        df_rt = pd.DataFrame(events)
        for c in ["total_amount", "trip_distance", "passenger_count"]:
            if c in df_rt.columns:
                df_rt[c] = pd.to_numeric(df_rt[c], errors="coerce")

        # KPIs
        st.markdown('<div class="section-title">⚡ KPIs Temps Réel</div>', unsafe_allow_html=True)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("📡 Événements total", f"{total_events:,}")
        if "total_amount" in df_rt.columns:
            k2.metric("💰 Montant moyen", f"${df_rt['total_amount'].mean():.2f}")
            k3.metric("💵 Revenu estimé", f"${df_rt['total_amount'].sum():.0f}")
        if "trip_distance" in df_rt.columns:
            k4.metric("📏 Distance moy.", f"{df_rt['trip_distance'].mean():.2f} km")

        st.markdown("<br>", unsafe_allow_html=True)

        # Anomalies
        if "total_amount" in df_rt.columns:
            df_rt["anomalie"] = df_rt["total_amount"] > 55
            nb_anomalies = int(df_rt["anomalie"].sum())
            if nb_anomalies > 0:
                st.markdown(f'<div class="alert-box">⚠️ <strong>{nb_anomalies} course(s) à montant élevé détectée(s)</strong> — Seuil : $55</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="ok-box">✅ Aucune anomalie détectée sur les 50 derniers événements</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        c1, c2 = st.columns(2)

        # Distribution montants
        with c1:
            st.markdown('<div class="section-title">💰 Distribution des montants</div>', unsafe_allow_html=True)
            if "total_amount" in df_rt.columns:
                fig_fare = go.Figure()
                fig_fare.add_trace(go.Histogram(
                    x=df_rt["total_amount"].dropna(),
                    nbinsx=12,
                    marker_color=YELLOW,
                    marker_line_color="#0D0D0D",
                    marker_line_width=1,
                    opacity=0.85
                ))
                fig_fare.add_vline(x=55, line_dash="dash", line_color=RED,
                    annotation_text="Seuil $55", annotation_font_color=RED,
                    annotation_font_size=11)
                fig_fare.update_layout(**NYC_THEME, height=260, showlegend=False,
                    xaxis_title="Montant ($)", yaxis_title="Fréquence")
                st.plotly_chart(fig_fare, use_container_width=True)

        # Courses par arrondissement
        with c2:
            st.markdown('<div class="section-title">🗺️ Courses par arrondissement</div>', unsafe_allow_html=True)
            if "pickup_borough" in df_rt.columns:
                borough_data = df_rt["pickup_borough"].value_counts().reset_index()
                borough_data.columns = ["borough", "count"]
                colors_borough = [YELLOW, TEAL, ORANGE, BLUE, "#AA44FF"]
                fig_b = go.Figure(go.Bar(
                    x=borough_data["borough"],
                    y=borough_data["count"],
                    marker_color=colors_borough[:len(borough_data)],
                    marker_line_width=0,
                    text=borough_data["count"],
                    textposition="outside",
                    textfont=dict(color="#CCCCCC", size=11)
                ))
                fig_b.update_layout(**NYC_THEME, height=260, showlegend=False,
                    xaxis_title="", yaxis_title="Nb courses")
                st.plotly_chart(fig_b, use_container_width=True)

        # Pie paiement + revenus par borough
        c3, c4 = st.columns(2)

        with c3:
            st.markdown('<div class="section-title">💳 Mode de paiement</div>', unsafe_allow_html=True)
            if "payment_type" in df_rt.columns:
                pay_data = df_rt["payment_type"].value_counts().reset_index()
                pay_data.columns = ["type", "count"]
                fig_pie = go.Figure(go.Pie(
                    labels=pay_data["type"],
                    values=pay_data["count"],
                    hole=0.55,
                    marker_colors=[YELLOW, TEAL, ORANGE, BLUE],
                    textfont=dict(size=12),
                    hovertemplate="%{label}: %{value} courses<br>%{percent}<extra></extra>"
                ))
                fig_pie.add_annotation(
                    text=f"<b>{len(df_rt)}</b><br>courses",
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(size=14, color="#CCCCCC")
                )
                fig_pie.update_layout(**NYC_THEME, height=260, showlegend=True,
                    legend=dict(font=dict(color="#CCCCCC"), bgcolor="rgba(0,0,0,0)"))
                st.plotly_chart(fig_pie, use_container_width=True)

        with c4:
            st.markdown('<div class="section-title">💵 Revenu moyen / arrondissement</div>', unsafe_allow_html=True)
            if "pickup_borough" in df_rt.columns and "total_amount" in df_rt.columns:
                rev_borough = df_rt.groupby("pickup_borough")["total_amount"].mean().reset_index()
                rev_borough.columns = ["borough", "avg_amount"]
                rev_borough = rev_borough.sort_values("avg_amount", ascending=True)
                fig_rev = go.Figure(go.Bar(
                    x=rev_borough["avg_amount"],
                    y=rev_borough["borough"],
                    orientation="h",
                    marker=dict(
                        color=rev_borough["avg_amount"],
                        colorscale=[[0, "#222200"], [1, YELLOW]],
                        line_width=0
                    ),
                    text=rev_borough["avg_amount"].apply(lambda x: f"${x:.1f}"),
                    textposition="outside",
                    textfont=dict(color="#CCCCCC", size=11)
                ))
                fig_rev.update_layout(**NYC_THEME, height=260, showlegend=False,
                    xaxis_title="Montant moyen ($)",
                    yaxis=dict(gridcolor="#1A1A1A", linecolor="#333333", tickfont=dict(size=11)))
                st.plotly_chart(fig_rev, use_container_width=True)

    else:
        st.markdown("""
        <div style="text-align:center; padding:3rem; color:#555;">
            <div style="font-size:4rem">⚡</div>
            <div style="font-size:1.2rem; margin-top:1rem; color:#888;">Aucune donnée streaming disponible</div>
            <div style="font-size:0.85rem; margin-top:0.5rem; color:#555;">Lance le producer Kafka sur l'EC2 pour alimenter ce dashboard</div>
        </div>
        """, unsafe_allow_html=True)
