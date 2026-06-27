
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# =========================
# PAGE SETUP
# =========================
st.set_page_config(
    page_title="Basketball Analytics App",
    layout="wide"
)

# =========================
# LOGO + HEADER
# =========================
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    st.image(
        logotnib.jpg",
        width=260
    )

st.title("🏀 Basketball Analytics App")
st.markdown(
    "Zoek spelers, open spelerprofielen, ontdek vergelijkbare spelers en vergelijk spelers met elkaar."
)

# =========================
# DATA LADEN
# =========================
df = pd.read_excel(
    "basketball_FULL_dataset_2025_2026.xlsx",
    sheet_name="Merged"
)

# =========================
# HULPFUNCTIES
# =========================
def safe_get(series, col_name, default=0):
    return series[col_name] if col_name in series.index else default

def safe_numeric(series, col_name, default=0.0):
    val = safe_get(series, col_name, default)
    try:
        return float(val)
    except:
        return default

def format_metric_value(value, decimals=1):
    try:
        return f"{float(value):.{decimals}f}"
    except:
        return "-"

def build_typeahead_select(label, players, key_prefix, default_player=None):
    """
    Type-ahead search + selectbox.
    Als default_player meegegeven wordt, wordt die waar mogelijk standaard geselecteerd.
    """
    query = st.text_input(f"🔍 {label} zoeken", key=f"{key_prefix}_search")

    if query:
        matches = [p for p in players if query.lower() in p.lower()]
        matches = matches[:50]
        if not matches:
            st.warning(f"Geen spelers gevonden voor '{query}'")
            return None

        default_index = 0
        if default_player and default_player in matches:
            default_index = matches.index(default_player)

        return st.selectbox(
            label,
            matches,
            index=default_index,
            key=f"{key_prefix}_select"
        )

    # Geen query → volledige lijst, maar default speler vooraan zetten indien bekend
    if default_player and default_player in players:
        ordered_players = [default_player] + [p for p in players if p != default_player]
    else:
        ordered_players = players

    return st.selectbox(
        label,
        ordered_players,
        index=0,
        key=f"{key_prefix}_select"
    )

def robust_normalize(value, col_name, dataframe, lower_q=0.05, upper_q=0.95):
    """
    Normaliseert naar 0-100, maar clipt eerst op percentielen.
    Hierdoor verpesten outliers de radar chart minder.
    """
    try:
        series = pd.to_numeric(dataframe[col_name], errors="coerce").dropna()

        if series.empty:
            return 0.0

        low = series.quantile(lower_q)
        high = series.quantile(upper_q)

        if high == low:
            return 50.0

        clipped = min(max(float(value), low), high)
        norm = ((clipped - low) / (high - low)) * 100
        return round(norm, 1)
    except:
        return 0.0

def get_radar_stats_for_player(player_row, dataframe):
    """
    Stats die in de radar chart komen.
    """
    radar_cols = ["PPG", "APG", "RPG", "PER", "FG%", "3P%"]

    stats = {}
    for col in radar_cols:
        if col in dataframe.columns:
            raw_value = safe_numeric(player_row, col)
            stats[col] = robust_normalize(raw_value, col, dataframe)

    return stats

def build_radar_figure(player_names, stat_values_dict, title="Radar Chart"):
    categories = list(next(iter(stat_values_dict.values())).keys())

    fig = go.Figure()

    for player_name in player_names:
        values = list(stat_values_dict[player_name].values())
        values_closed = values + [values[0]]
        categories_closed = categories + [categories[0]]

        fig.add_trace(go.Scatterpolar(
            r=values_closed,
            theta=categories_closed,
            fill="toself",
            name=player_name
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100]
            )
        ),
        showlegend=True,
        title=title,
        height=500
    )

    return fig

# =========================
# FILTERS
# =========================
st.markdown("---")
st.subheader("🎯 Filters")

f1, f2, f3 = st.columns(3)

with f1:
    global_search = st.text_input("🔎 Zoek speler in resultaten")

