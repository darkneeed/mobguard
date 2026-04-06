#!/bin/bash
set -euo pipefail

# === КОНФИГУРАЦИЯ ===
CONFIG_FILE="/opt/ban_system/config.json"
DB_FILE="/opt/ban_system/bans.db"
SERVICE_NAME="mobguard"
VERSION="0.5"

# === ЦВЕТА ===
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

function check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}Нужен root для этой опции${NC}"
        read -n 1 -s -r -p "Нажмите клавишу..."
        return 1
    fi
    return 0
}

function get_service_status() {
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo -e "${GREEN}● ACTIVE${NC}"
    else
        echo -e "${RED}● STOPPED${NC}"
    fi
}

function get_mode_status() {
    CURRENT_DRY=$(jq -r '.settings.dry_run // true' "$CONFIG_FILE" 2>/dev/null || echo "true")
    if [ "$CURRENT_DRY" = "true" ]; then
        echo -e "${YELLOW}DRY RUN${NC}"
    else
        echo -e "${RED}BANHAMMER${NC}"
    fi
}

# === ЛОГИ ===
function view_logs() {
    clear
    echo -e "${YELLOW}=== ПРОСМОТР ЛОГОВ ===${NC}"
    echo "1. 📜 Полный поток (Live)"
    echo "2. 🧠 ML & Learning (Обучение системы)"
    echo "3. 🎭 Behavior & Subnets (Поведение)"
    echo "4. ⚠️ Важные события (Bans/Warnings)"
    echo "5. 🔍 Анализ решений (Цепочка проверки)"
    echo "6. ❌ Ошибки"
    echo "0. 🔙 Назад"
    echo "------------------------------------------------"
    read -p "Выбор: " log_choice
    echo -e "${GREEN}>> Ctrl+C для выхода <<${NC}"
    echo ""
   
    case $log_choice in
        1) journalctl -u $SERVICE_NAME -f -n 50 --output cat ;;
        2) journalctl -u $SERVICE_NAME -f -n 50 --output cat | grep --line-buffered -E "\[LEARNING\]|\[ML\]" ;;
        3) journalctl -u $SERVICE_NAME -f -n 50 --output cat | grep --line-buffered -E "\[BEHAVIOR\]|\[SUBNET\]|churn|lifetime" ;;
        4) journalctl -u $SERVICE_NAME -f -n 50 --output cat | grep --line-buffered -E "VIOLATION|ENFORCEMENT|БЛОКИРОВКА|ПРЕДУПРЕЖДЕНИЕ" ;;
        5) journalctl -u $SERVICE_NAME -f -n 50 --output cat | grep --line-buffered -E "\[ANALYSIS\]|\[IMPORTANT\]|Confidence|Score" ;;
        6) journalctl -u $SERVICE_NAME -f -n 50 -p err ;;
        0) return ;;
        *) echo "Неверный выбор"; sleep 1 ;;
    esac
}

# === УПРАВЛЕНИЕ СЕРВИСОМ ===
function service_control() {
    while true; do
        clear
        echo -e "${YELLOW}=== УПРАВЛЕНИЕ СЕРВИСОМ ===${NC}"
        echo "Статус: $(get_service_status)"
        echo ""
        echo "1. ▶️  Запустить (Start)"
        echo "2. ⏹️  Остановить (Stop)"
        echo "3. 🔄 Перезагрузить (Restart)"
        echo "4. 📋 Статус (Systemd)"
        echo "0. 🔙 Назад"
        echo "------------------------------------------------"
        read -p "Выбор: " srv_choice

        if check_root; then
            case $srv_choice in
                1) systemctl start $SERVICE_NAME; echo "Запуск..."; sleep 1 ;;
                2) systemctl stop $SERVICE_NAME; echo "Остановка..."; sleep 1 ;;
                3) systemctl restart $SERVICE_NAME; echo "Рестарт..."; sleep 1 ;;
                4) systemctl status $SERVICE_NAME --no-pager; read -n 1 -s -r -p "Нажмите клавишу..." ;;
                0) return ;;
            esac
        else
            return
        fi
    done
}

