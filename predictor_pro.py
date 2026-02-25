import json
import sqlite3
import datetime
from collections import deque
import os

def get_current_zodiac_map():
    zodiac_order = ['鼠', '牛', '虎', '兔', '龍', '蛇', '馬', '羊', '猴', '雞', '狗', '豬']
    now = datetime.datetime.now()
    year = now.year
    if now.month == 1 or (now.month == 2 and now.day < 5): year -= 1
    base_year = 2020
    current_zodiac_idx = (year - base_year) % 12
    zodiac_map = {z: [] for z in zodiac_order}
    for num in range(1, 50):
        offset = (num - 1) % 12
        z_idx = (current_zodiac_idx - offset) % 12
        zodiac_map[zodiac_order[z_idx]].append(num)
    return zodiac_map

def get_current_wuxing_map():
    nayin_cycle = ['金', '火', '木', '土', '金', '火', '水', '土', '金', '木',
                   '水', '土', '火', '木', '水', '金', '火', '木', '土', '金',
                   '火', '水', '土', '金', '木', '水', '土', '火', '木', '水']
    now = datetime.datetime.now()
    current_year = now.year
    if now.month == 1 or (now.month == 2 and now.day < 5): current_year -= 1
    wuxing_map = {'金': [], '木': [], '水': [], '火': [], '土': []}
    for num in range(1, 50):
        target_year = current_year - num + 1
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
    cursor.execute("SELECT period, numbers, special, special_zodiac FROM history ORDER BY period ASC")
    rows = cursor.fetchall()
    conn.close()
    
    records = []
    for row in rows:
        records.append({
            "period": row[0],
            "numbers": json.loads(row[1]),
            "special": row[2],
            "special_zodiac": row[3]
        })
    return records

def predict_next_period(db_file='lottery.db', output_file='prediction.json'):
    records = get_records_from_db(db_file)
    if not records:
        print("错误：数据库为空。")
        return
        
    latest = records[-1]
    next_period = str(int(latest['period']) + 1)
    
    ZODIAC_MAP = get_current_zodiac_map()
    NUM_TO_ZODIAC = {n: z for z, nums in ZODIAC_MAP.items() for n in nums}
    WUXING_MAP = get_current_wuxing_map()
    NUM_TO_WUXING = {n: w for w, nums in WUXING_MAP.items() for n in nums}
    COLOR_MAP = get_color_map()
    NUM_TO_COLOR = {n: c for c, nums in COLOR_MAP.items() for n in nums}

    print("\n" + "="*50)
    print(f"[系统] 启动【行为金融·资金热力盲区(精度强化版)】 - 目标期数: {next_period}")
    print("="*50 + "\n")

    miss_tracker = {n: 0 for n in range(1, 50)}
    freq_10 = {n: 0 for n in range(1, 50)}
    recent_30_queue = deque(maxlen=30)
    
    for r in records:
        curr_nums = set(r['numbers'] + [r['special']])
        recent_30_queue.append(curr_nums)
        for n in range(1, 50):
            if n in curr_nums: miss_tracker[n] = 0
            else: miss_tracker[n] += 1

    for past_nums in list(recent_30_queue)[-10:]:
        for n in past_nums: freq_10[n] += 1

    reversed_hist = records[::-1]
    recent_5_big = sum(1 for r in reversed_hist[:5] for n in r['numbers']+[r['special']] if n >= 25)
    recent_5_odd = sum(1 for r in reversed_hist[:5] for n in r['numbers']+[r['special']] if n % 2 != 0)
    
    big_heavy_bet = recent_5_big > 20
    small_heavy_bet = recent_5_big < 15
    odd_heavy_bet = recent_5_odd > 20
    even_heavy_bet = recent_5_odd < 15

    # ==========================================
    # 核心：纯粹的资金行为热力学 (附加微弱防并列梯度)
    # ==========================================
    capital_heat = {}
    for n in range(1, 50):
        heat = 100.0  
        
        # 1. 生日历法效应 (轻微影响)
        if n <= 31: heat += 25.0
            
        # 2. 赌徒谬误：追冷倍投 (极高权重)
        if miss_tracker[n] >= 10:
            heat += 15.0 + (miss_tracker[n] - 10) * 8.0 
        if miss_tracker[n] > 20:
            heat += 100.0 

        # 3. 追涨杀跌：旺码跟风 (高权重)
        if miss_tracker[n] == 0: heat += 40.0
        if freq_10[n] >= 3: heat += 50.0 
            
        # 4. 宏观偏态反推：抄底资金涌入
        is_big = n >= 25
        is_odd = n % 2 != 0
        if big_heavy_bet and not is_big: heat += 60.0
        if small_heavy_bet and is_big: heat += 60.0
        if odd_heavy_bet and not is_odd: heat += 60.0
        if even_heavy_bet and is_odd: heat += 60.0

        # 5. 🌟 微观惩罚梯度 (打破同分并列)
        # 即使都在盲区，遗漏值相对较大或数字靠后的号码，天然会多吸附一丝丝散户视线
        micro_gradient = (miss_tracker[n] * 0.1) + (n * 0.01)
        heat += micro_gradient

        capital_heat[n] = heat

    # ==========================================
    # 庄家视角：热度越低，安全分数越高 (严格浮点数排序)
    # ==========================================
    scores = {}
    for n in range(1, 50):
        scores[n] = 1000.0 - capital_heat[n]

    # 保留两位小数的高精度排序
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    top6_specials = [item[0] for item in sorted_scores[:6]]
    primary_special = top6_specials[0]
    normal_candidates = [item[0] for item in sorted_scores[6:12]]
    normal_candidates.sort()
    
    all_recommended = normal_candidates + [primary_special]
    odd_r = sum(1 for n in all_recommended if n % 2 == 1)
    even_r = len(all_recommended) - odd_r
    big_r = sum(1 for n in all_recommended if n >= 25)
    small_r = len(all_recommended) - big_r

    prediction = {
        'next_period': next_period,
        'based_on_period': latest['period'],
        'recommendation': {
            'normal_numbers': normal_candidates,
            'special_numbers': top6_specials,           
            'primary_special_zodiac': NUM_TO_ZODIAC.get(primary_special, '?')
        },
        'recommended_normal': normal_candidates,
        'recommended_special_top5': top6_specials,      
        'primary_special': primary_special,
        'primary_special_zodiac': NUM_TO_ZODIAC.get(primary_special, '?'),
        'combo_attributes': {
            'odd_even': f"奇{odd_r}偶{even_r}",
            'big_small': f"大{big_r}小{small_r}",
            'sum': sum(all_recommended)
        },
        'top_scores': [(num, float(score), NUM_TO_ZODIAC.get(num, '?'), NUM_TO_WUXING.get(num, '?'), NUM_TO_COLOR.get(num, '?')) for num, score in sorted_scores[:20]]
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(prediction, f, ensure_ascii=False, indent=2)

    print(f"✅ 庄家高精度盲区矩阵已生成！分析源已写入 {output_file}，准备通过主程序推送大屏。")

if __name__ == '__main__':
    predict_next_period()
