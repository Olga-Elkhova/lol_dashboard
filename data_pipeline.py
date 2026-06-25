"""
================================================================================
ФИНАЛЬНЫЙ СБОРЩИК ДАННЫХ LEAGUE OF LEGENDS
================================================================================
Назначение:
    Собирает данные игроков из лиг Challenger, Grandmaster, Master 
    для регионов EUW (Европа) и NA (Северная Америка) за текущий месяц.

Особенности:
    - Учитывает rate limits Riot API (20/сек, 100/120сек)
    - Сохраняет прогресс в PKL-файлах (перезагрузка ПК не страшна)
    - Пишет логи в файл data/pipeline.log
    - При повторном запуске докачивает только недостающие данные
    - Игроки без матчей также сохраняются (для полноты)
    - Регион матча определяется по префиксу match_id (EUW1_ / NA1_)

Запуск:
    python data_pipeline.py

Остановка:
    Ctrl+C (прогресс сохранится)

Выходные файлы (папка data/):
    - players_data.csv    - статистика игроков
    - matches_data.csv    - информация о матчах
    - champions_data.csv  - статистика чемпионов
    - *.pkl               - файлы прогресса (не удаляйте)
    - pipeline.log        - лог работы скрипта

Автор:
    LoL Dashboard Project

Версия:
    3.0 (Финальная)
================================================================================
"""

# =============================================================================
# БЛОК 1: ИМПОРТ БИБЛИОТЕК
# =============================================================================
import os
import time
import pickle
import logging
from datetime import datetime
from typing import Dict, List, Any, Set, Tuple, Optional

import requests
import pandas as pd
from dotenv import load_dotenv


# =============================================================================
# БЛОК 2: КОНФИГУРАЦИЯ
# =============================================================================

# Загружаем API ключ из .env файла
load_dotenv()
RIOT_API_KEY = os.getenv("RIOT_API_KEY")

if not RIOT_API_KEY:
    raise ValueError(
        "API ключ не найден!\n"
        "Создайте файл .env в корне проекта с содержимым:\n"
        "RIOT_API_KEY=RGAPI-ваш_ключ"
    )

# Регионы для сбора
REGIONS = ["euw1", "na1"]                    # Игровые регионы
MATCH_REGIONS = {                            # Соответствие для API матчей
    "euw1": "europe",
    "na1": "americas"
}

# Лиги для сбора (от высшей к низшей)
TIERS = ["challenger", "grandmaster", "master"]

# Параметры сбора
MAX_MATCHES_PER_PLAYER = 100    # Максимум матчей на игрока (по ТЗ)
BATCH_SAVE_SIZE = 500           # Сохранять прогресс каждые N матчей

# Настройка папки для данных
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


