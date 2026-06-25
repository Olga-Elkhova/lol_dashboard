import pickle

# Проверяем все PKL файлы на наличие имён
files = [
    "data/players_info.pkl",
    "data/players_stats.pkl",
]

for file in files:
    try:
        with open(file, "rb") as f:
            data = pickle.load(f)
        print(f"\n{file}:")
        print(f"  Тип: {type(data)}")
        print(f"  Количество записей: {len(data)}")
        
        # Берём первый элемент для проверки
        if isinstance(data, dict):
            first_key = next(iter(data.keys()))
            first_value = data[first_key]
            print(f"  Пример ключа: {first_key}")
            print(f"  Значение: {first_value}")
            
            # Проверяем поля
            if isinstance(first_value, dict):
                print(f"  Поля в значении: {list(first_value.keys())}")
                
                # Ищем summonerName
                if "summonerName" in first_value:
                    print(f"  ✅ summonerName найдено: {first_value['summonerName']}")
                else:
                    print("  ❌ summonerName НЕ найдено в значении")
    except Exception as e:
        print(f"Ошибка при чтении {file}: {e}")