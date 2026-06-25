"""
Дашборд League of Legends
Стек: DuckDB + Parquet + Streamlit + Plotly
Запуск: python -m streamlit run app.py
"""

import duckdb
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

# ============================================================================
# НАСТРОЙКА СТРАНИЦЫ
# ============================================================================
st.set_page_config(
    page_title="LoL Analytics Dashboard",
    page_icon="🎮",
    layout="wide"
)

st.title("🎮 League of Legends - Аналитика рейтинговых игр")
st.markdown("*Данные собраны за текущий месяц | Источник: Riot Games API*")
st.markdown("---")

# ============================================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================================
@st.cache_resource
def load_data():
    """Загружает данные из Parquet файлов через DuckDB"""
    conn = duckdb.connect()
    
    players = conn.execute("SELECT * FROM 'data/players_data.parquet'").df()
    matches = conn.execute("SELECT * FROM 'data/matches_data.parquet'").df()
    champions = conn.execute("SELECT * FROM 'data/champions_data.parquet'").df()
    
    return conn, players, matches, champions

with st.spinner("Загрузка данных..."):
    conn, players_df, matches_df, champions_df = load_data()

st.success(f"✅ Загружено: {len(players_df):,} игроков, {len(matches_df):,} матчей, {len(champions_df)} чемпионов")

# ============================================================================
# САЙДБАР
# ============================================================================
st.sidebar.header("🔍 Фильтры")

region_filter = st.sidebar.radio(
    "Выберите регион",
    options=["🌍 Все регионы", "🇪🇺 EUW", "🇺🇸 NA"],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.subheader("📊 Статистика")

if region_filter == "🇪🇺 EUW":
    region = "euw1"
    players_df_filtered = players_df[players_df["region"] == region]
    matches_df_filtered = matches_df[matches_df["region"] == region]
elif region_filter == "🇺🇸 NA":
    region = "na1"
    players_df_filtered = players_df[players_df["region"] == region]
    matches_df_filtered = matches_df[matches_df["region"] == region]
else:
    players_df_filtered = players_df
    matches_df_filtered = matches_df

st.sidebar.metric("Игроков", f"{len(players_df_filtered):,}")
st.sidebar.metric("Матчей", f"{len(matches_df_filtered):,}")
st.sidebar.metric("Чемпионов", len(champions_df))

# Фильтр по минимальному количеству матчей для чемпионов
min_matches = st.sidebar.slider(
    "Минимум матчей у чемпиона для анализа",
    min_value=100,
    max_value=5000,
    value=500,
    step=100
)

# ============================================================================
# ВКЛАДКИ ДЛЯ РАЗНЫХ АНАЛИТИК
# ============================================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Общая статистика",
    "🏆 Анализ чемпионов",
    "🌍 Сравнение регионов",
    "📈 Аномалии LP и винрейта",
    "🧩 Кластеризация игроков"
])

# ============================================================================
# TAB 1: ОБЩАЯ СТАТИСТИКА (было)
# ============================================================================
with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Распределение игроков по LP")
        fig_lp = px.histogram(
            players_df_filtered,
            x="league_points",
            nbins=30,
            title="Очки лиги (LP)",
            labels={"league_points": "LP", "count": "Количество игроков"},
            color_discrete_sequence=["#1f77b4"]
        )
        st.plotly_chart(fig_lp, width='stretch')
    
    with col2:
        st.subheader("⏱️ Длительность матчей")
        fig_duration = px.box(
            matches_df_filtered,
            y="game_duration_sec",
            title="Распределение длительности",
            labels={"game_duration_sec": "Длительность (сек)"}
        )
        fig_duration.update_layout(
            yaxis=dict(
                tickvals=[0, 300, 600, 900, 1200, 1500, 1800, 2100, 2400, 2700, 3000],
                ticktext=["0", "5", "10", "15", "20", "25", "30", "35", "40", "45", "50"]
            )
        )
        st.plotly_chart(fig_duration, width='stretch')
    
    # Дополнительная статистика
    st.subheader("📈 Ключевые метрики")
    col3, col4, col5, col6 = st.columns(4)
    
    with col3:
        st.metric("Средний LP", f"{players_df_filtered['league_points'].mean():.0f}")
    with col4:
        st.metric("Средний винрейт", f"{players_df_filtered['winrate_month'].mean():.1f}%")
    with col5:
        st.metric("Средняя длительность", f"{matches_df_filtered['game_duration_sec'].mean()/60:.1f} мин")
    with col6:
        st.metric("Всего матчей", f"{len(matches_df_filtered):,}")

