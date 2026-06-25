"""
Так как основной скрипт не скачал имена игроков,
извлечем имена игроков из players_info.pkl
Запуск: python extract_names.py
"""

import pickle
import pandas as pd
import os

DATA_DIR = "data"

print("=" * 50)
print(" ИЗВЛЕЧЕНИЕ ИМЁН ИГРОКОВ")
print("=" * 50)

# Загружаем players_info.pkl
with open(os.path.join(DATA_DIR, "players_info.pkl"), "rb") as f:
    players_info = pickle.load(f)

print(f" Загружено {len(players_info)} записей")

# Создаём DataFrame с именами
names_df = pd.DataFrame([
    {"puuid": puuid, "summoner_name": info.get("summonerName", "Unknown")}
    for puuid, info in players_info.items()
])

# Сохраняем как CSV
names_df.to_csv(os.path.join(DATA_DIR, "summoner_names.csv"), index=False, encoding="utf-8")

print(f" Сохранено: data/summoner_names.csv")
print(f"   {len(names_df[names_df['summoner_name'] != 'Unknown'])} игроков с именами")

print("\n Примеры имён:")
print(names_df.head(10).to_string())