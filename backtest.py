import json
import sqlite3
import datetime
from collections import defaultdict, deque
import numpy as np

def get_current_zodiac_map(ref_year):
    zodiac_order = ['鼠', '牛', '虎', '兔', '龍', '蛇', '馬', '羊', '猴', '雞', '狗', '豬']
    base_year = 2020
    current_zodiac_idx = (ref_year - base_year) % 12
    zodiac_map = {z: [] for z in zodiac_order}
    for num in range(1, 50):
        offset = (num - 1) % 12
        z_idx = (current_zodiac_idx - offset) % 12
        zodiac_map[zodiac_order[z_idx]].append(num)
    return zodiac_map

def get_current_wuxing_map(ref_year):
    nayin_cycle = ['金', '火', '木', '土', '金', '火', '水', '土', '金', '木',
                   '水', '土', '火', '木', '水', '金', '火', '木', '土', '金',
                   '火', '水', '土', '金', '木', '水', '土', '火', '木', '水']
    wuxing_map = {'金': [], '木': [], '水': [], '火': [], '土': []}
    for num in range(1, 50):
        target_year = ref_year - num + 1
        pair_index = (((target_year - 1984) % 60) + 60) % 60 // 2
        wuxing_map[nayin_cycle[pair_index]].append(num)
    return wuxing_map

def get_color_map():
    return {
        '红': [1, 2, 7, 8, 12, 13, 18, 19, 23, 24, 29, 30, 34, 35, 40, 45, 46],
        '蓝': [3, 4, 9, 10, 14, 15, 20, 25, 26, 31, 36, 37, 41, 42, 47, 48],
        '绿': [5, 6, 11, 16, 17, 21, 22, 27, 28, 32, 33, 38, 39, 43, 44, 49]
    }

