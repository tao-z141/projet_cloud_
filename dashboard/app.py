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
    page_icon=":taxi:",
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

YEAR_COLORS  = {"2024": VIOLET, "2025": CORAL}
MONTH_LABELS = {1: "Jan", 2: "Fev", 3: "Mar", 4: "Avr"}

BUCKET      = "nyc-taxi-platform"
API_URL     = "https://thg365gege.execute-api.eu-west-3.amazonaws.com/prod"
AWS_REGION  = "eu-west-3"
AWS_KEY     = st.secrets.get("AWS_ACCESS_KEY_ID", os.environ.get("AWS_ACCESS_KEY_ID"))
AWS_SECRET  = st.secrets.get("AWS_SECRET_ACCESS_KEY", os.environ.get("AWS_SECRET_ACCESS_KEY"))
COGNITO_CLIENT_ID = st.secrets.get("COGNITO_CLIENT_ID", os.environ.get("COGNITO_CLIENT_ID"))

# =========================
# AUTHENTIFICATION COGNITO - LOGIN INTERACTIF
# =========================
def cognito_login(username, password):
    try:
        client = boto3.client("cognito-idp", region_name=AWS_REGION,
            aws_access_key_id=AWS_KEY, aws_secret_access_key=AWS_SECRET)
        response = client.initiate_auth(
            ClientId=COGNITO_CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": username,
                "PASSWORD": password
            }
        )
        if "AuthenticationResult" in response:
            return response["AuthenticationResult"]["IdToken"], None, None
        elif response.get("ChallengeName") == "NEW_PASSWORD_REQUIRED":
            return None, "NEW_PASSWORD_REQUIRED", response["Session"]
        elif "ChallengeName" in response:
            return None, f"Challenge non gere : {response['ChallengeName']}", None
        else:
            return None, f"Reponse inattendue : {response}", None
    except Exception as e:
        return None, str(e), None

def cognito_set_new_password(username, new_password, session):
    try:
        client = boto3.client("cognito-idp", region_name=AWS_REGION,
            aws_access_key_id=AWS_KEY, aws_secret_access_key=AWS_SECRET)
        response = client.respond_to_auth_challenge(
            ClientId=COGNITO_CLIENT_ID,
            ChallengeName="NEW_PASSWORD_REQUIRED",
            Session=session,
            ChallengeResponses={
                "USERNAME": username,
                "NEW_PASSWORD": new_password
            }
        )
        return response["AuthenticationResult"]["IdToken"], None
    except Exception as e:
        return None, str(e)