with f2:
    position = st.selectbox(
        "📍 Positie",
        ["Alle"] + sorted(df["Position_avg"].dropna().astype(str).unique())
    )

with f3:
    per_min = float(df["PER"].min())
    per_max = float(df["PER"].max())

    per_range = st.slider(
        "📊 PER filter",
        min_value=round(per_min, 1),
        max_value=round(per_max, 1),
        value=(round(per_min, 1), round(per_max, 1))
    )

# =========================
# FILTER LOGIC
# =========================
filtered_df = df.copy()

if global_search:
    filtered_df = filtered_df[
        filtered_df["Player"].astype(str).str.contains(global_search, case=False, na=False)
    ]

if position != "Alle":
    filtered_df = filtered_df[
        filtered_df["Position_avg"].astype(str) == position
    ]

filtered_df = filtered_df[
    (filtered_df["PER"] >= per_range[0]) &
    (filtered_df["PER"] <= per_range[1])
]

# =========================
# SELECTED PLAYER SESSION
# =========================
if "selected_player" not in st.session_state:
    if not filtered_df.empty:
        st.session_state["selected_player"] = filtered_df.iloc[0]["Player"]
    else:
        st.session_state["selected_player"] = None

# =========================
# RESULTATEN + KLIKBARE SPELERS
# =========================
st.markdown("---")
st.subheader("📋 Spelerslijst")

left, right = st.columns([1.2, 1.8])

with left:
    st.write(f"**Aantal spelers gevonden:** {len(filtered_df)}")

    result_cols = ["Player", "Team", "Position_avg", "PPG", "APG", "RPG", "PER"]
    result_cols = [c for c in result_cols if c in filtered_df.columns]

    preview_df = filtered_df[result_cols].sort_values("PPG", ascending=False).head(50)

    st.markdown("### Klik op een speler")

    for idx, row in preview_df.iterrows():
        c1, c2 = st.columns([3, 1])

        with c1:
            st.markdown(
                f"**{row['Player']}**  \n"
                f"{row['Team']} | {row['Position_avg']} | "
                f"PPG: {row['PPG']} | APG: {row['APG']} | RPG: {row['RPG']} | PER: {row['PER']}"
            )

        with c2:
            if st.button("Open profiel", key=f"profile_{idx}"):
                st.session_state["selected_player"] = row["Player"]

