"""
Исправление имён игроков в Parquet файлах
Запуск: python fix_names_parquet.py
"""

import duckdb
import pickle
import os

DATA_DIR = "data"

print("=" * 50)
print("🔄 ИСПРАВЛЕНИЕ ИМЁН ИГРОКОВ")
print("=" * 50)

# 1. Загружаем players_info из PKL (там могут быть правильные имена)
players_info_file = os.path.join(DATA_DIR, "players_info.pkl")

if not os.path.exists(players_info_file):
    print("❌ Файл players_info.pkl не найден!")
    exit(1)

with open(players_info_file, "rb") as f:
    players_info = pickle.load(f)

print(f"✅ Загружено {len(players_info)} записей из players_info.pkl")

# 2. Подключаемся к DuckDB
conn = duckdb.connect()

# 3. Читаем Parquet файл
players_df = conn.execute("SELECT * FROM 'data/players_data.parquet'").df()

print(f"✅ Загружено {len(players_df)} игроков из Parquet")

# 4. Создаём словарь для маппинга puuid -> имя
name_mapping = {}
for puuid, info in players_info.items():
    name = info.get("summonerName", "Unknown")
    if name and name != "Unknown":
        name_mapping[puuid] = name

print(f"✅ Найдено {len(name_mapping)} имен в players_info")

# 5. Обновляем имена
def get_name(puuid):
    return name_mapping.get(puuid, "Unknown")

players_df["summoner_name"] = players_df["puuid"].apply(get_name)

# 6. Считаем сколько имён исправлено
fixed_count = len(players_df[players_df["summoner_name"] != "Unknown"])
print(f"✅ Исправлено имён: {fixed_count} из {len(players_df)}")

# 7. Сохраняем обратно в Parquet
conn.execute("COPY (SELECT * FROM players_df) TO 'data/players_data.parquet' (FORMAT PARQUET)")

print("\n" + "=" * 50)
print("✅ Имена игроков исправлены в Parquet файле!")
print(f"   Теперь {fixed_count} игроков имеют имена")