# === DEBUG ===
function manage_debug() {
    clear
    echo -e "${YELLOW}=== НАСТРОЙКА DEBUG ===${NC}"
    CURRENT_LEVEL=$(jq -r '.settings.debug_level // "OFF"' "$CONFIG_FILE" 2>/dev/null || echo "OFF")
    echo "Текущий уровень: $CURRENT_LEVEL"
    echo ""
    echo "1. OFF       (Только ошибки и баны)"
    echo "2. IMPORTANT (Важные события, Manual, Dedup)"
    echo "3. ANALYSIS  (Полный анализ каждого IP)"
    echo "4. FULL      (Всё подряд - максимальный шум)"
    echo ""
    echo -e "${MAGENTA}5. 🐞 LIVE DEBUG (Остановить сервис и запустить в консоли)${NC}"
    echo "0. Назад"
    
    read -p "Выбор: " dbg_choice
    case $dbg_choice in
        1) NEW_LEVEL="OFF";;
        2) NEW_LEVEL="IMPORTANT";;
        3) NEW_LEVEL="ANALYSIS";;
        4) NEW_LEVEL="FULL";;
        5) 
            if check_root; then
                echo -e "${RED}Останавливаю сервис...${NC}"
                systemctl stop $SERVICE_NAME
                echo -e "${GREEN}Запускаю MobGuard в режиме консоли... (Ctrl+C для выхода)${NC}"
                python3 /opt/ban_system/mobguard.py
                echo ""
                read -p "Запустить сервис обратно? (y/n): " restart_svc
                if [[ "$restart_svc" == "y" ]]; then systemctl start $SERVICE_NAME; fi
            fi
            return
            ;;
        0) return;;
        *) return;;
    esac

    jq ".settings.debug_level = \"$NEW_LEVEL\"" "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
    echo -e "✅ Установлен: ${GREEN}$NEW_LEVEL${NC}"
    
    read -p "Перезапустить сервис для применения? (y/n): " rst
    if [[ "$rst" == "y" ]]; then systemctl restart $SERVICE_NAME; fi
}

# === ML & DATABASE ===
function manage_ml() {
    while true; do
        clear
        echo -e "${YELLOW}=== ML & ПОДСЕТИ ===${NC}"
        
        # Stats
        ML_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM unsure_learning" 2>/dev/null || echo "0")
        SUBNET_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM subnet_evidence" 2>/dev/null || echo "0")
        
        echo -e "Записей обучения: ${CYAN}$ML_COUNT${NC}"
        echo -e "Известных подсетей: ${CYAN}$SUBNET_COUNT${NC}"
        echo ""
        echo "1. 🧠 Топ ML паттернов (ASN/Keywords)"
        echo "2. 🌐 Топ подсетей (Mobile/Home evidence)"
        echo "3. 🗑️ Сбросить всё обучение"
        echo "4. 🗑️ Сбросить статистику подсетей"
        echo "0. Назад"
        
        read -p "Выбор: " ml_choice
        case $ml_choice in
            1)
                echo ""
                echo -e "${BLUE}[ Топ ML решений ]${NC}"
                sqlite3 -header -column "$DB_FILE" "SELECT pattern_type, pattern_value, decision, confidence FROM unsure_learning ORDER BY confidence DESC LIMIT 15;"
                read -n 1 -s -r -p "..."
                ;;
            2)
                echo ""
                echo -e "${BLUE}[ Топ подсетей ]${NC}"
                sqlite3 -header -column "$DB_FILE" "SELECT subnet, mobile_count, home_count FROM subnet_evidence ORDER BY (mobile_count + home_count) DESC LIMIT 15;"
                read -n 1 -s -r -p "..."
                ;;
            3)
                if check_root; then
                    sqlite3 "$DB_FILE" "DELETE FROM unsure_learning;"
                    echo "✅ Обучение сброшено."
                    read -n 1 -s -r -p "..."
                fi
                ;;
            4)
                if check_root; then
                    sqlite3 "$DB_FILE" "DELETE FROM subnet_evidence;"
                    echo "✅ Подсети сброшены."
                    read -n 1 -s -r -p "..."
                fi
                ;;
            0) return ;;
        esac
    done
}