with right:
    st.subheader("🧑 Spelerprofiel")

    if st.session_state["selected_player"] is None:
        st.info("Geen speler geselecteerd.")
    else:
        player_name = st.session_state["selected_player"]
        player_df = df[df["Player"] == player_name]

        if player_df.empty:
            st.warning("Geen data gevonden voor deze speler.")
        else:
            player = player_df.iloc[0]

            st.markdown(f"## {player['Player']}")
            st.write(f"**Team:** {safe_get(player, 'Team', '-')}")
            st.write(f"**Positie:** {safe_get(player, 'Position_avg', '-')}")

            # =====================
            # CORE STATS
            # =====================
            st.markdown("### 📊 Core Stats")
            c1, c2, c3, c4 = st.columns(4)

            c1.metric("PPG", format_metric_value(safe_numeric(player, "PPG")))
            c2.metric("APG", format_metric_value(safe_numeric(player, "APG")))
            c3.metric("RPG", format_metric_value(safe_numeric(player, "RPG")))
            c4.metric("PER", format_metric_value(safe_numeric(player, "PER")))

            # =====================
            # RADAR CHART PROFILE
            # =====================
            st.markdown("### 🕸 Radar Chart")

            player_radar_stats = get_radar_stats_for_player(player, df)

            profile_radar_fig = build_radar_figure(
                player_names=[player["Player"]],
                stat_values_dict={
                    player["Player"]: player_radar_stats
                },
                title=f"Radar Profile – {player['Player']}"
            )

            st.plotly_chart(profile_radar_fig, use_container_width=True)
            st.caption("Radar chart gebruikt robuuste normalisatie met clipping op het 5e en 95e percentiel.")

            # =====================
            # SHOOTING
            # =====================
            st.markdown("### 🎯 Shooting")
            s1, s2, s3 = st.columns(3)

            s1.metric("FG%", format_metric_value(safe_numeric(player, "FG%"), 3))
            s2.metric("3P%", format_metric_value(safe_numeric(player, "3P%"), 3))
            s3.metric("FT%", format_metric_value(safe_numeric(player, "FT%"), 3))

            # =====================
            # ALLE STATS
            # =====================
            st.markdown("### 📋 Alle stats")
            st.dataframe(player_df, use_container_width=True)

            # =====================
            # VERGELIJKBARE SPELERS
            # =====================
            st.markdown("---")
            st.subheader(f"🔎 Vergelijkbare spelers voor {player_name}")

            same_position_only = st.checkbox("Alleen dezelfde positie", value=True)

            t1, t2, t3, t4 = st.columns(4)

            with t1:
                ppg_tol = st.slider("PPG marge", 0.0, 10.0, 3.0, 0.5)

            with t2:
                apg_tol = st.slider("APG marge", 0.0, 10.0, 2.0, 0.5)

            with t3:
                rpg_tol = st.slider("RPG marge", 0.0, 10.0, 2.0, 0.5)

            with t4:
                per_tol = st.slider("PER marge", 0.0, 15.0, 3.0, 0.5)

            player_ppg = safe_numeric(player, "PPG")
            player_apg = safe_numeric(player, "APG")
            player_rpg = safe_numeric(player, "RPG")
            player_per = safe_numeric(player, "PER")

            similar_df = df.copy()

            # speler zelf uitsluiten
            similar_df = similar_df[similar_df["Player"] != player_name]

            # positie filter
            if same_position_only:
                similar_df = similar_df[
                    similar_df["Position_avg"] == safe_get(player, "Position_avg", "")
                ]

            # criteria toepassen
            similar_df = similar_df[
                similar_df["PPG"].between(player_ppg - ppg_tol, player_ppg + ppg_tol)
                &
                similar_df["APG"].between(player_apg - apg_tol, player_apg + apg_tol)
                &
                similar_df["RPG"].between(player_rpg - rpg_tol, player_rpg + rpg_tol)
                &
                similar_df["PER"].between(player_per - per_tol, player_per + per_tol)
            ].copy()

            if not similar_df.empty:
                similar_df["SimilarityScore"] = (
                    (similar_df["PPG"] - player_ppg).abs()
                    + (similar_df["APG"] - player_apg).abs()
                    + (similar_df["RPG"] - player_rpg).abs()
                    + (similar_df["PER"] - player_per).abs()
                )

                similar_df = similar_df.sort_values("SimilarityScore")

                sim_cols = [
                    "Player",
                    "Team",
                    "Position_avg",
                    "PPG",
                    "APG",
                    "RPG",
                    "PER",
                    "SimilarityScore"
                ]

                sim_cols = [c for c in sim_cols if c in similar_df.columns]

                st.write(f"**{len(similar_df)} vergelijkbare spelers gevonden**")

                sim_preview = similar_df[sim_cols].head(15)

                for idx, row in sim_preview.iterrows():
                    c1, c2 = st.columns([3, 1])

                    with c1:
                        st.markdown(
                            f"**{row['Player']}**  \n"
                            f"{row['Team']} | {row['Position_avg']} | "
                            f"PPG: {row['PPG']} | APG: {row['APG']} | RPG: {row['RPG']} | "
                            f"PER: {row['PER']} | Similarity: {round(row['SimilarityScore'], 2)}"
                        )

                    with c2:
                        if st.button("Open profiel", key=f"similar_{idx}"):
                            st.session_state["selected_player"] = row["Player"]

            else:
                st.info("Geen vergelijkbare spelers gevonden met deze criteria.")

# =========================
# PLAYER COMPARISON
# =========================
st.markdown("---")
st.subheader("🆚 Player Comparison")