# =============================================================================
# БЛОК 3: НАСТРОЙКА ЛОГИРОВАНИЯ
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(DATA_DIR, "pipeline.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)


# =============================================================================
# БЛОК 4: ПУТИ К ФАЙЛАМ ПРОГРЕССА
# =============================================================================

# PKL файлы для сохранения состояния (не удалять!)
PLAYERS_INFO_FILE = os.path.join(DATA_DIR, "players_info.pkl")      # {puuid: данные_игрока}
PLAYERS_STATS_FILE = os.path.join(DATA_DIR, "players_stats.pkl")    # {puuid: статистика}
CHAMPIONS_STATS_FILE = os.path.join(DATA_DIR, "champions_stats.pkl") # {champion: статистика}
PROCESSED_MATCHES_FILE = os.path.join(DATA_DIR, "processed_matches.pkl")  # set(match_ids)
MATCHES_LIST_FILE = os.path.join(DATA_DIR, "matches_list.pkl")      # list[матч]


# =============================================================================
# БЛОК 5: RATE LIMITER (ПЛАНИРОВЩИК ЗАПРОСОВ)
# =============================================================================

class RateLimiter:
    """
    Планировщик запросов для соблюдения rate limits Riot API.
    
    Ограничения:
        - 20 запросов в секунду
        - 100 запросов за 120 секунд
    
    Использование:
        limiter = RateLimiter()
        limiter.wait_if_needed()  # Вызывать ПЕРЕД каждым запросом
        response = requests.get(url, headers=headers)
    """
    
    def __init__(self):
        self._requests_per_second = []   # Временные метки запросов (последняя секунда)
        self._requests_per_120s = []     # Временные метки запросов (последние 120 сек)
        self._min_interval = 0.05        # 50 мс минимальная задержка между запросами
    
    def wait_if_needed(self) -> None:
        """Проверяет лимиты и ждёт, если нужно."""
        now = time.time()
        
        # Очищаем устаревшие метки
        self._requests_per_second = [t for t in self._requests_per_second if now - t < 1.0]
        self._requests_per_120s = [t for t in self._requests_per_120s if now - t < 120.0]
        
        # Лимит 20 запросов/секунду
        if len(self._requests_per_second) >= 20:
            oldest = min(self._requests_per_second)
            wait_time = 1.0 - (now - oldest) + 0.05
            if wait_time > 0:
                logging.warning(f"Rate limit (20/сек), ожидание {wait_time:.2f} сек...")
                time.sleep(wait_time)
                now = time.time()
                self._requests_per_second = [t for t in self._requests_per_second if now - t < 1.0]
                self._requests_per_120s = [t for t in self._requests_per_120s if now - t < 120.0]
        
        # Лимит 100 запросов/120 секунд
        if len(self._requests_per_120s) >= 100:
            oldest = min(self._requests_per_120s)
            wait_time = 120.0 - (now - oldest) + 0.05
            if wait_time > 0:
                logging.warning(f"Rate limit (100/120сек), ожидание {wait_time:.2f} сек...")
                time.sleep(wait_time)
                now = time.time()
                self._requests_per_second = [t for t in self._requests_per_second if now - t < 1.0]
                self._requests_per_120s = [t for t in self._requests_per_120s if now - t < 120.0]
        
        # Регистрируем текущий запрос
        self._requests_per_second.append(now)
        self._requests_per_120s.append(now)
        
        # Минимальная задержка между запросами (для стабильности)
        if len(self._requests_per_second) > 1:
            time_since_last = now - self._requests_per_second[-2]
            if time_since_last < self._min_interval:
                time.sleep(self._min_interval - time_since_last)


# =============================================================================
# БЛОК 6: ФУНКЦИИ РАБОТЫ С ПРОГРЕССОМ
# =============================================================================

def save_progress(players_info: Dict, players_stats: Dict,
                  champions_stats: Dict, processed_matches: Set,
                  matches_list: List) -> None:
    """
    Сохраняет текущее состояние сборщика в PKL-файлы.
    Вызывается при автосохранении и в конце работы.
    """
    try:
        with open(PLAYERS_INFO_FILE, "wb") as f:
            pickle.dump(players_info, f)
        with open(PLAYERS_STATS_FILE, "wb") as f:
            pickle.dump(players_stats, f)
        with open(CHAMPIONS_STATS_FILE, "wb") as f:
            pickle.dump(champions_stats, f)
        with open(PROCESSED_MATCHES_FILE, "wb") as f:
            pickle.dump(processed_matches, f)
        with open(MATCHES_LIST_FILE, "wb") as f:
            pickle.dump(matches_list, f)
        logging.debug(f"Прогресс сохранён ({len(matches_list)} матчей)")
    except Exception as e:
        logging.error(f"Ошибка сохранения прогресса: {e}")


def load_progress() -> Tuple[Dict, Dict, Dict, Set, List]:
    """
    Загружает сохранённый прогресс из PKL-файлов.
    Если файлы отсутствуют, возвращает пустые структуры.
    """
    players_info = {}
    players_stats = {}
    champions_stats = {}
    processed_matches = set()
    matches_list = []
    
    logging.info("Загрузка сохранённого прогресса...")
    
    if os.path.exists(PLAYERS_INFO_FILE):
        try:
            with open(PLAYERS_INFO_FILE, "rb") as f:
                players_info = pickle.load(f)
            logging.info(f"  - Игроков: {len(players_info)}")
        except Exception as e:
            logging.warning(f"Не удалось загрузить players_info: {e}")
    
    if os.path.exists(PLAYERS_STATS_FILE):
        try:
            with open(PLAYERS_STATS_FILE, "rb") as f:
                players_stats = pickle.load(f)
            logging.info(f"  - Игроков со статистикой: {len(players_stats)}")
        except Exception as e:
            logging.warning(f"Не удалось загрузить players_stats: {e}")
    
    if os.path.exists(CHAMPIONS_STATS_FILE):
        try:
            with open(CHAMPIONS_STATS_FILE, "rb") as f:
                champions_stats = pickle.load(f)
            logging.info(f"  - Чемпионов: {len(champions_stats)}")
        except Exception as e:
            logging.warning(f"Не удалось загрузить champions_stats: {e}")
    
    if os.path.exists(PROCESSED_MATCHES_FILE):
        try:
            with open(PROCESSED_MATCHES_FILE, "rb") as f:
                processed_matches = pickle.load(f)
            logging.info(f"  - Обработанных матчей: {len(processed_matches)}")
        except Exception as e:
            logging.warning(f"Не удалось загрузить processed_matches: {e}")
    
    if os.path.exists(MATCHES_LIST_FILE):
        try:
            with open(MATCHES_LIST_FILE, "rb") as f:
                matches_list = pickle.load(f)
            logging.info(f"  - Матчей в списке: {len(matches_list)}")
        except Exception as e:
            logging.warning(f"Не удалось загрузить matches_list: {e}")
    
    return players_info, players_stats, champions_stats, processed_matches, matches_list


# =============================================================================
# БЛОК 7: API ЗАПРОСЫ (С ПОВТОРНЫМИ ПОПЫТКАМИ)
# =============================================================================

def api_request(url: str, rate_limiter: RateLimiter, retries: int = 3) -> Dict[str, Any]:
    """
    Выполняет GET-запрос к API с повторными попытками при ошибках.
    
    Args:
        url: Адрес API
        rate_limiter: Объект RateLimiter для соблюдения лимитов
        retries: Количество повторных попыток
    
    Returns:
        JSON-ответ или пустой словарь при ошибке
    """
    headers = {"X-Riot-Token": RIOT_API_KEY}
    
    for attempt in range(retries):
        rate_limiter.wait_if_needed()
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            
            elif response.status_code == 429:
                wait_time = 2 ** attempt
                logging.warning(f"HTTP 429, попытка {attempt+1}/{retries}, ожидание {wait_time} сек...")
                time.sleep(wait_time)
                continue
            
            elif response.status_code in [401, 403]:
                logging.error(f"Ошибка авторизации ({response.status_code}). Проверьте API ключ!")
                return {}
            
            elif response.status_code == 404:
                logging.debug(f"HTTP 404 (не найдено): {url}")
                return {}
            
            else:
                logging.warning(f"HTTP {response.status_code}, попытка {attempt+1}/{retries}")
                if attempt < retries - 1:
                    time.sleep(1)
                continue
        
        except requests.exceptions.Timeout:
            logging.warning(f"Таймаут, попытка {attempt+1}/{retries}")
            if attempt < retries - 1:
                time.sleep(2)
            continue
        
        except requests.exceptions.RequestException as e:
            logging.warning(f"Ошибка соединения: {e}, попытка {attempt+1}/{retries}")
            if attempt < retries - 1:
                time.sleep(2)
            continue
    
    logging.error(f"Не удалось выполнить запрос после {retries} попыток: {url}")
    return {}


# =============================================================================
# БЛОК 8: ПОЛУЧЕНИЕ ИГРОКОВ ИЗ ЛИГ
# =============================================================================

def get_league_players(region: str, tier: str, rate_limiter: RateLimiter) -> List[Dict]:
    """
    Получает список игроков из указанной лиги.
    
    Returns:
        Список словарей с ключами: puuid, summonerName, tier, region, leaguePoints, wins, losses
    """
    url = f"https://{region}.api.riotgames.com/lol/league/v4/{tier}leagues/by-queue/RANKED_SOLO_5x5"
    data = api_request(url, rate_limiter)
    
    if not data or "entries" not in data:
        logging.warning(f"Не удалось получить игроков для {region}/{tier}")
        return []
    
    players = []
    for entry in data["entries"]:
        puuid = entry.get("puuid")
        if puuid:
            players.append({
                "puuid": puuid,
                "summonerName": entry.get("summonerName", "Unknown"),
                "tier": tier,
                "region": region,
                "leaguePoints": entry.get("leaguePoints", 0),
                "wins": entry.get("wins", 0),
                "losses": entry.get("losses", 0),
            })
    
    return players


# =============================================================================
# БЛОК 9: ПОЛУЧЕНИЕ ID МАТЧЕЙ ИГРОКА
# =============================================================================

def get_player_match_ids(puuid: str, region: str, rate_limiter: RateLimiter) -> List[str]:
    """
    Получает до MAX_MATCHES_PER_PLAYER идентификаторов матчей за текущий месяц.
    """
    match_region = MATCH_REGIONS[region]
    
    # Начало текущего месяца в Unix timestamp (секунды)
    now = datetime.now()
    start_of_month = datetime(now.year, now.month, 1)
    start_timestamp = int(start_of_month.timestamp())
    
    url = (f"https://{match_region}.api.riotgames.com"
           f"/lol/match/v5/matches/by-puuid/{puuid}/ids"
           f"?startTime={start_timestamp}"
           f"&queue=420"           # 420 = рейтинговые соло игры
           f"&start=0"
           f"&count={MAX_MATCHES_PER_PLAYER}")
    
    match_ids = api_request(url, rate_limiter)
    return match_ids if isinstance(match_ids, list) else []


# =============================================================================
# БЛОК 10: ОБРАБОТКА ДЕТАЛЕЙ МАТЧА
# =============================================================================

def process_match_details(match_id: str, rate_limiter: RateLimiter,
                          players_stats: Dict, champions_stats: Dict,
                          matches_list: List, processed_matches: Set[str]) -> bool:
    """
    Загружает детальную информацию о матче и обновляет статистику.
    
    Args:
        match_id: Идентификатор матча (EUW1_123456 или NA1_123456)
        rate_limiter: Объект RateLimiter
        players_stats: Словарь статистики игроков (изменяется)
        champions_stats: Словарь статистики чемпионов (изменяется)
        matches_list: Список матчей (изменяется)
        processed_matches: Множество обработанных match_id (изменяется)
    
    Returns:
        True, если матч успешно обработан, False в противном случае
    """
    # Пропускаем уже обработанные матчи
    if match_id in processed_matches:
        return False
    
    # Определяем регион матча по префиксу ID (важное исправление!)
    region_code = match_id.split("_")[0]  # "EUW1" или "NA1"
    match_region = "euw1" if region_code == "EUW1" else "na1"
    
    # Запрашиваем данные матча
    api_region = MATCH_REGIONS[match_region]
    url = f"https://{api_region}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    match_data = api_request(url, rate_limiter)
    
    if not match_data or "info" not in match_data:
        return False
    
    info = match_data["info"]
    game_duration = info.get("gameDuration", 0)
    game_creation = info.get("gameCreation", 0)
    game_version = info.get("gameVersion", "unknown")
    
    # Фильтр по текущему месяцу
    match_date = datetime.fromtimestamp(game_creation / 1000)
    now = datetime.now()
    start_of_month = datetime(now.year, now.month, 1)
    
    if match_date < start_of_month:
        logging.debug(f"Матч {match_id} пропущен (не за текущий месяц)")
        return False
    
    # Определяем победившую команду
    participants = info.get("participants", [])
    blue_win = False
    for p in participants:
        if p.get("teamId") == 100:
            blue_win = p.get("win", False)
            break
    
    # Сохраняем информацию о матче
    matches_list.append({
        "match_id": match_id,
        "region": match_region,
        "game_duration_sec": game_duration,
        "game_creation": game_creation,
        "game_version": game_version,
        "blue_team_won": blue_win
    })
    
    # Обновляем статистику участников
    for p in participants:
        puuid = p.get("puuid")
        champion_name = p.get("championName", "Unknown")
        champion_id = p.get("championId", 0)
        kills = p.get("kills", 0)
        deaths = p.get("deaths", 0)
        assists = p.get("assists", 0)
        win = p.get("win", False)
        
        # Статистика игрока
        if puuid not in players_stats:
            players_stats[puuid] = {
                "matches_played": 0, "wins": 0,
                "total_kills": 0, "total_deaths": 0, "total_assists": 0
            }
        
        players_stats[puuid]["matches_played"] += 1
        players_stats[puuid]["wins"] += 1 if win else 0
        players_stats[puuid]["total_kills"] += kills
        players_stats[puuid]["total_deaths"] += deaths
        players_stats[puuid]["total_assists"] += assists
        
        # Статистика чемпиона
        if champion_name not in champions_stats:
            champions_stats[champion_name] = {
                "champion_id": champion_id, "matches_played": 0, "wins": 0,
                "total_kills": 0, "total_deaths": 0, "total_assists": 0
            }
        
        champions_stats[champion_name]["matches_played"] += 1
        champions_stats[champion_name]["wins"] += 1 if win else 0
        champions_stats[champion_name]["total_kills"] += kills
        champions_stats[champion_name]["total_deaths"] += deaths
        champions_stats[champion_name]["total_assists"] += assists
    
    return True


# =============================================================================
# БЛОК 11: СОХРАНЕНИЕ CSV ФАЙЛОВ
# =============================================================================

def save_csv_files(players_stats: Dict, players_info: Dict,
                   champions_stats: Dict, matches_list: List) -> None:
    """
    Сохраняет три набора данных в CSV файлы.
    """
    # 1. players_data.csv
    players_records = []
    
    # Игроки с матчами
    for puuid, stats in players_stats.items():
        info = players_info.get(puuid, {})
        matches = stats["matches_played"]
        winrate = (stats["wins"] / matches * 100) if matches > 0 else 0
        
        players_records.append({
            "puuid": puuid,
            "summoner_name": info.get("summonerName", "Unknown"),
            "region": info.get("region", "unknown"),
            "tier": info.get("tier", "unknown"),
            "league_points": info.get("leaguePoints", 0),
            "total_wins_season": info.get("wins", 0),
            "total_losses_season": info.get("losses", 0),
            "matches_played_month": matches,
            "wins_month": stats["wins"],
            "winrate_month": round(winrate, 2),
            "avg_kills": round(stats["total_kills"] / matches, 2) if matches > 0 else 0,
            "avg_deaths": round(stats["total_deaths"] / matches, 2) if matches > 0 else 0,
            "avg_assists": round(stats["total_assists"] / matches, 2) if matches > 0 else 0,
        })
    
    # Игроки без матчей (для полноты данных)
    for puuid, info in players_info.items():
        if puuid not in players_stats:
            players_records.append({
                "puuid": puuid,
                "summoner_name": info.get("summonerName", "Unknown"),
                "region": info.get("region", "unknown"),
                "tier": info.get("tier", "unknown"),
                "league_points": info.get("leaguePoints", 0),
                "total_wins_season": info.get("wins", 0),
                "total_losses_season": info.get("losses", 0),
                "matches_played_month": 0,
                "wins_month": 0,
                "winrate_month": 0,
                "avg_kills": 0,
                "avg_deaths": 0,
                "avg_assists": 0,
            })
    
    players_df = pd.DataFrame(players_records)
    players_df.to_csv(os.path.join(DATA_DIR, "players_data.csv"), index=False, encoding="utf-8")
    logging.info(f"  ✓ Сохранено {len(players_records)} игроков")
    
    # 2. champions_data.csv
    champions_records = []
    for champ_name, stats in champions_stats.items():
        matches = stats["matches_played"]
        winrate = (stats["wins"] / matches * 100) if matches > 0 else 0
        champions_records.append({
            "champion_name": champ_name,
            "champion_id": stats["champion_id"],
            "matches_played": matches,
            "wins": stats["wins"],
            "winrate": round(winrate, 2),
            "avg_kills": round(stats["total_kills"] / matches, 2) if matches > 0 else 0,
            "avg_deaths": round(stats["total_deaths"] / matches, 2) if matches > 0 else 0,
            "avg_assists": round(stats["total_assists"] / matches, 2) if matches > 0 else 0,
        })
    
    champions_df = pd.DataFrame(champions_records)
    champions_df = champions_df.sort_values("matches_played", ascending=False)
    champions_df.to_csv(os.path.join(DATA_DIR, "champions_data.csv"), index=False, encoding="utf-8")
    logging.info(f"  ✓ Сохранено {len(champions_records)} чемпионов")
    
    # 3. matches_data.csv
    matches_df = pd.DataFrame(matches_list)
    matches_df.to_csv(os.path.join(DATA_DIR, "matches_data.csv"), index=False, encoding="utf-8")
    logging.info(f"  ✓ Сохранено {len(matches_list)} матчей")


# =============================================================================
# БЛОК 12: ОСНОВНАЯ ФУНКЦИЯ СБОРА ДАННЫХ
# =============================================================================

def collect_all_data() -> None:
    """
    Главная функция, управляющая процессом сбора данных.
    
    Алгоритм:
        1. Загружает сохранённый прогресс
        2. Находит новых игроков в лигах (которых ещё нет в базе)
        3. Добавляет их в players_info
        4. Определяет игроков, у которых меньше MAX_MATCHES_PER_PLAYER матчей
        5. Собирает недостающие матчи для этих игроков
        6. Периодически сохраняет прогресс
    """
    logging.info("=" * 70)
    logging.info("ЗАПУСК СБОРЩИКА ДАННЫХ LEAGUE OF LEGENDS")
    logging.info("=" * 70)
    logging.info(f"Регионы: {REGIONS}")
    logging.info(f"Лиги: {TIERS}")
    logging.info(f"Матчей на игрока: до {MAX_MATCHES_PER_PLAYER}")
    logging.info(f"Папка данных: {DATA_DIR}")
    logging.info("=" * 70)
    
    rate_limiter = RateLimiter()
    
    # ===== ШАГ 1: ЗАГРУЗКА ПРОГРЕССА =====
    logging.info("\n[1/4] Загрузка сохранённого прогресса...")
    players_info, players_stats, champions_stats, processed_matches, matches_list = load_progress()
    
    existing_puuids = set(players_info.keys())
    logging.info(f"  Игроков в базе: {len(existing_puuids)}")
    logging.info(f"  Матчей обработано: {len(processed_matches)}")
    
    # ===== ШАГ 2: ПОИСК НОВЫХ ИГРОКОВ =====
    logging.info("\n[2/4] Поиск новых игроков в лигах...")
    new_players = []
    
    for region in REGIONS:
        for tier in TIERS:
            print(f"  {region.upper()} - {tier.capitalize()}...", end=" ", flush=True)
            players = get_league_players(region, tier, rate_limiter)
            print(f"{len(players)} игроков")
            logging.info(f"  {region.upper()} - {tier.capitalize()}: {len(players)} игроков")
            
            for player in players:
                if player["puuid"] not in existing_puuids:
                    new_players.append(player)
                    existing_puuids.add(player["puuid"])
    
    for player in new_players:
        players_info[player["puuid"]] = player
    
    logging.info(f"\n  Добавлено новых игроков: {len(new_players)}")
    logging.info(f"  Всего игроков теперь: {len(players_info)}")
    
    # ===== ШАГ 3: ОПРЕДЕЛЕНИЕ ИГРОКОВ ДЛЯ СБОРА МАТЧЕЙ =====
    logging.info("\n[3/4] Определение игроков, требующих сбора матчей...")


    # Данные по EUW были скачаны предыдущей версией скрипта. 
    # Для экономии времени скачивания недостающих данных по NA, добавим фильтр по региону
    '''
    Эта часть кода скачивает данные и для EUW и для NA. Это долго, поэтому заменяю на код с фильтром по региону
    players_to_fetch = []
    for puuid, info in players_info.items():
        stats = players_stats.get(puuid, {})
        current_matches = stats.get("matches_played", 0)
        
        # Собираем матчи для тех, у кого меньше максимального количества
        if current_matches < MAX_MATCHES_PER_PLAYER:
            players_to_fetch.append((puuid, info, current_matches))
     '''
    players_to_fetch = []
    for puuid, info in players_info.items():
        # ДОБАВЛЯЕМ ФИЛЬТР: только NA игроки
        if info.get("region") != "na1":
            continue
    
        stats = players_stats.get(puuid, {})
        current_matches = stats.get("matches_played", 0)
        if current_matches < MAX_MATCHES_PER_PLAYER:
            players_to_fetch.append((puuid, info, current_matches))

    
    # Сортируем: сначала те, у кого уже есть матчи (почти готовые)
    players_to_fetch.sort(key=lambda x: x[2], reverse=True)
    
    # Статистика по регионам
    euw_count = sum(1 for _, info, _ in players_to_fetch if info['region'] == 'euw1')
    na_count = sum(1 for _, info, _ in players_to_fetch if info['region'] == 'na1')
    
    logging.info(f"  Игроков для сбора матчей: {len(players_to_fetch)}")
    logging.info(f"    - EUW: {euw_count}")
    logging.info(f"    - NA: {na_count}")
    
    if len(players_to_fetch) == 0:
        logging.info("\n✅ Все игроки уже имеют максимальное количество матчей!")
        save_csv_files(players_stats, players_info, champions_stats, matches_list)
        save_progress(players_info, players_stats, champions_stats, processed_matches, matches_list)
        return
    
    # ===== ШАГ 4: СБОР МАТЧЕЙ =====
    logging.info("\n[4/4] Сбор матчей...")
    
    total_new_matches = 0
    total_skipped = 0
    total_errors = 0
    
    for idx, (puuid, info, current) in enumerate(players_to_fetch):
        try:
            # Получаем ID матчей игрока
            match_ids = get_player_match_ids(puuid, info["region"], rate_limiter)
            
            # Обрабатываем каждый матч
            for match_id in match_ids:
                if process_match_details(match_id, rate_limiter, players_stats,
                                         champions_stats, matches_list, processed_matches):
                    total_new_matches += 1
                    processed_matches.add(match_id)
                else:
                    if match_id in processed_matches:
                        total_skipped += 1
            
            # Логируем прогресс каждые 10 игроков
            if (idx + 1) % 10 == 0 or (idx + 1) == len(players_to_fetch):
                logging.info(f"  Прогресс: {idx+1}/{len(players_to_fetch)} игроков | "
                           f"Новых матчей: {total_new_matches} | "
                           f"Пропущено дубликатов: {total_skipped}")
                
                # Автосохранение
                if len(matches_list) >= BATCH_SAVE_SIZE:
                    save_csv_files(players_stats, players_info, champions_stats, matches_list)
                    save_progress(players_info, players_stats, champions_stats,
                                 processed_matches, matches_list)
                    logging.info(f"  [Автосохранение: {len(matches_list)} матчей]")
        
        except Exception as e:
            total_errors += 1
            logging.error(f"Ошибка при обработке {info.get('summonerName', puuid[:16])}: {e}")
            continue
    
    # ===== ФИНАЛЬНОЕ СОХРАНЕНИЕ =====
    logging.info("\n[Финальное сохранение...]")
    save_csv_files(players_stats, players_info, champions_stats, matches_list)
    save_progress(players_info, players_stats, champions_stats, processed_matches, matches_list)
    
    # ===== ИТОГОВАЯ СТАТИСТИКА =====
    na_players = [p for p in players_info.values() if p.get("region") == "na1"]
    euw_players = [p for p in players_info.values() if p.get("region") == "euw1"]
    na_matches = [m for m in matches_list if m["region"] == "na1"]
    euw_matches = [m for m in matches_list if m["region"] == "euw1"]
    
    logging.info("\n" + "=" * 70)
    logging.info("СТАТИСТИКА ЗАВЕРШЕНИЯ")
    logging.info("=" * 70)
    logging.info(f"\n  ИГРОКИ:")
    logging.info(f"    Всего: {len(players_info)}")
    logging.info(f"    EUW: {len(euw_players)}")
    logging.info(f"    NA: {len(na_players)}")
    logging.info(f"\n  МАТЧИ:")
    logging.info(f"    Всего: {len(matches_list)}")
    logging.info(f"    EUW: {len(euw_matches)}")
    logging.info(f"    NA: {len(na_matches)}")
    logging.info(f"\n  ЧЕМПИОНЫ: {len(champions_stats)}")
    logging.info(f"\n  ОШИБКИ: {total_errors}")
    logging.info("=" * 70)
    logging.info("\n Сбор данных завершён!")
    logging.info(f"   CSV файлы сохранены в папку '{DATA_DIR}/'")
    logging.info("   Теперь можно загружать их в DataLens или запускать dashboard.py")


# =============================================================================
# БЛОК 13: ТОЧКА ВХОДА
# =============================================================================

if __name__ == "__main__":
    try:
        collect_all_data()
    except KeyboardInterrupt:
        logging.info("\n\n Прерывание пользователем (Ctrl+C)")
        logging.info("Прогресс сохранён. При следующем запуске скрипт продолжит с того же места.")
    except Exception as e:
        logging.error(f" Непредвиденная ошибка: {e}")
        raise