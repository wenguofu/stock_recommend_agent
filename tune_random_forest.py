#!/usr/bin/env python3
"""
随机森林 方向预测 — 多轮回测调参

目标: walk-forward回测, 准确率→55%
方法: 逐股票扩展窗口训练, 网格搜索最优参数
"""

import sys, os, json, math, random, time, sqlite3
from datetime import datetime
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

def get_codes(n=1000, min_days=250):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT code FROM backtest_data GROUP BY code HAVING COUNT(*)>=? ORDER BY COUNT(*) DESC", (min_days,)).fetchall()
    conn.close()
    codes = [r[0] for r in rows]
    if len(codes) > n:
        random.seed(42)
        codes = random.sample(codes, n)
    return codes

def load_df(code):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT date,open,high,low,close,volume,turnover FROM backtest_data WHERE code=? ORDER BY date", conn, params=(code,))
    conn.close()
    if len(df) < 80: return None
    for c in ['close','high','low','open','volume']:
        df[c] = df[c].astype(float)
    return df

def build_features_labels(df):
    """从DataFrame构建特征矩阵X和标签y (5日方向)"""
    close = df['close'].values.astype(float)
    high = df['high'].values.astype(float)
    low = df['low'].values.astype(float)
    open_p = df['open'].values.astype(float)
    volume = df['volume'].values.astype(float)
    n = len(close)
    horizon = 5

    # 至少需要60天历史 + 5天未来
    if n < 65: return None, None

    feature_list = []
    
    for i in range(60, n - horizon):
        feats = {}
        # 收益率
        for p in [1, 3, 5, 10, 20]:
            feats[f'ret_{p}d'] = (close[i] / close[i-p] - 1) * 100 if i >= p else 0
        
        # 波动率
        rets = np.diff(close[i-20:i+1]) / close[i-20:i]
        feats['vol_20d'] = float(np.std(rets) * 100 * np.sqrt(252))
        
        # 均线偏离
        for p in [5, 10, 20, 60]:
            if i >= p:
                ma = np.mean(close[i-p+1:i+1])
                feats[f'ma_dev_{p}'] = (close[i] / ma - 1) * 100
        
        # RSI
        if i >= 15:
            deltas = np.diff(close[i-14:i+1])
            g = np.sum(deltas[deltas>0]) if np.any(deltas>0) else 0
            l = abs(np.sum(deltas[deltas<0])) if np.any(deltas<0) else 1e-10
            feats['rsi_14'] = 100 - 100/(1+g/l)
        
        # 量比
        avg_vol = np.mean(volume[i-20:i]) if i >= 20 else volume[i]
        feats['volume_ratio'] = volume[i] / avg_vol if avg_vol > 0 else 1.0
        
        # 布林带
        if i >= 20:
            ma20 = np.mean(close[i-19:i+1])
            std20 = np.std(close[i-19:i+1])
            if std20 > 0:
                feats['boll_pos'] = (close[i] - (ma20-2*std20)) / (4*std20) * 100
        
        # 回撤
        if i >= 20:
            peak = np.max(close[i-19:i+1])
            feats['dd_20d'] = (peak - close[i]) / peak * 100
        
        # 振幅
        feats['amplitude'] = (high[i] - low[i]) / open_p[i] * 100
        
        # 连续涨跌天数
        up_days = 0; down_days = 0
        for j in range(i, max(i-5, 0), -1):
            if close[j] > close[j-1]: up_days += 1
            else: break
        for j in range(i, max(i-5, 0), -1):
            if close[j] < close[j-1]: down_days += 1
            else: break
        feats['consec_up'] = up_days
        feats['consec_down'] = down_days
        
        feature_list.append(feats)
    
    X = pd.DataFrame(feature_list).fillna(0)
    y = np.array([1 if close[i+horizon] > close[i] else 0 for i in range(60, n-horizon)])
    
    return X, y