function view_db_full() {
    clear
    echo -e "${YELLOW}=== СВОДКА БД ===${NC}"
    
    echo -e "${BLUE}[ Статус ]${NC}"
    sqlite3 "$DB_FILE" "
        SELECT 'Violations: ', COUNT(*) FROM violations;
        SELECT 'Trackers:   ', COUNT(*) FROM active_trackers;
        SELECT 'History:    ', COUNT(*) FROM violation_history;
        SELECT 'IP Cache:   ', COUNT(*) FROM ip_decisions;
    "
    
    echo ""
    echo -e "${BLUE}[ Активные баны ]${NC}"
    sqlite3 -header -column "$DB_FILE" "SELECT substr(uuid,1,8) as uuid, strikes, substr(unban_time,1,16) as unban_time FROM violations WHERE unban_time > datetime('now') LIMIT 10;"
    
    echo ""
    echo -e "${BLUE}[ Топ активных трекеров ]${NC}"
    # Сложный запрос через python, так как sqlite3 bash limited
    python3 -c "
import sqlite3, datetime
try:
    conn = sqlite3.connect('$DB_FILE')
    cursor = conn.cursor()
    cursor.execute('SELECT key, start_time FROM active_trackers')
    print(f'{'KEY':<40} {'DURATION':<10}')
    print('-'*50)
    now = datetime.datetime.now()
    rows = []
    for row in cursor.fetchall():
        try:
            start = datetime.datetime.fromisoformat(row[1])
            dur = int((now - start).total_seconds())
            rows.append((row[0], dur))
        except: pass
    rows.sort(key=lambda x: x[1], reverse=True)
    for r in rows[:10]:
        print(f'{r[0]:<40} {r[1]}s')
except: pass
"
    
    echo ""
    read -n 1 -s -r -p "Нажмите клавишу..."
}

# === MANUAL CHECK ===
function manual_ip_check() {
    clear
    echo -e "${YELLOW}=== MANUAL IP АНАЛИЗ ===${NC}"
    read -p "Введите IP: " ip
    if [[ -z "$ip" ]]; then return; fi
    
    echo ""
    echo -e "${CYAN}Загрузка движка и анализ $ip...${NC}"
    
    # Используем Python для корректного импорта классов
    python3 - <<EOF
import sys
import asyncio
import os
import json
sys.path.insert(0, '/opt/ban_system')

try:
    # MOCK Config loading to avoid full init
    with open('$CONFIG_FILE', 'r') as f:
        config = json.load(f)

    from mobguard import DatabaseManager, NetworkAnalyzer, BehavioralEngine
    
    # Init DB manager
    db = DatabaseManager('$DB_FILE')
    
    # Init Engine
    behavioral_engine = BehavioralEngine(db, config)
    
    # Patch NetworkAnalyzer to use our engine instance (dirty hack for script)
    # But better: just instantiate NA and inject engine if possible, 
    # OR replicate the check logic briefly.
    
    # Replicating check logic simply for display
    from ipinfo_api import ipinfo_api
    
    async def run_check():
        print(f"📡 Querying IPInfo for {ip}...")
        info = await ipinfo_api.get_ip_info('$ip')
        org = info.get('org', 'N/A')
        print(f"   ORG: {org}")
        print(f"   ASN: {ipinfo_api.parse_asn(org)}")
        
        print(f"🧠 Checking ML confidence...")
        asn = ipinfo_api.parse_asn(org)
        if asn:
            mob_conf = await db.get_learning_confidence('asn', str(asn), 'MOBILE')
            home_conf = await db.get_learning_confidence('asn', str(asn), 'HOME')
            print(f"   ASN ML: MOBILE={mob_conf} | HOME={home_conf}")
        
        print(f"🌐 Checking Subnet Evidence...")
        ev = await db.get_subnet_evidence('$ip')
        print(f"   Subnet: MOBILE={ev['MOBILE']} | HOME={ev['HOME']}")
        
        print(f"💾 Checking Cache...")
        cached = await db.get_cached_decision('$ip')
        if cached:
            print(f"   [CACHED] Status: {cached['status']} ({cached['confidence']})")
        else:
            print("   [NOT CACHED]")

    asyncio.run(run_check())

except Exception as e:
    print(f"Error: {e}")
EOF
    echo ""
    read -n 1 -s -r -p "Нажмите клавишу..."
}

