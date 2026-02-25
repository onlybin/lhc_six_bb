import os
import subprocess
import json
import sys
import io
import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='ignore')

# 文件路径配置
LOTTERY_DATA_FILE = 'lottery_complete.json'
ANALYSIS_RESULT_FILE = 'analysis_result.json'
PREDICTION_RESULT_FILE = 'prediction.json'
CHART_DATA_FILE = 'chart_data.json'
REPORT_FILE = 'lottery_analysis_report.md'

def run_script(script_name, *args):
    cmd = [sys.executable, script_name] + list(args)
    print(f"\n>>> 正在运行: {' '.join(cmd)}")
    process = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    if process.returncode != 0:
        print(f"错误: {script_name} 运行失败\n{process.stderr}")
        exit(1)
    print(process.stdout)
    return process.stdout

def run_predictor_with_fallback():
    """智能容灾降级机制：优先跑 Pro 版，报错则自动回退旧版"""
    print("\n>>> 🚀 尝试启动 [资金热力反推引擎] (predictor_pro.py)...")
    cmd_pro = [sys.executable, 'predictor_pro.py']
    process_pro = subprocess.run(cmd_pro, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    
    if process_pro.returncode == 0:
        print(process_pro.stdout)
        return
        
    print(f"⚠️ [Pro 版本运行异常] (系统已拦截):\n{process_pro.stderr}")
    print(">>> 🔄 触发自动降级保护：正在切换回备用引擎 (predictor.py)...")
    
    cmd_base = [sys.executable, 'predictor.py']
    process_base = subprocess.run(cmd_base, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    
    if process_base.returncode == 0:
        print(process_base.stdout)
    else:
        print(f"❌ [致命错误] 备用引擎也运行失败：\n{process_base.stderr}")
        exit(1)

def generate_report(latest_prediction, analysis_data):
    print("\n>>> 正在组装行为金融反杀大屏报告...")
    total_records = analysis_data.get('total_records', 0)
    
    special_rec_text = []
    top_specials = latest_prediction.get('recommendation', {}).get('special_numbers', [])
    for i, num in enumerate(top_specials):
        found = next((item for item in latest_prediction.get('top_scores', []) if item[0] == num), None)
        if found:
            score, zodiac = found[1], found[2]
            wuxing = found[3] if len(found)>3 else '?'
            color = found[4] if len(found)>4 else '?'
            if i == 0:
                special_rec_text.append(f"- **[绝对盲区] 第{i+1}名: {num:02d} ({zodiac}/{wuxing}/{color}波)** - 安全权重: **{score:.2f}** 🛡️")
            else:
                special_rec_text.append(f"- 第{i+1}名: **{num:02d} ({zodiac}/{wuxing}/{color}波)** - 安全权重: {score:.2f}")
    special_text_block = '\n'.join(special_rec_text)

    normal_rec_text = []
    for num in latest_prediction.get('recommended_normal', []):
        found = next((item for item in latest_prediction.get('top_scores', []) if item[0] == num), None)
        normal_rec_text.append(f"- **{num:02d} ({found[2] if found else '?'})**")
    normal_text_block = '\n'.join(normal_rec_text)

    # 强制转换为东八区时间
    tz = datetime.timezone(datetime.timedelta(hours=8))
    report_time = datetime.datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    
    attributes = latest_prediction.get('combo_attributes', {})

    report_content = f"""# 📊 行为金融与资金热力反推大屏

**最近更新时间:** {report_time} | **目标推演期数:** 第 {latest_prediction.get('next_period')} 期

> **[底层协议]** 数据仓基于 {total_records} 期无损全量回溯。当前算法已全面切入【散户资金热力反推模型】。推演逻辑捕捉全网追热、博反弹、倍投追漏等散户博弈动作，为您反向锁定庄家低赔付的“绝对安全区”。

---

### 🎯 2.1 绝密防守矩阵 (低热度盲区 Top 6)
*(注：列表按全网模拟下注资金量由低到高排序。权重分数越高，代表该号码吸附的散户资金越少，被庄家作为杀猪出口的概率越高。)*
{special_text_block}

### 🎲 2.2 边缘正码精选 (6个常规防守位)
{normal_text_block}

### ⚖️ 2.3 宏观偏态诱导指标
*(注：当盘面某项指标发生严重倾斜时，散户通常会重仓抄底博反方向，此时庄家往往会继续顺势爆破。以下为当前极易触发反杀的预期偏向：)*
- **盘面奇偶预期:** {attributes.get('odd_even', '未知')}
- **盘面大小预期:** {attributes.get('big_small', '未知')}
- **7球预期和值:** {attributes.get('sum', '未知')}
"""
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(report_content)

def main():
    for f in [ANALYSIS_RESULT_FILE, PREDICTION_RESULT_FILE, CHART_DATA_FILE, REPORT_FILE]:
        if os.path.exists(f):
            try: os.remove(f)
            except: pass

    run_script('fetcher.py')
    run_script('analyzer.py')
    
    # 执行包含降级机制的热力引擎
    run_predictor_with_fallback()

    with open(PREDICTION_RESULT_FILE, 'r', encoding='utf-8') as f:
        prediction_data = json.load(f)
    with open(ANALYSIS_RESULT_FILE, 'r', encoding='utf-8') as f:
        analysis_data = json.load(f)

    generate_report(prediction_data, analysis_data)
    print("\n=========================================")
    print("✅ 行为金融流水线执行完毕！请刷新极客大屏查看最终矩阵。")
    print("=========================================\n")

if __name__ == '__main__':
    main()