def show_login_screen():
    st.markdown("""
    <div style="max-width:420px; margin: 4rem auto; text-align:center;">
        <h1 style="color:#1A1A2E; font-size:1.8rem; margin-bottom:0.3rem;">NYC Taxi Data Platform</h1>
        <p style="color:#888; font-size:0.9rem; margin-bottom:2rem;">Connexion requise</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        # Etape 2 : nouveau mot de passe requis par Cognito
        if st.session_state.get("pending_new_password"):
            st.info("Premiere connexion : merci de definir un nouveau mot de passe.")
            with st.form("new_password_form"):
                new_password = st.text_input("Nouveau mot de passe", type="password")
                confirm_password = st.text_input("Confirmer le mot de passe", type="password")
                submit_np = st.form_submit_button("Valider", use_container_width=True)

                if submit_np:
                    if not new_password or new_password != confirm_password:
                        st.error("Les mots de passe ne correspondent pas.")
                    else:
                        token, error = cognito_set_new_password(
                            st.session_state["pending_username"],
                            new_password,
                            st.session_state["pending_session"]
                        )
                        if token:
                            st.session_state["auth_token"] = token
                            st.session_state["username"] = st.session_state["pending_username"]
                            del st.session_state["pending_new_password"]
                            del st.session_state["pending_username"]
                            del st.session_state["pending_session"]
                            st.rerun()
                        else:
                            st.error(f"Erreur : {error}")
            return

        # Etape 1 : login classique
        with st.form("login_form"):
            username = st.text_input("Email")
            password = st.text_input("Mot de passe", type="password")
            submit = st.form_submit_button("Se connecter", use_container_width=True)

            if submit:
                if not username or not password:
                    st.error("Merci de renseigner email et mot de passe.")
                else:
                    token, error, session = cognito_login(username, password)
                    if token:
                        st.session_state["auth_token"] = token
                        st.session_state["username"] = username
                        st.rerun()
                    elif error == "NEW_PASSWORD_REQUIRED":
                        st.session_state["pending_new_password"] = True
                        st.session_state["pending_username"] = username
                        st.session_state["pending_session"] = session
                        st.rerun()
                    else:
                        st.error(f"Echec de connexion : {error}")

def api_headers():
    token = st.session_state.get("auth_token")
    if token:
        return {"Authorization": token}
    return {}

# Bloque l'acces tant que l'utilisateur n'est pas authentifie
if "auth_token" not in st.session_state:
    show_login_screen()
    st.stop()

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
        r = requests.get(f"{API_URL}/realtime", headers=api_headers(), timeout=5)
        return r.json()
    except:
        return {"events_count": 0, "latest_events": []}

# Header
header_col1, header_col2 = st.columns([5, 1])
with header_col1:
    st.markdown("""
    <div class="nyc-header">
        <div><h1>NYC Taxi Data Platform</h1></div>
    </div>
    """, unsafe_allow_html=True)
with header_col2:
    st.markdown("<div style='padding-top:1.8rem'></div>", unsafe_allow_html=True)
    if st.button("Deconnexion", use_container_width=True):
        del st.session_state["auth_token"]
        st.rerun()

tab1, tab2, tab3 = st.tabs([
    "Performance Operationnelle",
    "Impact Meteo",
    "Supervision Temps Reel"
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
            (df_daily["day"].dt.month <= 3) &
            (df_daily["day"].dt.year.isin([2024, 2025]))
        ].sort_values("day")

        df_daily["year"]      = df_daily["day"].dt.year.astype(str)
        df_daily["month_num"] = df_daily["day"].dt.month
        df_daily["month_lbl"] = df_daily["month_num"].map(MONTH_LABELS)

        st.markdown('<div class="section-title">KPIs Globaux - Jan Fev Mar 2024 vs 2025</div>', unsafe_allow_html=True)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Courses", f"{int(df_daily['nb_trips'].sum()):,}")
        k2.metric("Tarif Moyen", f"${df_daily['avg_fare_usd'].mean():.2f}")
        k3.metric("Distance Moy.", f"{df_daily['avg_distance_km'].mean():.2f} km")
        k4.metric("Revenus Totaux", f"${df_daily['total_revenue_usd'].sum()/1e6:.1f}M")

        st.markdown("<br>", unsafe_allow_html=True)

        df_month = df_daily.groupby(["year", "month_num", "month_lbl"]).agg(
            nb_trips=("nb_trips", "sum"),
            total_revenue=("total_revenue_usd", "sum"),
            avg_fare=("avg_fare_usd", "mean"),
            avg_distance=("avg_distance_km", "mean")
        ).reset_index().sort_values(["month_num", "year"])

        c1, c2 = st.columns(2)

        with c1:
            st.markdown('<div class="section-title">Courses par mois - 2024 vs 2025</div>', unsafe_allow_html=True)
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
            st.markdown('<div class="section-title">Revenus par mois ($M) - 2024 vs 2025</div>', unsafe_allow_html=True)
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
            st.markdown('<div class="section-title">Tarif moyen par mois - 2024 vs 2025</div>', unsafe_allow_html=True)
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
            st.markdown('<div class="section-title">Distance moyenne par mois - 2024 vs 2025</div>', unsafe_allow_html=True)
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

        st.markdown('<div class="section-title">Volume quotidien - 2024 vs 2025</div>', unsafe_allow_html=True)
        fig5 = go.Figure()
        for year, color in YEAR_COLORS.items():
            d = df_daily[df_daily["year"] == year]
            if d.empty: continue
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
            xaxis_tickformat="%b")
        st.plotly_chart(fig5, use_container_width=True)

        if not df_zone.empty:
            st.markdown('<div class="section-title">Top 15 Zones - Revenus cumules</div>', unsafe_allow_html=True)
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
        st.warning("Aucune donnee Gold disponible.")

# ============================================================
# TAB 2 — METEO
# ============================================================
with tab2:
    with st.spinner(""):
        df_weather = load_s3_parquet("silver/weather_clean/")
        df_daily2  = load_s3_parquet("gold/kpi_daily/")

    if not df_weather.empty and "temperature_2m" in df_weather.columns:
        st.markdown('<div class="section-title">Meteo NYC - Jan Fev Mar 2024 et 2025</div>', unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Temperature moy.", f"{df_weather['temperature_2m'].mean():.1f}C")
        m2.metric("Max.", f"{df_weather['temperature_2m'].max():.1f}C")
        m3.metric("Min.", f"{df_weather['temperature_2m'].min():.1f}C")
        if "precipitation" in df_weather.columns:
            m4.metric("Precipitations", f"{df_weather['precipitation'].sum():.0f} mm")

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
                df_corr["month_num"] = df_corr["day"].dt.month
                df_corr["month_lbl"] = df_corr["month_num"].map(MONTH_LABELS)
                st.markdown('<div class="section-title">Correlations Meteo vers Demande</div>', unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                with c1:
                    fig_c1 = px.scatter(df_corr, x="avg_temp", y="nb_trips",
                        color="year",
                        trendline="ols",
                        color_discrete_map=YEAR_COLORS,
                        labels={"avg_temp": "Temperature moy. (C)", "nb_trips": "Nb courses", "year": "Annee"})
                    fig_c1.update_traces(marker=dict(size=8, opacity=0.65))
                    fig_c1.update_layout(**THEME, title="Temperature vs Courses", height=300,
                        legend=dict(bgcolor="rgba(0,0,0,0)"))
                    st.plotly_chart(fig_c1, use_container_width=True)
                with c2:
                    fig_c2 = px.scatter(df_corr, x="total_precip", y="nb_trips",
                        color="year",
                        trendline="ols",
                        color_discrete_map=YEAR_COLORS,
                        labels={"total_precip": "Precipitations (mm)", "nb_trips": "Nb courses", "year": "Annee"})
                    fig_c2.update_traces(marker=dict(size=8, opacity=0.65))
                    fig_c2.update_layout(**THEME, title="Precipitations vs Courses", height=300,
                        legend=dict(bgcolor="rgba(0,0,0,0)"))
                    st.plotly_chart(fig_c2, use_container_width=True)
    else:
        st.warning("Aucune donnee meteo.")

# ============================================================
# TAB 3 — STREAMING
# ============================================================
with tab3:
    col_refresh, _ = st.columns([1, 6])
    with col_refresh:
        if st.button("Rafraichir", use_container_width=True):
            st.cache_data.clear()

    realtime     = load_realtime()
    total_events = realtime.get("events_count", 0)
    events       = realtime.get("latest_events", [])

    if events:
        df_rt = pd.DataFrame(events)
        for c in ["total_amount", "trip_distance", "passenger_count"]:
            if c in df_rt.columns:
                df_rt[c] = pd.to_numeric(df_rt[c], errors="coerce")

        st.markdown('<div class="section-title">KPIs Temps Reel</div>', unsafe_allow_html=True)
        k1, k2, k3 = st.columns(3)
        if "total_amount" in df_rt.columns:
            k1.metric("Montant moyen", f"${df_rt['total_amount'].mean():.2f}")
            k2.metric("Revenu estime", f"${df_rt['total_amount'].sum():.0f}")
        if "trip_distance" in df_rt.columns:
            k3.metric("Distance moy.", f"{df_rt['trip_distance'].mean():.2f} km")

        st.markdown("<br>", unsafe_allow_html=True)

        if "total_amount" in df_rt.columns:
            df_rt["anomalie"] = df_rt["total_amount"] > 55
            nb_anomalies = int(df_rt["anomalie"].sum())
            if nb_anomalies > 0:
                st.markdown(f'<div class="alert-box"><strong>{nb_anomalies} course(s) a montant eleve</strong> - Seuil de detection : $55</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="ok-box">Aucune anomalie detectee sur les derniers evenements</div>', unsafe_allow_html=True)

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
                    xaxis_title="Montant ($)", yaxis_title="Frequence")
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
            <div style="font-size:1.1rem; margin-top:1rem; color:#666;">Aucune donnee streaming disponible</div>
            <div style="font-size:0.85rem; margin-top:0.5rem;">Lance le producer Kafka sur l'EC2 pour alimenter ce dashboard</div>
        </div>
        """, unsafe_allow_html=True)
