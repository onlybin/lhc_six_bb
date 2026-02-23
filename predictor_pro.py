import json
import os
import numpy as np
import sqlite3
from collections import defaultdict, deque
import datetime
from sklearn.ensemble import IsolationForest

# 🔌 接入独立 AI 算法库
import ai_models

# ==========================================
# 基础易理与规则字典推算
# ==========================================
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

# 新增：从 SQLite 数据库提取结构化数据
def get_records_from_db(db_path='lottery.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT period, raw_time, numbers, zodiacs, special, special_zodiac FROM history ORDER BY period DESC")
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

def predict_next_period(db_file='lottery.db', output_file='prediction.json', memory_file='learning_memory.json'):
    # 修改：使用 get_records_from_db 替代 json.load
    records = get_records_from_db(db_file)

    latest = records[0]
    next_period = str(int(latest['period']) + 1)
    
    ZODIAC_MAP = get_current_zodiac_map()
    NUM_TO_ZODIAC = {n: z for z, nums in ZODIAC_MAP.items() for n in nums}
    WUXING_MAP = get_current_wuxing_map()
    NUM_TO_WUXING = {n: w for w, nums in WUXING_MAP.items() for n in nums}
    COLOR_MAP = get_color_map()
    NUM_TO_COLOR = {n: c for c, nums in COLOR_MAP.items() for n in nums}

    RELATIONS = {
        '三合': {'鼠':['龍','猴'], '牛':['蛇','雞'], '虎':['馬','狗'], '兔':['豬','羊'], '龍':['鼠','猴'], '蛇':['牛','雞'], '馬':['虎','狗'], '羊':['兔','豬'], '猴':['鼠','龍'], '雞':['牛','蛇'], '狗':['虎','馬'], '豬':['兔','羊']},
        '六合': {'鼠':'牛', '牛':'鼠', '虎':'豬', '豬':'虎', '兔':'狗', '狗':'兔', '龍':'雞', '雞':'龍', '蛇':'猴', '猴':'蛇', '馬':'羊', '羊':'馬'},
        '正冲': {'鼠':'馬', '馬':'鼠', '牛':'羊', '羊':'牛', '虎':'猴', '猴':'虎', '兔':'雞', '雞':'兔', '龍':'狗', '狗':'龍', '蛇':'豬', '豬':'蛇'},
        '六害': {'鼠':'羊', '羊':'鼠', '牛':'馬', '馬':'牛', '虎':'蛇', '蛇':'虎', '兔':'龍', '龍':'兔', '猴':'豬', '豬':'猴', '狗':'雞', '雞':'狗'}
    }
    WUXING_SHENG = {'金':'水', '水':'木', '木':'火', '火':'土', '土':'金'}
    WUXING_KE = {'金':'木', '木':'土', '土':'水', '水':'火', '火':'金'}

    print("\n" + "="*50)
    print("[系统] 量化分析与记忆读取中...")
    latest_actual_nums = set(latest['numbers'])
    latest_actual_special = latest['special']
    
    if os.path.exists(memory_file):
        with open(memory_file, 'r', encoding='utf-8') as mf:
            memory = json.load(mf)
        if memory.get('target_period') == latest['period']:
            pred_normals = set(memory.get('recommended_normal', []))
            pred_specials = set(memory.get('recommended_special', []))
            hit_normals = pred_normals.intersection(latest_actual_nums)
            hit_special = latest_actual_special in pred_specials
            print(f"  [复盘期数]: 第 {latest['period']} 期")
            print(f"  [实际开出]: 正码 {latest['numbers']} | 特码 {latest_actual_special}")
            print(f"  [系统推演]: 推荐正码 {list(pred_normals)} | 特码矩阵 {list(pred_specials)}")
        else:
            print("  [状态]: 暂无匹配的上一期记忆，开始初始化学习。")
    print("="*50 + "\n")

    # ==========================================
    # 模块 1：特征清洗
    # ==========================================
    reversed_records = records[::-1]
    miss_tracker = {n: 0 for n in range(1, 50)}
    freq_all = {n: 0 for n in range(1, 50)}
    recent_50_queue = deque(maxlen=50) 
    recent_30_queue = deque(maxlen=30) 
    running_trans_counts = defaultdict(lambda: defaultdict(int))
    running_trans_totals = defaultdict(int)

    X_train_data = [] 
    y_train_data = [] 
    
    iso_forest = IsolationForest(contamination=0.1, random_state=42)
    
    for i in range(len(reversed_records) - 1):
        curr_draw = reversed_records[i]
        next_draw = reversed_records[i+1]
        
        curr_nums = set(curr_draw['numbers'] + [curr_draw['special']])
        next_nums = set(next_draw['numbers'] + [next_draw['special']])
        
        recent_50_queue.append(curr_nums)
        recent_30_queue.append(curr_nums)
        for n in curr_nums: freq_all[n] += 1
        for n in range(1, 50):
            if n in curr_nums: miss_tracker[n] = 0
            else: miss_tracker[n] += 1

        freq_recent_50 = {n: 0 for n in range(1, 50)}
        for past_nums in recent_50_queue:
            for n in past_nums: freq_recent_50[n] += 1
                
        freq_10 = {n: 0 for n in range(1, 50)}
        freq_30 = {n: 0 for n in range(1, 50)}
        for past_nums in list(recent_30_queue)[-10:]:
            for n in past_nums: freq_10[n] += 1
        for past_nums in recent_30_queue:
            for n in past_nums: freq_30[n] += 1
                
        last_special_zodiac = curr_draw['special_zodiac']
        last_special_wuxing = NUM_TO_WUXING.get(curr_draw['special'], '金')
        sanhe = RELATIONS['三合'].get(last_special_zodiac, [])
        liuhe = RELATIONS['六合'].get(last_special_zodiac, '')
        zhengchong = RELATIONS['正冲'].get(last_special_zodiac, '')
        liuhai = RELATIONS['六害'].get(last_special_zodiac, '')

        for n in range(1, 50):
            z = NUM_TO_ZODIAC.get(n, '')
            w = NUM_TO_WUXING.get(n, '')
            c = NUM_TO_COLOR.get(n, '绿')
            zodiac_rel_val = 1 if z in sanhe or z == liuhe else (-1 if z == zhengchong or z == liuhai else 0)
            wuxing_rel_val = 1 if WUXING_SHENG.get(last_special_wuxing) == w else (-1 if WUXING_KE.get(last_special_wuxing) == w else 0)
            color_val = 1 if c == '红' else (2 if c == '蓝' else 3) 
            macd_val = (freq_10[n] / 10.0) - (freq_30[n] / 30.0) if len(recent_30_queue) >= 30 else 0
            markov_prob = running_trans_counts[last_special_zodiac][z] / running_trans_totals[last_special_zodiac] if running_trans_totals[last_special_zodiac] > 0 else 0.0
            
            feat = [
                miss_tracker[n], freq_all[n], freq_recent_50[n], macd_val, markov_prob,                
                1 if n >= 25 else 0, 1 if n % 2 != 0 else 0, zodiac_rel_val, wuxing_rel_val, color_val
            ]
            X_train_data.append(feat)
            y_train_data.append(1 if n in next_nums else 0)
            
        running_trans_counts[curr_draw['special_zodiac']][next_draw['special_zodiac']] += 1
        running_trans_totals[curr_draw['special_zodiac']] += 1

    iso_forest.fit(X_train_data)
    anomaly_scores = iso_forest.decision_function(X_train_data)
    for idx in range(len(X_train_data)):
        X_train_data[idx].append(anomaly_scores[idx])

    # 最新一期的特征构造
    latest_nums = set(latest['numbers'] + [latest['special']])
    recent_50_queue.append(latest_nums)
    recent_30_queue.append(latest_nums)
    for n in latest_nums: freq_all[n] += 1
    for n in range(1, 50):
        if n in latest_nums: miss_tracker[n] = 0
        else: miss_tracker[n] += 1

    freq_recent_50 = {n: 0 for n in range(1, 50)}
    for past_nums in recent_50_queue:
        for n in past_nums: freq_recent_50[n] += 1
            
    freq_10 = {n: 0 for n in range(1, 50)}
    freq_30 = {n: 0 for n in range(1, 50)}
    for past_nums in list(recent_30_queue)[-10:]:
        for n in past_nums: freq_10[n] += 1
    for past_nums in recent_30_queue:
        for n in past_nums: freq_30[n] += 1

    recent_10_big = sum(1 for r in records[:10] for n in r['numbers']+[r['special']] if n >= 25)
    recent_10_odd = sum(1 for r in records[:10] for n in r['numbers']+[r['special']] if n % 2 != 0)
    big_bias = (recent_10_big / 70.0) - 0.5
    odd_bias = (recent_10_odd / 70.0) - 0.5
    
    last_special_zodiac = latest['special_zodiac']
    last_special_wuxing = NUM_TO_WUXING.get(latest['special'], '金')
    sanhe = RELATIONS['三合'].get(last_special_zodiac, [])
    liuhe = RELATIONS['六合'].get(last_special_zodiac, '')
    zhengchong = RELATIONS['正冲'].get(last_special_zodiac, '')
    liuhai = RELATIONS['六害'].get(last_special_zodiac, '')

    X_predict_data = []
    for n in range(1, 50):
        z = NUM_TO_ZODIAC.get(n, '')
        w = NUM_TO_WUXING.get(n, '')
        c = NUM_TO_COLOR.get(n, '绿')
        zodiac_rel_val = 1 if z in sanhe or z == liuhe else (-1 if z == zhengchong or z == liuhai else 0)
        wuxing_rel_val = 1 if WUXING_SHENG.get(last_special_wuxing) == w else (-1 if WUXING_KE.get(last_special_wuxing) == w else 0)
        color_val = 1 if c == '红' else (2 if c == '蓝' else 3)
        macd_val = (freq_10[n] / 10.0) - (freq_30[n] / 30.0) if len(recent_30_queue) >= 30 else 0
        markov_prob = running_trans_counts[last_special_zodiac][z] / running_trans_totals[last_special_zodiac] if running_trans_totals[last_special_zodiac] > 0 else 0.0
        
        feat = [
            miss_tracker[n], freq_all[n], freq_recent_50[n], macd_val, markov_prob,
            1 if n >= 25 else 0, 1 if n % 2 != 0 else 0, zodiac_rel_val, wuxing_rel_val, color_val
        ]
        X_predict_data.append(feat)

    curr_anomaly_scores = iso_forest.decision_function(X_predict_data)
    for idx in range(len(X_predict_data)):
        X_predict_data[idx].append(curr_anomaly_scores[idx])

    # ==========================================
    # 🌟 模块 2：呼叫外部插件
    # ==========================================
    ensemble_probabilities = ai_models.get_ensemble_probabilities(X_train_data, y_train_data, X_predict_data)

    # ==========================================
    # 模块 3：继承指纹与偏态补偿
    # ==========================================
    scores = defaultdict(float)
    for n in range(1, 50):
        if n in latest_nums:
            continue

        base_score = ensemble_probabilities[n-1] * 100
        is_big = 1 if n >= 25 else 0
        is_odd = 1 if n % 2 != 0 else 0
        macd_val = X_predict_data[n-1][3]
        
        if big_bias > 0.05 and not is_big: base_score += 1.5
        elif big_bias < -0.05 and is_big: base_score += 1.5
        if odd_bias > 0.05 and not is_odd: base_score += 1.5
        elif odd_bias < -0.05 and is_odd: base_score += 1.5

        continuous_fingerprint = (miss_tracker[n] * 0.033) + (freq_all[n] * 0.011) - (freq_recent_50[n] * 0.04) + (macd_val * 0.05)
        scores[n] = base_score + continuous_fingerprint

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    print(f"\n>>> 双引擎融合推演完毕 - 第 {next_period} 期高分特码雷达 (前6名观测):")
    top6_specials = []
    for i, (num, score) in enumerate(sorted_scores[:6]):
        zodiac = NUM_TO_ZODIAC.get(num, '?')
        wuxing = NUM_TO_WUXING.get(num, '?')
        color = NUM_TO_COLOR.get(num, '?')
        macd = X_predict_data[num-1][3]
        macd_tag = "[+升温]" if macd > 0 else ("[-降温]" if macd < 0 else "[平稳]")
        print(f"  顺位 {i+1}: 号码 {num:02d} ({zodiac}/{wuxing}/{color}波) {macd_tag} - 综合权重: {score:.3f}")
        top6_specials.append(num)
    
    primary_special = top6_specials[0]
    
    normal_candidates = []
    for num, score in sorted_scores:
        if num == primary_special: 
            continue
        normal_candidates.append(num)
        if len(normal_candidates) >= 6:
            break
            
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

    memory_data = {
        'target_period': next_period,
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'recommended_normal': normal_candidates,
        'recommended_special': top6_specials            
    }
    with open(memory_file, 'w', encoding='utf-8') as mf:
        json.dump(memory_data, mf, ensure_ascii=False, indent=2)

    print(f"\n推演完成！基础代码已原样保留，XGBoost 模型插件调用成功。")

if __name__ == '__main__':
    predict_next_period()