def get_records_from_db(db_path='lottery.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT period, raw_time, numbers, zodiacs, special, special_zodiac FROM history ORDER BY period ASC")
    rows = cursor.fetchall()
    conn.close()
    
    records = []
    for row in rows:
        records.append({
            "period": row[0],
            "date": row[1],
            "numbers": json.loads(row[2]),
            "zodiacs": json.loads(row[3]),
            "special": row[4],
            "special_zodiac": row[5]
        })
    return records

def run_metaphysics_heatmap_backtest(test_window=50, db_file='lottery.db'):
    records = get_records_from_db(db_file)
    total_records = len(records)
    
    if total_records < test_window + 50:
        print("错误：数据量不足以支撑回测窗口。")
        return

    print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] 开启【玄学迷信 + 杀猪盘资金热力】双轨引擎...")
    print(f"核心逻辑：叠加谐音避讳、生肖相冲、五行相生等中式玄学因素，锁定庄家终极盲区。")
    print("-" * 75)

    RELATIONS_CHONG = {'鼠':'馬', '馬':'鼠', '牛':'羊', '羊':'牛', '虎':'猴', '猴':'虎', '兔':'雞', '雞':'兔', '龍':'狗', '狗':'龍', '蛇':'豬', '豬':'蛇'}
    WUXING_SHENG = {'金':'水', '水':'木', '木':'火', '火':'土', '土':'金'}

    top1_hit_count = 0
    top6_hit_count = 0
    normal_hit_rates = []

    for i in range(total_records - test_window, total_records):
        history_slice = records[:i]
        target_record = records[i]
        target_period = target_record['period']
        actual_special = target_record['special']
        actual_normals = set(target_record['numbers'])
        
        latest = history_slice[-1]
        ref_year = int(latest['date'][:4])
        
        ZODIAC_MAP = get_current_zodiac_map(ref_year)
        NUM_TO_ZODIAC = {n: z for z, nums in ZODIAC_MAP.items() for n in nums}
        WUXING_MAP = get_current_wuxing_map(ref_year)
        NUM_TO_WUXING = {n: w for w, nums in WUXING_MAP.items() for n in nums}
        COLOR_MAP = get_color_map()
        NUM_TO_COLOR = {n: c for c, nums in COLOR_MAP.items() for n in nums}
        
        current_year_zodiac = NUM_TO_ZODIAC.get(1, '鼠')

        miss_tracker = {n: 0 for n in range(1, 50)}
        freq_10 = {n: 0 for n in range(1, 50)}
        recent_30_queue = deque(maxlen=30)
        
        for j in range(len(history_slice) - 1):
            curr_nums = set(history_slice[j]['numbers'] + [history_slice[j]['special']])
            recent_30_queue.append(curr_nums)
            for n in range(1, 50):
                if n in curr_nums: miss_tracker[n] = 0
                else: miss_tracker[n] += 1

        for past_nums in list(recent_30_queue)[-10:]:
            for n in past_nums: freq_10[n] += 1

        latest_nums = set(latest['numbers'] + [latest['special']])
        for n in range(1, 50):
            if n in latest_nums: miss_tracker[n] = 0
            else: miss_tracker[n] += 1

        reversed_hist = history_slice[::-1]
        recent_5_big = sum(1 for r in reversed_hist[:5] for n in r['numbers']+[r['special']] if n >= 25)
        recent_5_odd = sum(1 for r in reversed_hist[:5] for n in r['numbers']+[r['special']] if n % 2 != 0)
        big_heavy_bet = recent_5_big > 20
        small_heavy_bet = recent_5_big < 15
        odd_heavy_bet = recent_5_odd > 20
        even_heavy_bet = recent_5_odd < 15

        color_streak = []
        for r in reversed_hist:
            c = NUM_TO_COLOR.get(r['special'], '绿')
            if not color_streak or color_streak[-1] == c:
                color_streak.append(c)
            else:
                break
        streak_len = len(color_streak)
        streak_color = color_streak[0] if color_streak else None

        last_special = latest['special']
        last_special_zodiac = latest['special_zodiac']
        last_special_wuxing = NUM_TO_WUXING.get(last_special, '金')

        # ==========================================
        # 🧨 核心模块：玄学+心理 资金热力图
        # ==========================================
        capital_heat = {}
        for n in range(1, 50):
            heat = 100.0  
            
            # --- 【中式玄学与迷信维度】 ---
            
            # 1. 死穴凶数回避 (散户极度嫌弃) -> 资金抽离
            if n % 10 == 4:
                heat -= 40.0  # 4, 14, 24, 34, 44 散户基本不碰，庄家极度安全
                
            # 2. 极数崇拜与天机号 -> 资金沉淀
            if n in [1, 49]:
                heat += 60.0
                
            # 3. 生肖正冲恐惧 -> 散户不敢买，资金抽离
            curr_zodiac = NUM_TO_ZODIAC.get(n, '')
            if curr_zodiac == RELATIONS_CHONG.get(last_special_zodiac, ''):
                heat -= 35.0  # 散户觉得这期绝不可能开，庄家反向杀出
                
            # 4. 五行相生追捧 -> 散户重注，资金暴涨
            curr_wuxing = NUM_TO_WUXING.get(n, '')
            if curr_wuxing == WUXING_SHENG.get(last_special_wuxing, ''):
                heat += 45.0  # 木生火，散户狂追火

            # --- 【传统行为心理维度】 ---
            if n <= 31: heat += 30.0 # 生日
            if n % 10 in [6, 8, 9] or n in [11, 22, 33]: heat += 40.0 # 吉利号
            if curr_zodiac == current_year_zodiac: heat += 50.0 # 本命年
            if n == last_special - 1 or n == last_special + 1: heat += 45.0 # 邻号
            
            # 极限倍投雪球 (遗漏)
            if miss_tracker[n] >= 8: heat += 20.0 + (miss_tracker[n] - 8) * 15.0
            if miss_tracker[n] >= 18: heat += 200.0 

            # 追涨杀跌
            if miss_tracker[n] == 0: heat += 50.0 
            if freq_10[n] >= 3: heat += 80.0      
                
            # 宏观偏态
            is_big = n >= 25
            is_odd = n % 2 != 0
            if big_heavy_bet and not is_big: heat += 80.0
            if small_heavy_bet and is_big: heat += 80.0
            if odd_heavy_bet and not is_odd: heat += 80.0
            if even_heavy_bet and is_odd: heat += 80.0
                
            # 波色断龙
            color = NUM_TO_COLOR.get(n, '绿')
            if streak_len >= 3 and color != streak_color:
                heat += 120.0  

            capital_heat[n] = heat

        # ==========================================
        # 🛡️ 庄家收割打分：安全分数 = 10000 - 资金热度
        # ==========================================
        scores = {}
        for n in range(1, 50):
            scores[n] = 10000.0 - capital_heat[n]

        # 锁定庄家低赔付玄学盲区
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top6_specials = [item[0] for item in sorted_scores[:6]]
        primary_special = top6_specials[0]
        
        normal_candidates = []
        for num, _ in sorted_scores:
            if num == primary_special: continue
            normal_candidates.append(num)
            if len(normal_candidates) >= 6: break

        is_top1_hit = (actual_special == primary_special)
        is_top6_hit = (actual_special in top6_specials)
        normal_hit_count = len(set(normal_candidates).intersection(actual_normals))
        
        if is_top1_hit: top1_hit_count += 1
        if is_top6_hit: top6_hit_count += 1
        normal_hit_rates.append(normal_hit_count)

        hit_status = "🎯 TOP1 玄学斩杀!" if is_top1_hit else ("✅ TOP6 完美避险" if is_top6_hit else "❌ 庄家常规派彩")
        print(f"| 期数: {target_period} | 真实特码: {actual_special:02d} | 玄学杀猪 Top6: {[f'{n:02d}' for n in top6_specials]} | 状态: {hit_status}")

    print("-" * 75)
    print("📊 [玄学迷信 + 杀猪盘资金热力模型 - 50期回测总结]")
    print(f"测试样本量: {test_window} 期")
    print(f"绝对盲区狙击命中率 (Top 1): {top1_hit_count} / {test_window}  ({(top1_hit_count/test_window)*100:.2f}%)")
    print(f"低赔付矩阵防守成功率 (Top 6): {top6_hit_count} / {test_window}  ({(top6_hit_count/test_window)*100:.2f}%)")
    print(f"正码防守平均散户避险数: {np.mean(normal_hit_rates):.2f} / 6")
    print("-" * 75)

if __name__ == '__main__':
    run_metaphysics_heatmap_backtest(test_window=50)
