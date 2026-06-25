"""
ПРОВЕРКА КАЧЕСТВА И ПОЛНОТЫ ДАННЫХ
Запуск: python check_data_quality.py
"""

import pandas as pd
import os
from datetime import datetime

DATA_DIR = "data"

print("=" * 70)
print("ПРОВЕРКА КАЧЕСТВА ДАННЫХ LEAGUE OF LEGENDS")
print("=" * 70)

# ============================================================================
# 1. ПРОВЕРКА СУЩЕСТВОВАНИЯ ФАЙЛОВ
# ============================================================================
print("\n[1] ПРОВЕРКА ФАЙЛОВ")
print("-" * 50)

files = {
    "players_data.csv": "Игроки",
    "matches_data.csv": "Матчи",
    "champions_data.csv": "Чемпионы"
}

data = {}
for filename, description in files.items():
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        df = pd.read_csv(path)
        data[filename] = df
        print(f" {description} ({filename}): {len(df):,} строк")
    else:
        print(f" Файл не найден: {filename}")

if len(data) < 3:
    print("\n Не все файлы найдены! Проверьте папку data.")
    exit(1)

# ============================================================================
# 2. ПРОВЕРКА ИГРОКОВ (players_data.csv)
# ============================================================================
print("\n[2] ПРОВЕРКА ИГРОКОВ (players_data.csv)")
print("-" * 50)

players_df = data["players_data.csv"]

# Регионы
region_counts = players_df["region"].value_counts()
print(f"  Регионы:")
for region, count in region_counts.items():
    region_name = "EUW" if region == "euw1" else "NA"
    pct = count / len(players_df) * 100
    print(f"    {region_name}: {count:,} игроков ({pct:.1f}%)")

# Лиги
tier_counts = players_df["tier"].value_counts()
print(f"\n  Лиги:")
for tier in ["challenger", "grandmaster", "master"]:
    count = tier_counts.get(tier, 0)
    pct = count / len(players_df) * 100
    print(f"    {tier.capitalize()}: {count:,} игроков ({pct:.1f}%)")

# Игроки с матчами
players_with_matches = players_df[players_df["matches_played_month"] > 0]
players_without_matches = players_df[players_df["matches_played_month"] == 0]
print(f"\n  Игроки с матчами: {len(players_with_matches):,}")
print(f"  Игроки без матчей: {len(players_without_matches):,}")

# По регионам и лигам
print(f"\n  Детально по регионам и лигам:")
for region in ["euw1", "na1"]:
    region_name = "EUW" if region == "euw1" else "NA"
    region_df = players_df[players_df["region"] == region]
    print(f"\n    {region_name}:")
    for tier in ["challenger", "grandmaster", "master"]:
        tier_df = region_df[region_df["tier"] == tier]
        with_matches = len(tier_df[tier_df["matches_played_month"] > 0])
        print(f"      {tier.capitalize()}: {len(tier_df)} игроков, {with_matches} с матчами")

# Средние показатели
print(f"\n  Средние показатели игроков (за месяц):")
print(f"    Матчей: {players_df['matches_played_month'].mean():.2f}")
print(f"    Винрейт: {players_df['winrate_month'].mean():.2f}%")
print(f"    Убийств: {players_df['avg_kills'].mean():.2f}")
print(f"    Смертей: {players_df['avg_deaths'].mean():.2f}")
print(f"    Помощей: {players_df['avg_assists'].mean():.2f}")

# Топ-10 по LP
top_lp = players_df.nlargest(10, "league_points")[["summoner_name", "region", "tier", "league_points"]]
print(f"\n  Топ-10 игроков по LP:")
for idx, row in top_lp.iterrows():
    print(f"    {row['summoner_name']:20} | {row['region'].upper():3} | {row['tier']:12} | {row['league_points']:4} LP")

# ============================================================================
# 3. ПРОВЕРКА МАТЧЕЙ (matches_data.csv)
# ============================================================================
print("\n[3] ПРОВЕРКА МАТЧЕЙ (matches_data.csv)")
print("-" * 50)

matches_df = data["matches_data.csv"]

# Регионы матчей
region_counts = matches_df["region"].value_counts()
print(f"  Регионы матчей:")
for region, count in region_counts.items():
    region_name = "EUW" if region == "euw1" else "NA"
    pct = count / len(matches_df) * 100
    print(f"    {region_name}: {count:,} матчей ({pct:.1f}%)")

# Длительность
print(f"\n  Длительность матчей (секунды):")
print(f"    Минимум: {matches_df['game_duration_sec'].min():.0f} сек ({matches_df['game_duration_sec'].min()/60:.1f} мин)")
print(f"    Средняя: {matches_df['game_duration_sec'].mean():.0f} сек ({matches_df['game_duration_sec'].mean()/60:.1f} мин)")
print(f"    Максимум: {matches_df['game_duration_sec'].max():.0f} сек ({matches_df['game_duration_sec'].max()/60:.1f} мин)")
print(f"    Медиана: {matches_df['game_duration_sec'].median():.0f} сек ({matches_df['game_duration_sec'].median()/60:.1f} мин)")

# Победители
blue_wins = matches_df["blue_team_won"].sum()
red_wins = len(matches_df) - blue_wins
print(f"\n  Исходы матчей:")
print(f"    Синяя команда победила: {blue_wins:,} ({blue_wins/len(matches_df)*100:.1f}%)")
print(f"    Красная команда победила: {red_wins:,} ({red_wins/len(matches_df)*100:.1f}%)")