all_players = sorted(df["Player"].dropna().astype(str).unique().tolist())

# Geselecteerde profielspeler automatisch als Player 1
default_player1 = st.session_state.get("selected_player", all_players[0])

if default_player1 not in all_players:
    default_player1 = all_players[0]

default_player2_candidates = [p for p in all_players if p != default_player1]
default_player2 = default_player2_candidates[0] if default_player2_candidates else default_player1

c1, c2 = st.columns(2)

with c1:
    player1 = build_typeahead_select(
        "Player 1",
        all_players,
        "player1",
        default_player=default_player1
    )

with c2:
    player2 = build_typeahead_select(
        "Player 2",
        all_players,
        "player2",
        default_player=default_player2
    )

if player1 and player2:
    p1_df = df[df["Player"] == player1]
    p2_df = df[df["Player"] == player2]

    if not p1_df.empty and not p2_df.empty:
        p1 = p1_df.iloc[0]
        p2 = p2_df.iloc[0]

        left, right = st.columns(2)

        with left:
            st.markdown(f"### {player1}")
            st.write(f"**Team:** {safe_get(p1, 'Team', '-')}")
            st.write(f"**Positie:** {safe_get(p1, 'Position_avg', '-')}")

        with right:
            st.markdown(f"### {player2}")
            st.write(f"**Team:** {safe_get(p2, 'Team', '-')}")
            st.write(f"**Positie:** {safe_get(p2, 'Position_avg', '-')}")

        st.markdown("#### Key Stats")

        k1, k2, k3, k4 = st.columns(4)

        p1_ppg = safe_numeric(p1, "PPG")
        p2_ppg = safe_numeric(p2, "PPG")

        p1_apg = safe_numeric(p1, "APG")
        p2_apg = safe_numeric(p2, "APG")

        p1_rpg = safe_numeric(p1, "RPG")
        p2_rpg = safe_numeric(p2, "RPG")

        p1_per = safe_numeric(p1, "PER")
        p2_per = safe_numeric(p2, "PER")

        k1.metric("PPG", format_metric_value(p1_ppg), format_metric_value(p1_ppg - p2_ppg))
        k2.metric("APG", format_metric_value(p1_apg), format_metric_value(p1_apg - p2_apg))
        k3.metric("RPG", format_metric_value(p1_rpg), format_metric_value(p1_rpg - p2_rpg))
        k4.metric("PER", format_metric_value(p1_per), format_metric_value(p1_per - p2_per))

        st.markdown("#### 🎯 Shooting")

        s1, s2, s3 = st.columns(3)

        p1_fg = safe_numeric(p1, "FG%")
        p2_fg = safe_numeric(p2, "FG%")

        p1_3p = safe_numeric(p1, "3P%")
        p2_3p = safe_numeric(p2, "3P%")

        p1_ft = safe_numeric(p1, "FT%")
        p2_ft = safe_numeric(p2, "FT%")

        s1.metric("FG%", format_metric_value(p1_fg, 3), format_metric_value(p1_fg - p2_fg, 3))
        s2.metric("3P%", format_metric_value(p1_3p, 3), format_metric_value(p1_3p - p2_3p, 3))
        s3.metric("FT%", format_metric_value(p1_ft, 3), format_metric_value(p1_ft - p2_ft, 3))

        # =====================
        # RADAR CHART COMPARISON
        # =====================
        st.markdown("#### 🕸 Radar Comparison")

        p1_radar_stats = get_radar_stats_for_player(p1, df)
        p2_radar_stats = get_radar_stats_for_player(p2, df)

        compare_radar_fig = build_radar_figure(
            player_names=[player1, player2],
            stat_values_dict={
                player1: p1_radar_stats,
                player2: p2_radar_stats
            },
            title=f"Radar Comparison – {player1} vs {player2}"
        )

        st.plotly_chart(compare_radar_fig, use_container_width=True)
        st.caption("Vergelijkingschart gebruikt robuuste normalisatie met clipping op het 5e en 95e percentiel.")
