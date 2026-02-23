import json
import sqlite3
import datetime
from collections import defaultdict, deque
import numpy as np
from sklearn.ensemble import IsolationForest

# 接入独立的 AI 算法库
import ai_models

# ==========================================
# 基础字典推算 (保持与主程序完全一致)
# ==========================================
def get_current_zodiac_map(ref_year):
    zodiac_order = ['鼠', '牛', '虎', '兔', '龍', '蛇', '馬', '羊', '猴', '雞', '狗', '豬']
    year = ref_year
    # 简化处理：假设立春分界，此处以基准年份计算
    base_year = 2020
    current_zodiac_idx = (year - base_year) % 12
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
    cursor.execute("SELECT period, raw_time, numbers, zodiacs, special, special_zodiac FROM history ORDER BY period ASC") # 注意：回测需按时间正序排列
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

# ==========================================
# 核心回测逻辑
# ==========================================
def run_backtest(test_window=20, db_file='lottery.db'):
    records = get_records_from_db(db_file)
    total_records = len(records)
    
    if total_records < test_window + 50:
        print("错误：数据量不足以支撑回测窗口与特征冷启动要求。")
        return

    print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] 开始执行量化回测...")
    print(f"总数据量: {total_records} 期 | 回测窗口: 近 {test_window} 期")
    print("-" * 60)

    top1_hit_count = 0
    top6_hit_count = 0
    normal_hit_rates = []

    # 步进验证循环 (Walk-Forward)
    for i in range(total_records - test_window, total_records):
        # 1. 截断数据：只取目标期之前的数据作为“历史”
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

        RELATIONS = {
            '三合': {'鼠':['龍','猴'], '牛':['蛇','雞'], '虎':['馬','狗'], '兔':['豬','羊'], '龍':['鼠','猴'], '蛇':['牛','雞'], '馬':['虎','狗'], '羊':['兔','豬'], '猴':['鼠','龍'], '雞':['牛','蛇'], '狗':['虎','馬'], '豬':['兔','羊']},
            '六合': {'鼠':'牛', '牛':'鼠', '虎':'豬', '豬':'虎', '兔':'狗', '狗':'兔', '龍':'雞', '雞':'龍', '蛇':'猴', '猴':'蛇', '馬':'羊', '羊':'馬'},
            '正冲': {'鼠':'馬', '馬':'鼠', '牛':'羊', '羊':'牛', '虎':'猴', '猴':'虎', '兔':'雞', '雞':'兔', '龍':'狗', '狗':'龍', '蛇':'豬', '豬':'蛇'},
            '六害': {'鼠':'羊', '羊':'鼠', '牛':'馬', '馬':'牛', '虎':'蛇', '蛇':'虎', '兔':'龍', '龍':'兔', '猴':'豬', '豬':'猴', '狗':'雞', '雞':'狗'}
        }
        WUXING_SHENG = {'金':'水', '水':'木', '木':'火', '火':'土', '土':'金'}
        WUXING_KE = {'金':'木', '木':'土', '土':'水', '水':'火', '火':'金'}

        # 2. 特征工程构建 (基于截断的历史数据)
        miss_tracker = {n: 0 for n in range(1, 50)}
        freq_all = {n: 0 for n in range(1, 50)}
        recent_50_queue = deque(maxlen=50) 
        recent_30_queue = deque(maxlen=30) 
        running_trans_counts = defaultdict(lambda: defaultdict(int))
        running_trans_totals = defaultdict(int)

        X_train_data = [] 
        y_train_data = [] 
        
        iso_forest = IsolationForest(contamination=0.1, random_state=42)
        
        for j in range(len(history_slice) - 1):
            curr_draw = history_slice[j]
            next_draw = history_slice[j+1]
            
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

        # 构建待预测的最新一期特征
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

        reversed_hist = history_slice[::-1]
        recent_10_big = sum(1 for r in reversed_hist[:10] for n in r['numbers']+[r['special']] if n >= 25)
        recent_10_odd = sum(1 for r in reversed_hist[:10] for n in r['numbers']+[r['special']] if n % 2 != 0)
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

        # 3. 调用 AI 算法模块 (静默输出以避免刷屏)
        import sys, os
        original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w') # 临时屏蔽 ai_models 内部的 print 
        ensemble_probabilities = ai_models.get_ensemble_probabilities(X_train_data, y_train_data, X_predict_data)
        sys.stdout = original_stdout # 恢复输出

        # 4. 偏态补偿与打分
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

        # 5. 提取预测结果
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top6_specials = [item[0] for item in sorted_scores[:6]]
        primary_special = top6_specials[0]
        
        normal_candidates = []
        for num, _ in sorted_scores:
            if num == primary_special: continue
            normal_candidates.append(num)
            if len(normal_candidates) >= 6: break

        # 6. 对比真实结果进行评判
        is_top1_hit = (actual_special == primary_special)
        is_top6_hit = (actual_special in top6_specials)
        normal_hit_count = len(set(normal_candidates).intersection(actual_normals))
        
        if is_top1_hit: top1_hit_count += 1
        if is_top6_hit: top6_hit_count += 1
        normal_hit_rates.append(normal_hit_count)

        # 打印单期回测日志
        hit_status = "🎯 TOP1精确命中" if is_top1_hit else ("✅ TOP6矩阵命中" if is_top6_hit else "❌ 未命中")
        print(f"| 期数: {target_period} | 真实特码: {actual_special:02d} | 预测Top6: {[f'{n:02d}' for n in top6_specials]} | 状态: {hit_status} | 正码防守命中: {normal_hit_count}/6")

    # ==========================================
    # 输出量化评估报告
    # ==========================================
    print("-" * 60)
    print("📊 [量化回测总结报告]")
    print(f"测试样本量: {test_window} 期")
    print(f"首选特码命中率 (Top 1): {top1_hit_count} / {test_window}  ({(top1_hit_count/test_window)*100:.2f}%)")
    print(f"核心矩阵命中率 (Top 6): {top6_hit_count} / {test_window}  ({(top6_hit_count/test_window)*100:.2f}%)")
    print(f"正码防守平均命中数: {np.mean(normal_hit_rates):.2f} / 6")
    print("-" * 60)

if __name__ == '__main__':
    # 默认回测最近 20 期，可自行修改参数
    run_backtest(test_window=20)