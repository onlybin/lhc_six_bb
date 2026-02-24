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

def run_capital_heatmap_backtest(test_window=50, db_file='lottery.db'):
    records = get_records_from_db(db_file)
    total_records = len(records)
    
    if total_records < test_window + 50:
        print("错误：数据量不足以支撑回测窗口。")
        return

    print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] 开启【散户资金热力图反杀】测试引擎...")
    print(f"核心逻辑：模拟散户下注心理，锁定全盘资金量最低的庄家安全盲区。")
    print("-" * 65)

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
        
        # 计算基础统计指标
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

        # 更新最新一期
        latest_nums = set(latest['numbers'] + [latest['special']])
        for n in range(1, 50):
            if n in latest_nums: miss_tracker[n] = 0
            else: miss_tracker[n] += 1

        # 宏观偏态探测 (反推散户抄底资金)
        reversed_hist = history_slice[::-1]
        recent_5_big = sum(1 for r in reversed_hist[:5] for n in r['numbers']+[r['special']] if n >= 25)
        recent_5_odd = sum(1 for r in reversed_hist[:5] for n in r['numbers']+[r['special']] if n % 2 != 0)
        
        # 散户心理：如果最近严重偏大，散户一定会重注买小博反弹
        big_heavy_bet = recent_5_big > 20  # 大数过热，散户买小数
        small_heavy_bet = recent_5_big < 15 # 小数过热，散户买大数
        odd_heavy_bet = recent_5_odd > 20
        even_heavy_bet = recent_5_odd < 15

        # ==========================================
        # 🧨 核心模块：构建散户资金热力图 (Simulated Betting Heatmap)
        # ==========================================
        capital_heat = {}
        for n in range(1, 50):
            heat = 100.0  # 基础底仓资金
            
            # 1. 生日效应偏差 (日历号 1-31 资金天然沉淀)
            if n <= 31:
                heat += 25.0
                
            # 2. 玄学吉利号资金
            if n % 10 in [6, 8, 9] or n in [11, 22, 33, 44]:
                heat += 30.0
                
            # 3. 赌徒谬误：追漏资金 (呈指数级倍投)
            if miss_tracker[n] >= 10:
                # 遗漏超过10期后，每多一期，散户倍投的资金加码越重
                heat += 15.0 + (miss_tracker[n] - 10) * 8.0 
            if miss_tracker[n] > 20:
                heat += 100.0 # 绝对冷号，挂满散户血本，极度危险区域

            # 4. 追热效应：刚出的号和近期狂爆的号
            if miss_tracker[n] == 0:
                heat += 40.0 # 刚出的上期号码，散户喜欢买连码
            if freq_10[n] >= 3:
                heat += 50.0 # 旺码资金堆积
                
            # 5. 宏观偏态反推：抄底资金
            is_big = n >= 25
            is_odd = n % 2 != 0
            if big_heavy_bet and not is_big: heat += 60.0  # 散户疯狂买小
            if small_heavy_bet and is_big: heat += 60.0    # 散户疯狂买大
            if odd_heavy_bet and not is_odd: heat += 60.0  
            if even_heavy_bet and is_odd: heat += 60.0

            # 记录该号码的模拟资金量
            capital_heat[n] = heat

        # ==========================================
        # 🛡️ 庄家收割打分：资金热度越低，分数越高 (完全逆向)
        # ==========================================
        scores = {}
        for n in range(1, 50):
            # 核心转化：得分 = 负的资金热度
            scores[n] = -capital_heat[n]

        # 获取得分最高（即资金热度最低的无视盲区）的6个号码
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top6_specials = [item[0] for item in sorted_scores[:6]]
        primary_special = top6_specials[0]
        
        # 正码防守矩阵
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

        hit_status = "🎯 TOP1 盲区狙击!" if is_top1_hit else ("✅ TOP6 低热命中" if is_top6_hit else "❌ 庄家放弃收割")
        print(f"| 期数: {target_period} | 真实特码: {actual_special:02d} | 低热度盲区 Top6: {[f'{n:02d}' for n in top6_specials]} | 状态: {hit_status}")

    print("-" * 65)
    print("📊 [资金热力图反杀模拟 - 回测总结报告]")
    print(f"测试样本量: {test_window} 期")
    print(f"庄家绝对盲区命中率 (Top 1): {top1_hit_count} / {test_window}  ({(top1_hit_count/test_window)*100:.2f}%)")
    print(f"低赔付矩阵命中率 (Top 6): {top6_hit_count} / {test_window}  ({(top6_hit_count/test_window)*100:.2f}%)")
    print(f"正码防守平均命中数: {np.mean(normal_hit_rates):.2f} / 6")
    print("-" * 65)

if __name__ == '__main__':
    run_capital_heatmap_backtest(test_window=50)
