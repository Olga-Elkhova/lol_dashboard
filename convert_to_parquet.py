"""
Конвертация CSV → Parquet с помощью DuckDB
Запуск: python convert_to_parquet.py

"""

import duckdb
import os
import time

DATA_DIR = "data"

print("=" * 50)
print(" КОНВЕРТАЦИЯ CSV → PARQUET")
print("=" * 50)

# Создаём подключение к DuckDB (in-memory)
conn = duckdb.connect()

files = ["players_data.csv", "matches_data.csv", "champions_data.csv"]

for filename in files:
    csv_path = os.path.join(DATA_DIR, filename)
    parquet_path = os.path.join(DATA_DIR, filename.replace(".csv", ".parquet"))
    
    if not os.path.exists(csv_path):
        print(f" Файл не найден: {csv_path}")
        continue
    
    print(f"\n📄 Чтение: {filename}")
    start_time = time.time()
    
    # Читаем CSV через DuckDB (быстрее, чем pandas для больших файлов)
    table_name = filename.replace(".csv", "")
    conn.execute(f"""
        CREATE OR REPLACE TABLE {table_name} AS 
        SELECT * FROM read_csv_auto('{csv_path}')
    """)
    
    # Сохраняем в Parquet
    conn.execute(f"""
        COPY {table_name} TO '{parquet_path}' (FORMAT PARQUET)
    """)
    
    elapsed = time.time() - start_time
    
    # Сравниваем размеры
    csv_size = os.path.getsize(csv_path) / (1024 * 1024)
    parquet_size = os.path.getsize(parquet_path) / (1024 * 1024)
    
    print(f"   CSV: {csv_size:.2f} MB")
    print(f"   Parquet: {parquet_size:.2f} MB (сжатие в {csv_size/parquet_size:.1f}x)")
    print(f"  ⏱  Время: {elapsed:.2f} сек")

print("\n" + "=" * 50)
print(" Конвертация завершена!")
print(f" Parquet файлы сохранены в папку {DATA_DIR}/")