def walk_forward_backtest(df, X, y, params, retrain_every=20):
    """
    Walk-forward回测: 逐段训练, 逐段预测
    返回: accuracy, predictions
    """
    from sklearn.ensemble import RandomForestClassifier
    
    n = len(X)
    if n < 60: return None
    
    train_start = 0
    correct = 0
    total = 0
    predictions = []
    
    for test_start in range(30, n, retrain_every):
        test_end = min(test_start + retrain_every, n)
        
        X_train = X.iloc[train_start:test_start]
        y_train = y[train_start:test_start]
        X_test = X.iloc[test_start:test_end]
        y_test = y[test_start:test_end]
        
        if len(X_train) < 30 or len(X_test) < 1:
            continue
        
        rf = RandomForestClassifier(
            n_estimators=params.get('n_estimators', 100),
            max_depth=params.get('max_depth', 5),
            min_samples_leaf=params.get('min_samples_leaf', 10),
            max_features=params.get('max_features', 'sqrt'),
            class_weight='balanced',
            random_state=42,
            n_jobs=-1,
        )
        
        rf.fit(X_train, y_train)
        preds = rf.predict(X_test)
        
        for j, pred in enumerate(preds):
            actual = y_test[j]
            correct += 1 if pred == actual else 0
            total += 1
            
            # 获取概率
            proba = None
            if hasattr(rf, 'predict_proba'):
                try:
                    proba = rf.predict_proba(X_test.iloc[j:j+1])[0]
                except:
                    pass
            
            predictions.append({
                'pred': int(pred),
                'actual': int(actual),
                'proba_up': round(float(proba[1])*100, 1) if proba is not None and len(proba)>1 else None,
                'train_size': len(X_train),
            })
    
    acc = correct / total * 100 if total > 0 else 0
    return acc, total, predictions

def grid_search_round(codes, param_grid, round_name, n_stocks=200):
    """在一组参数上回测, 返回平均准确率"""
    results = []
    
    for params in param_grid:
        total_correct = 0
        total_preds = 0
        
        for code in codes[:n_stocks]:
            df = load_df(code)
            if df is None: continue
            X, y = build_features_labels(df)
            if X is None: continue
            
            acc, n, _ = walk_forward_backtest(df, X, y, params)
            if acc is not None:
                total_correct += acc * n / 100
                total_preds += n
        
        avg_acc = total_correct / total_preds * 100 if total_preds > 0 else 0
        results.append({'params': params, 'accuracy': round(avg_acc, 2), 'predictions': total_preds})
        print(f"  {params['name']}: acc={avg_acc:.2f}% ({total_preds} preds)")
    
    return results