# ============================================================================
# TAB 2: АНАЛИЗ ЧЕМПИОНОВ
# ============================================================================
with tab2:
    st.subheader("🏆 Анализ меты чемпионов")
    
    # Фильтруем чемпионов по минимальному количеству матчей
    champions_filtered = champions_df[champions_df["matches_played"] >= min_matches].copy()
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Топ-10 по винрейту
        st.markdown("#### 🔥 Топ-10 чемпионов по винрейту")
        top_winrate = champions_filtered.nlargest(10, "winrate")
        
        fig_top = px.bar(
            top_winrate,
            x="winrate",
            y="champion_name",
            orientation="h",
            title=f"Винрейт (мин. {min_matches} матчей)",
            labels={"winrate": "Винрейт (%)", "champion_name": ""},
            text="winrate",
            color="winrate",
            color_continuous_scale="Viridis"
        )
        fig_top.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig_top.update_layout(coloraxis_showscale=False, height=500)
        st.plotly_chart(fig_top, width='stretch')
    
    with col2:
        # Флоп-10 по винрейту (худшие)
        st.markdown("#### 💀 Флоп-10 чемпионов по винрейту")
        bottom_winrate = champions_filtered.nsmallest(10, "winrate")
        
        fig_bottom = px.bar(
            bottom_winrate,
            x="winrate",
            y="champion_name",
            orientation="h",
            title=f"Винрейт (мин. {min_matches} матчей)",
            labels={"winrate": "Винрейт (%)", "champion_name": ""},
            text="winrate",
            color="winrate",
            color_continuous_scale="Reds"
        )
        fig_bottom.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig_bottom.update_layout(coloraxis_showscale=False, height=500)
        st.plotly_chart(fig_bottom, width='stretch')
    
    # Нишевые чемпионы
    st.markdown("---")
    st.subheader("🎯 Нишевые чемпионы (редкие, но эффективные)")
    
    # Чемпионы с малым количеством матчей, но высоким винрейтом
    niche_champions = champions_df[
        (champions_df["matches_played"] >= 100) & 
        (champions_df["matches_played"] <= 500)
    ].nlargest(10, "winrate")
    
    if len(niche_champions) > 0:
        fig_niche = px.bar(
            niche_champions,
            x="winrate",
            y="champion_name",
            orientation="h",
            title="Нишевые чемпионы (100-500 матчей, высокий винрейт)",
            labels={"winrate": "Винрейт (%)", "champion_name": ""},
            text="winrate",
            color="matches_played",
            color_continuous_scale="Blues"
        )
        fig_niche.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig_niche.update_layout(height=400, coloraxis_showscale=False)
        st.plotly_chart(fig_niche, width='stretch')
    else:
        st.info("Нет чемпионов, соответствующих критериям (100-500 матчей)")
