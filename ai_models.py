# ai_models.py
# 这是一个独立的 AI 算法模块，专门负责训练和提供预测概率

from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.model_selection import RandomizedSearchCV
from xgboost import XGBClassifier
import numpy as np

def get_anomaly_scores(X_train, X_predict):
    """引擎0：孤立森林（计算异常分，用于防范杀猪盘和极端偏态）"""
    iso_forest = IsolationForest(contamination=0.1, random_state=42)
    iso_forest.fit(X_train)
    train_scores = iso_forest.decision_function(X_train)
    predict_scores = iso_forest.decision_function(X_predict)
    return train_scores, predict_scores

def get_ensemble_probabilities(X_train, y_train, X_predict):
    """引擎1 & 引擎2：训练 Random Forest 和 XGBoost，并返回融合后的概率"""
    
    print(">>> [AI 核心子系统] 正在启动引擎 1: 随机森林 (AutoML 寻优)...")
    base_rf = RandomForestClassifier(class_weight='balanced', random_state=42)
    rf_param = {
        'n_estimators': [50, 100, 150],
        'max_depth': [3, 5, 8, None],
        'min_samples_split': [2, 5, 10]
    }
    rf_search = RandomizedSearchCV(base_rf, param_distributions=rf_param, n_iter=5, cv=3, scoring='roc_auc', random_state=42, n_jobs=1)
    rf_search.fit(X_train, y_train)
    rf_prob = rf_search.best_estimator_.predict_proba(X_predict)[:, 1]

    print(">>> [AI 核心子系统] 正在启动引擎 2: XGBoost 极度梯度提升树 (AutoML 寻优)...")
    base_xgb = XGBClassifier(eval_metric='logloss', random_state=42)
    xgb_param = {
        'n_estimators': [50, 100, 150],
        'max_depth': [3, 5, 7],
        'learning_rate': [0.01, 0.05, 0.1],
        'subsample': [0.8, 1.0]
    }
    xgb_search = RandomizedSearchCV(base_xgb, param_distributions=xgb_param, n_iter=5, cv=3, scoring='roc_auc', random_state=42, n_jobs=1)
    xgb_search.fit(X_train, y_train)
    xgb_prob = xgb_search.best_estimator_.predict_proba(X_predict)[:, 1]

    # Stacking 融合：两个模型各占 50% 的话语权 (Soft Voting)
    print(">>> [AI 核心子系统] 双引擎运算完毕，正在执行概率融合 (Soft-Voting)...")
    ensemble_probabilities = (rf_prob * 0.5) + (xgb_prob * 0.5)
    
    return ensemble_probabilities