def main():
    print("=" * 60)
    print("随机森林 Walk-Forward 回测调参")
    print("=" * 60)
    
    codes = get_codes(200, min_days=250)
    print(f"\n股票池: {len(codes)}只 (≥250天数据)")
    
    # ═══ Round 1: 默认参数基线 ═══
    print(f"\n{'='*40}")
    print("Round 1: 默认参数基线")
    print(f"{'='*40}")
    
    base_params = [
        {'name': 'default(100/None/1)', 'n_estimators': 100, 'max_depth': None, 'min_samples_leaf': 1, 'max_features': 'sqrt'},
        {'name': 'rule_engine(baseline)', 'n_estimators': 0, 'max_depth': 0, 'min_samples_leaf': 0, 'max_features': 'rule'},
    ]
    
    # Rule engine baseline
    rule_acc, rule_n = 0, 0
    for code in codes[:200]:
        df = load_df(code)
        if df is None: continue
        close = df['close'].values.astype(float)
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        open_p = df['open'].values.astype(float)
        volume = df['volume'].values.astype(float)
        n = len(close)
        for i in range(60, n-5):
            score = 0
            m20 = (close[i]/close[i-20]-1)*100 if i>=20 else 0
            m5 = (close[i]/close[i-5]-1)*100 if i>=5 else 0
            if m5>5: score+=8
            elif m5>2: score+=4
            elif m5<-5: score-=8
            if m20>30: score-=5
            elif m20>15: score+=3
            elif m20>5: score+=6
            elif m20<-20: score+=8
            # MA
            ma5=np.mean(close[i-4:i+1]); ma20=np.mean(close[i-19:i+1])
            if ma5>ma20: score+=12
            else: score-=12
            # RSI
            if i>=14:
                d=np.diff(close[i-14:i+1])
                g=sum(d[d>0]) if any(d>0) else 0
                l=abs(sum(d[d<0])) if any(d<0) else 1e-10
                rsi=100-100/(1+g/l)
                if rsi<=25: score+=15
                elif rsi>=80: score-=12
            pred = 1 if score > 0 else 0
            actual = 1 if close[i+5] > close[i] else 0
            rule_acc += 1 if pred==actual else 0
            rule_n += 1
    
    print(f"  rule_engine: acc={rule_acc/rule_n*100:.2f}% ({rule_n} preds)")
    
    rf1 = grid_search_round(codes, [
        {'name': 'RF_depth=None', 'n_estimators': 100, 'max_depth': None, 'min_samples_leaf': 1, 'max_features': 'sqrt'},
        {'name': 'RF_depth=5', 'n_estimators': 100, 'max_depth': 5, 'min_samples_leaf': 5, 'max_features': 'sqrt'},
        {'name': 'RF_depth=3', 'n_estimators': 100, 'max_depth': 3, 'min_samples_leaf': 10, 'max_features': 'sqrt'},
    ], 'R1')
    
    # ═══ Round 2: 深度+树数 ═══
    print(f"\n{'='*40}")
    print("Round 2: 深度+树数网格搜索")
    print(f"{'='*40}")
    
    rf2 = grid_search_round(codes, [
        {'name': 'd3_n100', 'n_estimators': 100, 'max_depth': 3, 'min_samples_leaf': 10, 'max_features': 'sqrt'},
        {'name': 'd3_n200', 'n_estimators': 200, 'max_depth': 3, 'min_samples_leaf': 10, 'max_features': 'sqrt'},
        {'name': 'd4_n200', 'n_estimators': 200, 'max_depth': 4, 'min_samples_leaf': 15, 'max_features': 'sqrt'},
        {'name': 'd5_n150', 'n_estimators': 150, 'max_depth': 5, 'min_samples_leaf': 20, 'max_features': 'sqrt'},
        {'name': 'd2_n300', 'n_estimators': 300, 'max_depth': 2, 'min_samples_leaf': 5, 'max_features': 'sqrt'},
    ], 'R2')
    
    # ═══ Round 3: 叶子+特征 ═══
    print(f"\n{'='*40}")
    print("Round 3: 正则化参数")
    print(f"{'='*40}")
    
    rf3 = grid_search_round(codes, [
        {'name': 'leaf10', 'n_estimators': 200, 'max_depth': 4, 'min_samples_leaf': 10, 'max_features': 'sqrt'},
        {'name': 'leaf20', 'n_estimators': 200, 'max_depth': 4, 'min_samples_leaf': 20, 'max_features': 'sqrt'},
        {'name': 'leaf30', 'n_estimators': 200, 'max_depth': 4, 'min_samples_leaf': 30, 'max_features': 'sqrt'},
        {'name': 'feat_log2', 'n_estimators': 200, 'max_depth': 4, 'min_samples_leaf': 20, 'max_features': 'log2'},
        {'name': 'feat_0.5', 'n_estimators': 200, 'max_depth': 4, 'min_samples_leaf': 20, 'max_features': 0.5},
    ], 'R3')
    
    # ═══ Round 4: 最佳组合微调 ═══
    all_results = base_params + rf1 + rf2 + rf3
    all_results.sort(key=lambda x: x['accuracy'], reverse=True)
    best = all_results[0]
    
    print(f"\n{'='*40}")
    print(f"Round 4: 最优参数微调 (best={best['params']['name']} {best['accuracy']}%)")
    print(f"{'='*40}")
    
    bp = best['params']
    rf4 = grid_search_round(codes, [
        {'name': 'best_n+50', 'n_estimators': min(bp.get('n_estimators',200)+50, 500), 'max_depth': bp['max_depth'], 'min_samples_leaf': bp['min_samples_leaf'], 'max_features': bp['max_features']},
        {'name': 'best_n-50', 'n_estimators': max(bp.get('n_estimators',200)-50, 50), 'max_depth': bp['max_depth'], 'min_samples_leaf': bp['min_samples_leaf'], 'max_features': bp['max_features']},
        {'name': 'best_leaf+10', 'n_estimators': bp['n_estimators'], 'max_depth': bp['max_depth'], 'min_samples_leaf': bp['min_samples_leaf']+10, 'max_features': bp['max_features']},
    ], 'R4', n_stocks=200)
    
    # ═══ Final: 最优参数 1000股验证 ═══
    all_final = all_results + rf4
    all_final.sort(key=lambda x: x['accuracy'], reverse=True)
    champion = all_final[0]
    
    print(f"\n{'='*60}")
    print(f"最优参数: {champion['params']['name']}")
    print(f"200股准确率: {champion['accuracy']}%")
    print(f"{'='*60}")
    
    codes_full = get_codes(1000, min_days=250)
    print(f"\n最终验证: 1000只股票...")
    
    final_correct = 0
    final_total = 0
    final_proba_up = []
    final_proba_down = []
    
    cp = champion['params']
    for si, code in enumerate(codes_full):
        df = load_df(code)
        if df is None: continue
        X, y = build_features_labels(df)
        if X is None: continue
        
        acc, n, preds = walk_forward_backtest(df, X, y, {
            'n_estimators': cp['n_estimators'],
            'max_depth': cp['max_depth'],
            'min_samples_leaf': cp['min_samples_leaf'],
            'max_features': cp['max_features'],
        })
        
        if acc is not None:
            final_correct += acc * n / 100
            final_total += n
            
            for p in preds:
                if p['proba_up'] is not None:
                    if p['actual'] == 1:
                        final_proba_up.append(p['proba_up'])
                    else:
                        final_proba_down.append(p['proba_up'])
        
        if (si+1) % 200 == 0:
            print(f"  [{si+1}/{len(codes_full)}] acc={final_correct/final_total*100:.2f}%")
    
    final_acc = final_correct / final_total * 100 if final_total > 0 else 0
    print(f"\n{'='*60}")
    print(f"最终结果 (1000股)")
    print(f"{'='*60}")
    print(f"准确率: {final_acc:.2f}%")
    print(f"预测数: {final_total}")
    print(f"规则引擎基线: {rule_acc/rule_n*100:.2f}%")
    print(f"提升: {final_acc - rule_acc/rule_n*100:+.2f}pp")
    
    if final_proba_up:
        print(f"看涨信号平均概率(实际涨): {np.mean(final_proba_up):.1f}%")
    if final_proba_down:
        print(f"看涨信号平均概率(实际跌): {np.mean(final_proba_down):.1f}%")
    
    # Save
    out = {
        'champion': {'name': cp['name'], 'params': {k:v for k,v in cp.items() if k!='name'}, 'accuracy_200': champion['accuracy']},
        'final_accuracy_1000': round(final_acc, 2),
        'rule_baseline': round(rule_acc/rule_n*100, 2),
        'improvement_pp': round(final_acc - rule_acc/rule_n*100, 2),
        'total_predictions': final_total,
        'all_rounds': [{'name': r['params']['name'], 'acc': r['accuracy'], 'preds': r['predictions']} for r in all_final],
    }
    
    path = os.path.join(os.path.dirname(__file__), 'eval_result', 'rf_tuning_results.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=2)
    print(f"\n报告已保存: {path}")

if __name__ == '__main__':
    main()