# ============================================================================
# TAB 3: СРАВНЕНИЕ РЕГИОНОВ
# ============================================================================
with tab3:
    st.subheader("🌍 Сравнение регионов EUW vs NA")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Винрейт синей команды по регионам
        region_winrate = matches_df.groupby("region")["blue_team_won"].mean().reset_index()
        region_winrate["winrate"] = region_winrate["blue_team_won"] * 100
        region_winrate["region"] = region_winrate["region"].map({"euw1": "EUW", "na1": "NA"})
        
        fig_region_win = px.bar(
            region_winrate,
            x="region",
            y="winrate",
            title="Винрейт синей команды по регионам",
            labels={"winrate": "Винрейт синей (%)", "region": ""},
            color="region",
            color_discrete_sequence=["#1f77b4", "#ff7f0e"]
        )
        st.plotly_chart(fig_region_win, width='stretch')
    
    with col2:
        # Средняя длительность по регионам
        region_duration = matches_df.groupby("region")["game_duration_sec"].mean().reset_index()
        region_duration["duration_min"] = region_duration["game_duration_sec"] / 60
        region_duration["region"] = region_duration["region"].map({"euw1": "EUW", "na1": "NA"})
        
        fig_region_duration = px.bar(
            region_duration,
            x="region",
            y="duration_min",
            title="Средняя длительность матча по регионам",
            labels={"duration_min": "Средняя длительность (мин)", "region": ""},
            color="region",
            color_discrete_sequence=["#1f77b4", "#ff7f0e"]
        )
        st.plotly_chart(fig_region_duration, width='stretch')
    
    # Сравнение топ-чемпионов по регионам
    st.markdown("---")
    st.subheader("🏆 Топ-10 чемпионов по регионам")
    
    # Разделяем данные по регионам
    champions_euw = champions_df.copy()
    champions_euw["region"] = "EUW"
    champions_na = champions_df.copy()
    champions_na["region"] = "NA"
    
    # Создаём общий датафрейм с регионами
    # (здесь нужно было бы иметь данные по чемпионам для каждого региона,
    # но в champions_data нет региона, поэтому используем общую статистику)
    
    st.info("ℹ️ Статистика чемпионов общая для обоих регионов (данные по чемпионам не разделены по регионам)")

# ============================================================================
# TAB 4: АНОМАЛИИ LP И ВИНРЕЙТА
# ============================================================================
with tab4:
    st.subheader("📈 Поиск аномалий в LP и винрейте")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Распределение LP с выделением аномалий
        st.markdown("#### Распределение LP с аномалиями")
        
        # Вычисляем квартили и IQR для LP
        q1 = players_df_filtered["league_points"].quantile(0.25)
        q3 = players_df_filtered["league_points"].quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        # Аномалии по LP
        lp_anomalies = players_df_filtered[
            (players_df_filtered["league_points"] < lower_bound) | 
            (players_df_filtered["league_points"] > upper_bound)
        ]
        
        fig_lp_anomalies = px.histogram(
            players_df_filtered,
            x="league_points",
            nbins=30,
            title=f"LP (аномалий: {len(lp_anomalies)})",
            labels={"league_points": "LP", "count": "Количество игроков"},
            color_discrete_sequence=["#1f77b4"]
        )
        
        # Добавляем вертикальные линии для границ
        fig_lp_anomalies.add_vline(x=lower_bound, line_dash="dash", line_color="red", annotation_text="Нижняя граница")
        fig_lp_anomalies.add_vline(x=upper_bound, line_dash="dash", line_color="red", annotation_text="Верхняя граница")
        
        st.plotly_chart(fig_lp_anomalies, width='stretch')
        
        # Показываем аномалии
        if len(lp_anomalies) > 0:
            st.markdown(f"**Найдено {len(lp_anomalies)} аномалий по LP**")
            st.dataframe(
                lp_anomalies[["summoner_name", "region", "tier", "league_points"]].head(10),
                use_container_width=True
            )
    
    with col2:
        # Распределение винрейта с аномалиями
        st.markdown("#### Распределение винрейта с аномалиями")
        
        # Аномалии по винрейту (>80% или <20%)
        winrate_anomalies = players_df_filtered[
            (players_df_filtered["winrate_month"] > 80) | 
            (players_df_filtered["winrate_month"] < 20)
        ]
        
        fig_winrate_anomalies = px.histogram(
            players_df_filtered,
            x="winrate_month",
            nbins=30,
            title=f"Винрейт (аномалий: {len(winrate_anomalies)})",
            labels={"winrate_month": "Винрейт (%)", "count": "Количество игроков"},
            color_discrete_sequence=["#2ca02c"]
        )
        
        fig_winrate_anomalies.add_vline(x=20, line_dash="dash", line_color="red", annotation_text="20%")
        fig_winrate_anomalies.add_vline(x=80, line_dash="dash", line_color="red", annotation_text="80%")
        st.plotly_chart(fig_winrate_anomalies, width='stretch')
        
        if len(winrate_anomalies) > 0:
            st.markdown(f"**Найдено {len(winrate_anomalies)} аномалий по винрейту**")
            st.dataframe(
                winrate_anomalies[["summoner_name", "region", "tier", "winrate_month", "matches_played_month"]].head(10),
                use_container_width=True
            )
