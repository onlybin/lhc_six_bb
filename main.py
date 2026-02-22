import os
import subprocess
import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='ignore')

# 文件路径配置
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

def generate_report(latest_prediction, analysis_data):
    print("\n>>> 正在组装全模态分析报告...")
    
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
                special_rec_text.append(f"- **[首选] 第{i+1}名: {num:02d} ({zodiac}/{wuxing}/{color}波)** - 综合权重: **{score:.2f}** 🏆")
            else:
                special_rec_text.append(f"- 第{i+1}名: **{num:02d} ({zodiac}/{wuxing}/{color}波)** - 综合权重: {score:.2f}")
    special_text_block = '\n'.join(special_rec_text)

    normal_rec_text = []
    for num in latest_prediction.get('recommended_normal', []):
        found = next((item for item in latest_prediction.get('top_scores', []) if item[0] == num), None)
        normal_rec_text.append(f"- **{num:02d} ({found[2] if found else '?'})**")
    normal_text_block = '\n'.join(normal_rec_text)

    import datetime
    report_date = datetime.date.today().strftime('%Y年%m月%d日')
    attributes = latest_prediction.get('combo_attributes', {})

    report_content = f"""# 📊 AI 量化推演核心决策大屏

**报告生成时间:** {report_date} | **目标推演期数:** 第 {latest_prediction.get('next_period')} 期

> **[系统提示]** 基础算力平台已全面升级至 SQLite 关系型数据库底层，保障高并发分析安全。本期推演基于 {total_records} 期无损全量回溯。

---

### 🎯 2.1 特码预测 (高置信度矩阵)
*(注：列表依据孤立森林异常分、时序 MACD 动能及马尔可夫链转移概率综合降序排列)*
{special_text_block}

### 🎲 2.2 正码精选 (6个防守位)
{normal_text_block}

### ⚖️ 2.3 核心偏态指标
- **预测奇偶比:** {attributes.get('odd_even', '未知')}
- **预测大小比:** {attributes.get('big_small', '未知')}
- **7球预期和值:** {attributes.get('sum', '未知')}
"""
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(report_content)

def main():
    # 注意：这里移除了对 lottery.db 数据库文件的删除操作！保证安全积累。
    for f in [ANALYSIS_RESULT_FILE, PREDICTION_RESULT_FILE, CHART_DATA_FILE, REPORT_FILE]:
        if os.path.exists(f):
            try: os.remove(f)
            except: pass

    run_script('fetcher.py')
    run_script('analyzer.py')
    run_script('predictor.py')

    with open(PREDICTION_RESULT_FILE, 'r', encoding='utf-8') as f:
        prediction_data = json.load(f)
    with open(ANALYSIS_RESULT_FILE, 'r', encoding='utf-8') as f:
        analysis_data = json.load(f)

    generate_report(prediction_data, analysis_data)
    print("\n=========================================")
    print("✅ 全自动化流水线(SQLite版)执行完毕！")
    print("=========================================\n")

if __name__ == '__main__':
    main()