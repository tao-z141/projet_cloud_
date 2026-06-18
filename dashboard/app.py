import streamlit as st
import pandas as pd
import boto3
import io
import os
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(
    page_title="NYC Taxi Platform",
    page_icon="🚕",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp { background-color: #F0F2F6; color: #1A1A2E; }
    .main .block-container { padding-top: 1.5rem; padding-bottom: 1rem; max-width: 1400px; }

    .nyc-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.8rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 1.2rem;
    }
    .nyc-header h1 {
        color: #FFFFFF !important;
        font-size: 1.9rem !important;
        font-weight: 800 !important;
        margin: 0 !important;
        letter-spacing: -0.5px;
    }

    .section-title {
        color: #667eea;
        font-size: 0.82rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        border-left: 3px solid #667eea;
        padding-left: 0.7rem;
        margin: 1.2rem 0 0.8rem 0;
    }

    .stTabs [data-baseweb="tab-list"] {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 0.3rem;
        gap: 0.2rem;
        border: 1px solid #E0E4EE;
        box-shadow: 0 2px 10px rgba(102,126,234,0.08);
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: #888;
        border-radius: 10px;
        font-weight: 600;
        font-size: 0.88rem;
        padding: 0.55rem 1.4rem;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: #FFFFFF !important;
    }

    .alert-box {
        background: #FFF5F5;
        border: 1px solid #FFCCCC;
        border-left: 4px solid #FF4444;
        border-radius: 10px;
        padding: 0.9rem 1.2rem;
        margin: 0.8rem 0;
        color: #CC2222;
        font-weight: 500;
    }
    .ok-box {
        background: #F0FFF4;
        border: 1px solid #BBEECC;
        border-left: 4px solid #22BB55;
        border-radius: 10px;
        padding: 0.9rem 1.2rem;
        margin: 0.8rem 0;
        color: #1A8833;
        font-weight: 500;
    }

    [data-testid="metric-container"] {
        background: #FFFFFF;
        border: 1px solid #E0E4EE;
        border-top: 3px solid #667eea;
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 2px 10px rgba(102,126,234,0.06);
    }
    [data-testid="metric-container"] label {
        color: #999 !important;
        font-size: 0.75rem !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 600;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #1A1A2E !important;
        font-size: 1.7rem !important;
        font-weight: 800 !important;
    }

    #MainMenu, footer, header { visibility: hidden; }
    .stDeployButton { display: none; }
</style>
""", unsafe_allow_html=True)

THEME = dict(
    paper_bgcolor="#FFFFFF",
    plot_bgcolor="#FAFBFC",
    font=dict(color="#333333", family="Arial"),
    xaxis=dict(gridcolor="#EFEFEF", linecolor="#DDDDDD", tickcolor="#AAAAAA"),
    yaxis=dict(gridcolor="#EFEFEF", linecolor="#DDDDDD", tickcolor="#AAAAAA"),
    margin=dict(t=40, b=30, l=50, r=20)
)

VIOLET = "#667eea"
PURPLE = "#764ba2"
TEAL   = "#00B4D8"
CORAL  = "#FF6B6B"
GREEN  = "#06D6A0"
ORANGE = "#FF9A3C"

# Couleurs par année
YEAR_COLORS  = {"2024": VIOLET, "2025": CORAL}
MONTH_LABELS = {1: "Jan", 2: "Fév", 3: "Mar", 4: "Avr"}

BUCKET     = "nyc-taxi-platform"
API_URL    = "https://thg365gege.execute-api.eu-west-3.amazonaws.com/prod"
AWS_REGION = "eu-west-3"
AWS_KEY    = st.secrets.get("AWS_ACCESS_KEY_ID", os.environ.get("AWS_ACCESS_KEY_ID"))
AWS_SECRET = st.secrets.get("AWS_SECRET_ACCESS_KEY", os.environ.get("AWS_SECRET_ACCESS_KEY"))

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

# Header
st.markdown("""
<div class="nyc-header">
    <div style="font-size:2.8rem">🚕</div>
    <div><h1>NYC Taxi Data Platform</h1></div>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs([
    "🏙️  Performance Opérationnelle",
    "🌧️  Impact Météo",
    "⚡  Supervision Temps Réel"
])

# ============================================================
# TAB 1 — PERFORMANCE
# ============================================================
with tab1:
    with st.spinner(""):
        df_daily = load_s3_parquet("gold/kpi_daily/")
        df_zone  = load_s3_parquet("gold/kpi_zone/")

    if not df_daily.empty:
        df_daily["day"] = pd.to_datetime(df_daily["day"])
        df_daily = df_daily[
            (df_daily["day"] >= "2024-01-01") &
            (df_daily["day"] <= "2025-03-31")
        ].sort_values("day")

        df_daily["year"]      = df_daily["day"].dt.year.astype(str)
        df_daily["month_num"] = df_daily["day"].dt.month
        df_daily["month_lbl"] = df_daily["month_num"].map(MONTH_LABELS)

        # KPIs globaux
        st.markdown('<div class="section-title">KPIs Globaux — Q1 2024 vs Q1 2025</div>', unsafe_allow_html=True)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🚗 Total Courses", f"{int(df_daily['nb_trips'].sum()):,}")
        k2.metric("💰 Tarif Moyen", f"${df_daily['avg_fare_usd'].mean():.2f}")
        k3.metric("📏 Distance Moy.", f"{df_daily['avg_distance_km'].mean():.2f} km")
        k4.metric("💵 Revenus Totaux", f"${df_daily['total_revenue_usd'].sum()/1e6:.1f}M")

        st.markdown("<br>", unsafe_allow_html=True)

        # Agrégats par mois + année
        df_month = df_daily.groupby(["year", "month_num", "month_lbl"]).agg(
            nb_trips=("nb_trips", "sum"),
            total_revenue=("total_revenue_usd", "sum"),
            avg_fare=("avg_fare_usd", "mean"),
            avg_distance=("avg_distance_km", "mean")
        ).reset_index().sort_values(["month_num", "year"])

        c1, c2 = st.columns(2)

        with c1:
            st.markdown('<div class="section-title">Courses par mois — 2024 vs 2025</div>', unsafe_allow_html=True)
            fig1 = go.Figure()
            for year, color in YEAR_COLORS.items():
                d = df_month[df_month["year"] == year]
                if d.empty: continue
                fig1.add_trace(go.Bar(
                    x=d["month_lbl"].values,
                    y=d["nb_trips"].values,
                    name=year,
                    marker_color=color,
                    marker_line_width=0,
                    text=[f"{int(v/1e6*100)/100:.2f}M" for v in d["nb_trips"].values],
                    textposition="outside",
                    textfont=dict(size=10, color="#333")
                ))
            fig1.update_layout(**THEME, height=300, barmode="group",
                legend=dict(bgcolor="rgba(0,0,0,0)"), yaxis_title="Nb courses")
            st.plotly_chart(fig1, use_container_width=True)

        with c2:
            st.markdown('<div class="section-title">Revenus par mois ($M) — 2024 vs 2025</div>', unsafe_allow_html=True)
            fig2 = go.Figure()
            for year, color in YEAR_COLORS.items():
                d = df_month[df_month["year"] == year]
                if d.empty: continue
                fig2.add_trace(go.Bar(
                    x=d["month_lbl"].values,
                    y=(d["total_revenue"].values / 1e6),
                    name=year,
                    marker_color=color,
                    marker_line_width=0,
                    text=[f"${v/1e6:.1f}M" for v in d["total_revenue"].values],
                    textposition="outside",
                    textfont=dict(size=10, color="#333")
                ))
            fig2.update_layout(**THEME, height=300, barmode="group",
                legend=dict(bgcolor="rgba(0,0,0,0)"), yaxis_title="Revenus ($M)")
            st.plotly_chart(fig2, use_container_width=True)

        c3, c4 = st.columns(2)

        with c3:
            st.markdown('<div class="section-title">Tarif moyen par mois — 2024 vs 2025</div>', unsafe_allow_html=True)
            fig3 = go.Figure()
            for year, color in YEAR_COLORS.items():
                d = df_month[df_month["year"] == year].sort_values("month_num")
                if d.empty: continue
                fig3.add_trace(go.Scatter(
                    x=d["month_lbl"].values,
                    y=d["avg_fare"].values,
                    mode="lines+markers+text",
                    name=year,
                    line=dict(color=color, width=3),
                    marker=dict(size=10, color=color, line=dict(color="#FFF", width=2)),
                    text=[f"${v:.2f}" for v in d["avg_fare"].values],
                    textposition="top center",
                    textfont=dict(size=10, color="#333")
                ))
            fig3.update_layout(**THEME, height=280,
                legend=dict(bgcolor="rgba(0,0,0,0)"), yaxis_title="Tarif moyen ($)")
            st.plotly_chart(fig3, use_container_width=True)

        with c4:
            st.markdown('<div class="section-title">Distance moyenne par mois — 2024 vs 2025</div>', unsafe_allow_html=True)
            fig4 = go.Figure()
            for year, color in YEAR_COLORS.items():
                d = df_month[df_month["year"] == year].sort_values("month_num")
                if d.empty: continue
                fig4.add_trace(go.Scatter(
                    x=d["month_lbl"].values,
                    y=d["avg_distance"].values,
                    mode="lines+markers+text",
                    name=year,
                    line=dict(color=color, width=3),
                    marker=dict(size=10, color=color, line=dict(color="#FFF", width=2)),
                    text=[f"{v:.2f} km" for v in d["avg_distance"].values],
                    textposition="top center",
                    textfont=dict(size=10, color="#333")
                ))
            fig4.update_layout(**THEME, height=280,
                legend=dict(bgcolor="rgba(0,0,0,0)"), yaxis_title="Distance (km)")
            st.plotly_chart(fig4, use_container_width=True)

        # Courbe quotidienne par année
        st.markdown('<div class="section-title">Volume quotidien — 2024 vs 2025</div>', unsafe_allow_html=True)
        fig5 = go.Figure()
        for year, color in YEAR_COLORS.items():
            d = df_daily[df_daily["year"] == year]
            if d.empty: continue
            # Aligner sur l'axe jour de l'année pour superposer
            d = d.copy()
            d["day_of_year"] = d["day"].dt.strftime("2000-%m-%d")
            fig5.add_trace(go.Scatter(
                x=d["day_of_year"].values,
                y=d["nb_trips"].values,
                mode="lines",
                name=year,
                line=dict(color=color, width=1.8),
                opacity=0.85
            ))
        fig5.update_layout(**THEME, height=260, yaxis_title="Nb courses",
            legend=dict(bgcolor="rgba(0,0,0,0)"),
            xaxis=dict(gridcolor="#EFEFEF", linecolor="#DDDDDD",
                tickformat="%b", tickcolor="#AAAAAA"))
        st.plotly_chart(fig5, use_container_width=True)

        # Top zones
        if not df_zone.empty:
            st.markdown('<div class="section-title">Top 15 Zones — Revenus cumulés</div>', unsafe_allow_html=True)
            df_top = df_zone.sort_values("total_revenue_usd", ascending=False).head(15).copy()
            label_col = "zone_name" if "zone_name" in df_top.columns else "zone_id"
            df_top["label"] = df_top[label_col].astype(str).str[:25]
            fig6 = go.Figure(go.Bar(
                x=df_top["total_revenue_usd"].values / 1000,
                y=df_top["label"].values,
                orientation="h",
                marker=dict(
                    color=list(range(len(df_top))),
                    colorscale=[[0, "#E8EDFF"], [1, VIOLET]],
                    line_width=0
                )
            ))
            fig6.update_layout(
                paper_bgcolor="#FFFFFF", plot_bgcolor="#FAFBFC",
                font=dict(color="#333333", family="Arial"),
                margin=dict(t=10, b=30, l=10, r=20),
                height=320, showlegend=False,
                xaxis=dict(title="Revenus ($K)", gridcolor="#EFEFEF", linecolor="#DDDDDD"),
                yaxis=dict(gridcolor="#FAFBFC", linecolor="#DDDDDD", tickfont=dict(size=10))
            )
            st.plotly_chart(fig6, use_container_width=True)
    else:
        st.warning("Aucune donnée Gold disponible.")

# ============================================================
# TAB 2 — MÉTÉO
# ============================================================
with tab2:
    with st.spinner(""):
        df_weather = load_s3_parquet("silver/weather_clean/")
        df_daily2  = load_s3_parquet("gold/kpi_daily/")

    if not df_weather.empty and "temperature_2m" in df_weather.columns:
        st.markdown('<div class="section-title">Météo NYC — Q1 2024 & Q1 2025</div>', unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🌡️ Température moy.", f"{df_weather['temperature_2m'].mean():.1f}°C")
        m2.metric("🔴 Max.", f"{df_weather['temperature_2m'].max():.1f}°C")
        m3.metric("🔵 Min.", f"{df_weather['temperature_2m'].min():.1f}°C")
        if "precipitation" in df_weather.columns:
            m4.metric("🌧️ Précipitations", f"{df_weather['precipitation'].sum():.0f} mm")

        st.markdown("<br>", unsafe_allow_html=True)

        if not df_daily2.empty and "date" in df_weather.columns:
            df_daily2["day"] = pd.to_datetime(df_daily2["day"])
            df_daily2 = df_daily2[
                (df_daily2["day"] >= "2024-01-01") &
                (df_daily2["day"] <= "2025-03-31")
            ]
            df_weather["date"] = pd.to_datetime(df_weather["date"])
            df_w_daily = df_weather.groupby("date").agg(
                avg_temp=("temperature_2m", "mean"),
                total_precip=("precipitation", "sum")
            ).reset_index()
            df_corr = df_daily2.merge(df_w_daily, left_on="day", right_on="date", how="inner")

            if not df_corr.empty:
                df_corr["year"] = df_corr["day"].dt.year.astype(str)

                # Température par mois comparée 2024 vs 2025
                st.markdown('<div class="section-title">Température moyenne par mois — 2024 vs 2025</div>', unsafe_allow_html=True)
                df_corr["month_num"] = df_corr["day"].dt.month
                df_corr["month_lbl"] = df_corr["month_num"].map(MONTH_LABELS)
                df_temp_month = df_corr.groupby(["year", "month_num", "month_lbl"]).agg(
                    avg_temp=("avg_temp", "mean"),
                    nb_trips=("nb_trips", "sum")
                ).reset_index().sort_values(["month_num", "year"])

                fig_tm = go.Figure()
                for year, color in YEAR_COLORS.items():
                    d = df_temp_month[df_temp_month["year"] == year]
                    if d.empty: continue
                    fig_tm.add_trace(go.Bar(
                        x=d["month_lbl"].values,
                        y=d["avg_temp"].values,
                        name=year,
                        marker_color=color,
                        marker_line_width=0,
                        text=[f"{v:.1f}°C" for v in d["avg_temp"].values],
                        textposition="outside",
                        textfont=dict(size=10, color="#333")
                    ))
                fig_tm.update_layout(**THEME, height=280, barmode="group",
                    legend=dict(bgcolor="rgba(0,0,0,0)"), yaxis_title="Température moy. (°C)")
                st.plotly_chart(fig_tm, use_container_width=True)

                st.markdown('<div class="section-title">Corrélations Météo → Demande</div>', unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                with c1:
                    fig_c1 = px.scatter(df_corr, x="avg_temp", y="nb_trips",
                        color="year",
                        trendline="ols",
                        color_discrete_map=YEAR_COLORS,
                        labels={"avg_temp": "Température moy. (°C)", "nb_trips": "Nb courses", "year": "Année"})
                    fig_c1.update_traces(marker=dict(size=8, opacity=0.65))
                    fig_c1.update_layout(**THEME, title="🌡️ Température vs Courses", height=300,
                        legend=dict(bgcolor="rgba(0,0,0,0)"))
                    st.plotly_chart(fig_c1, use_container_width=True)
                with c2:
                    fig_c2 = px.scatter(df_corr, x="total_precip", y="nb_trips",
                        color="year",
                        trendline="ols",
                        color_discrete_map=YEAR_COLORS,
                        labels={"total_precip": "Précipitations (mm)", "nb_trips": "Nb courses", "year": "Année"})
                    fig_c2.update_traces(marker=dict(size=8, opacity=0.65))
                    fig_c2.update_layout(**THEME, title="🌧️ Précipitations vs Courses", height=300,
                        legend=dict(bgcolor="rgba(0,0,0,0)"))
                    st.plotly_chart(fig_c2, use_container_width=True)
    else:
        st.warning("Aucune donnée météo.")

# ============================================================
# TAB 3 — STREAMING
# ============================================================
with tab3:
    col_refresh, _ = st.columns([1, 6])
    with col_refresh:
        if st.button("🔄 Rafraîchir", use_container_width=True):
            st.cache_data.clear()

    realtime     = load_realtime()
    total_events = realtime.get("events_count", 0)
    events       = realtime.get("latest_events", [])

    if events:
        df_rt = pd.DataFrame(events)
        for c in ["total_amount", "trip_distance", "passenger_count"]:
            if c in df_rt.columns:
                df_rt[c] = pd.to_numeric(df_rt[c], errors="coerce")

        st.markdown('<div class="section-title">KPIs Temps Réel</div>', unsafe_allow_html=True)
        k1, k2, k3 = st.columns(3)
        if "total_amount" in df_rt.columns:
            k1.metric("💰 Montant moyen", f"${df_rt['total_amount'].mean():.2f}")
            k2.metric("💵 Revenu estimé", f"${df_rt['total_amount'].sum():.0f}")
        if "trip_distance" in df_rt.columns:
            k3.metric("📏 Distance moy.", f"{df_rt['trip_distance'].mean():.2f} km")

        st.markdown("<br>", unsafe_allow_html=True)

        if "total_amount" in df_rt.columns:
            df_rt["anomalie"] = df_rt["total_amount"] > 55
            nb_anomalies = int(df_rt["anomalie"].sum())
            if nb_anomalies > 0:
                st.markdown(f'<div class="alert-box">⚠️ <strong>{nb_anomalies} course(s) à montant élevé</strong> — Seuil de détection : $55</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="ok-box">✅ Aucune anomalie détectée sur les derniers événements</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)

        with c1:
            st.markdown('<div class="section-title">Distribution des montants ($)</div>', unsafe_allow_html=True)
            if "total_amount" in df_rt.columns:
                fig_fare = go.Figure()
                fig_fare.add_trace(go.Histogram(
                    x=df_rt["total_amount"].dropna(),
                    nbinsx=15,
                    marker_color=VIOLET,
                    marker_line_color="#FFFFFF",
                    marker_line_width=1,
                    opacity=0.85
                ))
                fig_fare.add_vline(x=55, line_dash="dash", line_color=CORAL,
                    annotation_text="Seuil $55", annotation_font_color=CORAL)
                fig_fare.update_layout(**THEME, height=250, showlegend=False,
                    xaxis_title="Montant ($)", yaxis_title="Fréquence")
                st.plotly_chart(fig_fare, use_container_width=True)

        with c2:
            st.markdown('<div class="section-title">Courses par arrondissement</div>', unsafe_allow_html=True)
            if "pickup_borough" in df_rt.columns:
                borough_data = df_rt["pickup_borough"].value_counts().reset_index()
                borough_data.columns = ["borough", "count"]
                fig_b = go.Figure(go.Bar(
                    x=borough_data["borough"].values,
                    y=borough_data["count"].values,
                    marker_color=[VIOLET, TEAL, CORAL, GREEN, ORANGE][:len(borough_data)],
                    marker_line_width=0,
                    text=borough_data["count"].values,
                    textposition="outside",
                    textfont=dict(color="#333333", size=11)
                ))
                fig_b.update_layout(**THEME, height=250, showlegend=False)
                st.plotly_chart(fig_b, use_container_width=True)

        c3, c4 = st.columns(2)

        with c3:
            st.markdown('<div class="section-title">Mode de paiement</div>', unsafe_allow_html=True)
            if "payment_type" in df_rt.columns:
                pay_data = df_rt["payment_type"].value_counts().reset_index()
                pay_data.columns = ["type", "count"]
                fig_pie = go.Figure(go.Pie(
                    labels=pay_data["type"].values,
                    values=pay_data["count"].values,
                    hole=0.55,
                    marker_colors=[VIOLET, TEAL, CORAL, GREEN],
                    textfont=dict(size=12)
                ))
                fig_pie.add_annotation(
                    text=f"<b>{len(df_rt)}</b><br>courses",
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(size=13, color="#333333")
                )
                fig_pie.update_layout(**THEME, height=250, showlegend=True,
                    legend=dict(font=dict(color="#333333"), bgcolor="rgba(0,0,0,0)"))
                st.plotly_chart(fig_pie, use_container_width=True)

        with c4:
            st.markdown('<div class="section-title">Revenu moyen par arrondissement</div>', unsafe_allow_html=True)
            if "pickup_borough" in df_rt.columns and "total_amount" in df_rt.columns:
                rev_b = df_rt.groupby("pickup_borough")["total_amount"].mean().reset_index()
                rev_b.columns = ["borough", "avg"]
                rev_b = rev_b.sort_values("avg", ascending=True)
                fig_rev = go.Figure(go.Bar(
                    x=rev_b["avg"].values,
                    y=rev_b["borough"].values,
                    orientation="h",
                    marker=dict(
                        color=list(range(len(rev_b))),
                        colorscale=[[0, "#E8EDFF"], [1, VIOLET]],
                        line_width=0
                    ),
                    text=[f"${v:.1f}" for v in rev_b["avg"].values],
                    textposition="outside",
                    textfont=dict(color="#333333", size=11)
                ))
                fig_rev.update_layout(**THEME, height=250, showlegend=False,
                    xaxis_title="Montant moyen ($)")
                st.plotly_chart(fig_rev, use_container_width=True)
    else:
        st.markdown("""
        <div style="text-align:center; padding:3rem; color:#AAAAAA;">
            <div style="font-size:3.5rem">⚡</div>
            <div style="font-size:1.1rem; margin-top:1rem; color:#666;">Aucune donnée streaming disponible</div>
            <div style="font-size:0.85rem; margin-top:0.5rem;">Lance le producer Kafka sur l'EC2 pour alimenter ce dashboard</div>
        </div>
        """, unsafe_allow_html=True)