# === ГЛАВНОЕ МЕНЮ ===
while true; do
    clear
    echo "================================================="
    echo -e "   MobGuard Panel v${VERSION} | $(get_service_status) | $(get_mode_status)"
    echo "================================================="
    
    # Quick Stats
    BANS=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM violations WHERE unban_time > datetime('now')" 2>/dev/null || echo "?")
    UNSURE=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM unsure_patterns" 2>/dev/null || echo "?")
    
    echo -e "   Баны: ${RED}$BANS${NC} | Unsure: ${YELLOW}$UNSURE${NC}"
    echo "================================================="
    echo ""
    echo -e "${GREEN}📊 МОНИТОРИНГ${NC}"
    echo "  1. 📜 Просмотр логов"
    echo "  2. 💾 База данных (Сводка)"
    echo "  3. 🧠 ML и Подсети (Управление обучением)"
    echo ""
    echo -e "${YELLOW}⚙️  УПРАВЛЕНИЕ${NC}"
    echo "  4. 🚀 Сервис (Start/Stop/Restart)"
    echo "  5. 🐛 Настройка Debug"
    echo "  6. 🔒 Переключить Dry Run / Production"
    echo "  7. 📝 Редактировать конфиг"
    echo ""
    echo -e "${BLUE}🔧 УТИЛИТЫ${NC}"
    echo "  8. 🔎 Manual IP Check"
    echo "  9. 🧹 Очистка/Обслуживание БД"
    echo ""
    echo "  0. ❌ Выход"
    echo "================================================="
    read -p "Выбор: " choice
    
    case $choice in
        1) view_logs ;;
        2) view_db_full ;;
        3) manage_ml ;;
        4) service_control ;;
        5) manage_debug ;;
        6) 
            # Toggle Dry Run logic
            CUR=$(jq -r '.settings.dry_run' "$CONFIG_FILE")
            if [ "$CUR" == "true" ]; then NEW="false"; else NEW="true"; fi
            jq ".settings.dry_run = $NEW" "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
            echo "Dry Run changed to $NEW"
            read -p "Рестарт? (y/n): " r; [[ "$r" == "y" ]] && systemctl restart $SERVICE_NAME
            ;;
        7) if check_root; then nano "$CONFIG_FILE"; fi ;;
        8) manual_ip_check ;;
        9) 
            # Simple cleanup
            read -p "Очистить старый кеш и трекеры? (y/n): " c
            if [[ "$c" == "y" ]]; then
                sqlite3 "$DB_FILE" "DELETE FROM active_trackers WHERE last_seen < datetime('now', '-24 hours');"
                sqlite3 "$DB_FILE" "DELETE FROM ip_decisions WHERE expires < datetime('now');"
                echo "Готово."
                sleep 1
            fi
            ;;
        0) exit 0 ;;
        *) echo "Неверный выбор"; sleep 1 ;;
    esac
done