# ============================================================================
# TAB 5: КЛАСТЕРИЗАЦИЯ ИГРОКОВ
# ============================================================================
with tab5:
    st.subheader("🧩 Кластеризация игроков по стилю игры")
    st.markdown("""
    *Игроки группируются по KDA (убийства/смерти/помощи) для выявления стилей игры:*
    - **Кластер 0**: Агрессивные игроки (много убийств и смертей)
    - **Кластер 1**: Поддерживающие игроки (много помощи, мало смертей)
    - **Кластер 2**: Сбалансированные игроки (средние показатели)
    - **Кластер 3**: Осторожные игроки (мало смертей, мало убийств)
    """)
    
    # Берём игроков с матчами
    players_for_clustering = players_df_filtered[players_df_filtered["matches_played_month"] >= 10].copy()
    
    if len(players_for_clustering) < 50:
        st.warning("Недостаточно игроков для кластеризации (нужно минимум 50)")
    else:
        # Подготовка данных для кластеризации
        features = ["avg_kills", "avg_deaths", "avg_assists"]
        X = players_for_clustering[features].fillna(0)
        
        # Масштабирование
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # K-Means кластеризация
        n_clusters = 4
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        players_for_clustering["cluster"] = kmeans.fit_predict(X_scaled)
        
        # Описание кластеров
        cluster_stats = players_for_clustering.groupby("cluster")[features].mean().round(2)
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 3D Scatter plot кластеров
            st.markdown("#### Визуализация кластеров")
            fig_clusters = px.scatter_3d(
                players_for_clustering,
                x="avg_kills",
                y="avg_deaths",
                z="avg_assists",
                color="cluster",
                title="Кластеры игроков по KDA",
                labels={"avg_kills": "Убийства", "avg_deaths": "Смерти", "avg_assists": "Помощи"},
                color_continuous_scale="Viridis",
                opacity=0.7
            )
            st.plotly_chart(fig_clusters, width='stretch')
        
        with col2:
            st.markdown("#### Средние показатели по кластерам")
            
            # Переименовываем кластеры для наглядности
            cluster_names = {
                0: "Агрессивный",
                1: "Поддерживающий",
                2: "Сбалансированный",
                3: "Осторожный"
            }
            
            # Сортируем кластеры для удобства
            cluster_stats_display = cluster_stats.copy()
            cluster_stats_display.index = cluster_stats_display.index.map(lambda x: f"Кластер {x} ({cluster_names.get(x, 'Unknown')})")
            
            st.dataframe(cluster_stats_display, use_container_width=True)

        # Распределение по кластерам
        st.markdown("---")
        st.markdown("#### Распределение игроков по кластерам")
        
        cluster_counts = players_for_clustering["cluster"].value_counts().reset_index()
        cluster_counts.columns = ["Кластер", "Количество"]
        cluster_counts["Кластер"] = cluster_counts["Кластер"].map(lambda x: f"Кластер {x} ({cluster_names.get(x, 'Unknown')})")
        
        fig_cluster_dist = px.pie(
            cluster_counts,
            values="Количество",
            names="Кластер",
            title="Распределение игроков по стилям игры",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        st.plotly_chart(fig_cluster_dist, width='stretch')
        
        # Таблица с примерами игроков из каждого кластера
        st.markdown("---")
        st.markdown("#### Примеры игроков из каждого кластера")
        
        # Показываем по 5 игроков из каждого кластера
        for cluster_id in sorted(players_for_clustering["cluster"].unique()):
            cluster_players = players_for_clustering[players_for_clustering["cluster"] == cluster_id]
            st.markdown(f"**Кластер {cluster_id} ({cluster_names.get(cluster_id, 'Unknown')})**")
            st.dataframe(
                cluster_players.head(5)[["summoner_name", "region", "tier", "avg_kills", "avg_deaths", "avg_assists"]],
                use_container_width=True
            )

# ============================================================================
# FOOTER
# ============================================================================
st.markdown("---")
st.caption("📅 Данные собраны за текущий месяц | Источник: Riot Games API")