# Версии игры
versions = matches_df["game_version"].value_counts().head(5)
print(f"\n  Топ-5 версий игры:")
for version, count in versions.items():
    print(f"    {version}: {count:,} матчей")

# Даты матчей
matches_df["game_date"] = pd.to_datetime(matches_df["game_creation"], unit='ms')
min_date = matches_df["game_date"].min()
max_date = matches_df["game_date"].max()
print(f"\n  Диапазон дат:")
print(f"    от {min_date.strftime('%Y-%m-%d')}")
print(f"    до {max_date.strftime('%Y-%m-%d')}")

# Проверка на матчи не за текущий месяц
now = datetime.now()
start_of_month = datetime(now.year, now.month, 1)
matches_outside = matches_df[matches_df["game_date"] < start_of_month]
matches_this_month = matches_df[matches_df["game_date"] >= start_of_month]
print(f"\n  Матчи за текущий месяц: {len(matches_this_month):,}")
if len(matches_outside) > 0:
    print(f"   Матчи вне текущего месяца: {len(matches_outside):,} ({len(matches_outside)/len(matches_df)*100:.1f}%)")
    print(f"     (Это может быть из-за разницы часовых поясов или ошибок фильтрации)")

# ============================================================================
# 4. ПРОВЕРКА ЧЕМПИОНОВ (champions_data.csv)
# ============================================================================
print("\n[4] ПРОВЕРКА ЧЕМПИОНОВ (champions_data.csv)")
print("-" * 50)

champions_df = data["champions_data.csv"]

print(f"  Всего чемпионов: {len(champions_df)}")
print(f"  Всего матчей сыграно: {champions_df['matches_played'].sum():,}")

# Топ-10 по популярности
top_popular = champions_df.nlargest(10, "matches_played")[["champion_name", "matches_played", "winrate"]]
print(f"\n  Топ-10 чемпионов по популярности:")
for idx, row in top_popular.iterrows():
    print(f"    {row['champion_name']:15} | {row['matches_played']:5,} матчей | {row['winrate']:5.1f}% винрейт")

# Топ-10 по винрейту (с мин. 1000 матчей)
min_matches = 1000
top_winrate = champions_df[champions_df["matches_played"] >= min_matches].nlargest(10, "winrate")
print(f"\n  Топ-10 чемпионов по винрейту (мин. {min_matches} матчей):")
for idx, row in top_winrate.iterrows():
    print(f"    {row['champion_name']:15} | {row['winrate']:5.1f}% | {row['matches_played']:5,} матчей")

# Чемпионы с аномальным винрейтом
low_winrate = champions_df[champions_df["winrate"] < 30]
high_winrate = champions_df[champions_df["winrate"] > 70]
if len(low_winrate) > 0:
    print(f"\n   Чемпионы с винрейтом < 30%: {len(low_winrate)}")
    for _, row in low_winrate.iterrows():
        print(f"    {row['champion_name']}: {row['winrate']:.1f}% ({row['matches_played']} матчей)")
if len(high_winrate) > 0:
    print(f"\n   Чемпионы с винрейтом > 70%: {len(high_winrate)}")
    for _, row in high_winrate.iterrows():
        print(f"    {row['champion_name']}: {row['winrate']:.1f}% ({row['matches_played']} матчей)")

# ============================================================================
# 5. ИТОГОВОЕ ЗАКЛЮЧЕНИЕ
# ============================================================================
print("\n[5] ИТОГОВОЕ ЗАКЛЮЧЕНИЕ")
print("=" * 70)

# Проверяем, достаточно ли данных для анализа
na_matches_count = len(matches_df[matches_df["region"] == "na1"])
euw_matches_count = len(matches_df[matches_df["region"] == "euw1"])
na_players_with_matches = len(players_df[(players_df["region"] == "na1") & (players_df["matches_played_month"] > 0)])
euw_players_with_matches = len(players_df[(players_df["region"] == "euw1") & (players_df["matches_played_month"] > 0)])

print(f"\n   ИТОГОВАЯ СТАТИСТИКА:")
print(f"    Всего матчей: {len(matches_df):,}")
print(f"      - EUW: {euw_matches_count:,}")
print(f"      - NA: {na_matches_count:,}")
print(f"\n    Всего игроков: {len(players_df):,}")
print(f"      - EUW с матчами: {euw_players_with_matches:,}")
print(f"      - NA с матчами: {na_players_with_matches:,}")

print(f"\n   ДАННЫЕ ГОТОВЫ К АНАЛИЗУ, ЕСЛИ:")
print(f"    1. Матчей > 50 000 (у вас {len(matches_df):,})")
print(f"    2. Есть данные из обоих регионов (у вас {len(matches_df['region'].unique())} регионов)")
print(f"    3. Нет явных аномалий в данных (винрейты в пределах 30-70%)")

if len(matches_df) > 50000 and len(matches_df['region'].unique()) >= 2:
    print(f"\n   ДАННЫЕ ДОСТАТОЧНЫ И КОРРЕКТНЫ!")
    print(f"     Можно переходить к созданию дашборда в DataLens.")
else:
    print(f"\n   ДАННЫХ НЕДОСТАТОЧНО ИЛИ ЕСТЬ ПРОБЛЕМЫ:")
    if len(matches_df) <= 50000:
        print(f"     - Матчей: {len(matches_df):,} (нужно > 50 000)")
    if len(matches_df['region'].unique()) < 2:
        print(f"     - Нет данных из обоих регионов")

print("\n" + "=" * 70)
print("ПРОВЕРКА ЗАВЕРШЕНА")
print("=" * 70)