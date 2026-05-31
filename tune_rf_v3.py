#!/usr/bin/env python3
"""RF调参 — 内存优化版: 预加载80只股票, 3轮调参, 最后1000股验证"""
import sys, os, json, random, time, gc
from datetime import datetime
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

sys.path.insert(0, os.path.dirname(__file__))
from models import SessionLocal

def preload_stocks(codes):
    """一次性加载所有股票数据到内存"""
    db = SessionLocal()
    try:
        data = {}
        for code in codes:
            df = pd.read_sql_query(
                "SELECT date,open,high,low,close,volume FROM backtest_data WHERE code=:code ORDER BY date",
                db.bind, params={'code': code})
            if len(df) < 80: continue
            for c in ['close','high','low','open','volume']:
                df[c] = df[c].astype(float)
            data[code] = df
        return data
    finally:
        db.close()

def build_XY_from_arrays(c, h, l, o, v):
    """从numpy数组构建特征 — 纯numpy, 比pandas快10x"""
    n = len(c)
    if n < 65: return None, None
    X_rows = []
    for i in range(60, n-5):
        f = np.zeros(14)
        # ret 1/3/5/10/20
        f[0] = (c[i]/c[i-1]-1)*100 if i>=1 else 0
        f[1] = (c[i]/c[i-3]-1)*100 if i>=3 else 0
        f[2] = (c[i]/c[i-5]-1)*100 if i>=5 else 0
        f[3] = (c[i]/c[i-10]-1)*100 if i>=10 else 0
        # vol 20d
        rets = np.diff(c[i-20:i+1])/c[i-20:i]
        f[4] = np.std(rets)*100*np.sqrt(252)
        # ma dev 5/20
        f[5] = (c[i]/np.mean(c[max(0,i-4):i+1])-1)*100
        f[6] = (c[i]/np.mean(c[max(0,i-19):i+1])-1)*100
        # RSI
        d = np.diff(c[max(0,i-14):i+1])
        g = np.sum(d[d>0]) if np.any(d>0) else 0
        ll = abs(np.sum(d[d<0])) if np.any(d<0) else 1e-10
        f[7] = 100 - 100/(1+g/ll)
        # vol ratio
        av = np.mean(v[max(0,i-20):i]) if i>=20 else v[i]
        f[8] = v[i]/av if av>0 else 1.0
        # boll pos
        m20 = np.mean(c[max(0,i-19):i+1]); s20 = np.std(c[max(0,i-19):i+1])
        f[9] = (c[i]-(m20-2*s20))/(4*s20)*100 if s20>0 else 50
        # dd 20d
        pk = np.max(c[max(0,i-19):i+1])
        f[10] = (pk-c[i])/pk*100 if pk>0 else 0
        # amplitude
        f[11] = (h[i]-l[i])/o[i]*100 if o[i]>0 else 0
        # consec up/down
        up=0; down=0
        for j in range(i, max(i-5,0), -1):
            if c[j]>c[j-1]: up+=1
            else: break
        for j in range(i, max(i-5,0), -1):
            if c[j]<c[j-1]: down+=1
            else: break
        f[12] = up; f[13] = down
        X_rows.append(f)
    
    X = np.array(X_rows, dtype=np.float32)
    X = np.nan_to_num(X, 0)
    y = np.array([1 if c[i+5]>c[i] else 0 for i in range(60, n-5)], dtype=np.int32)
    return X, y

def walk_forward_score(X, y, params, retrain=40):
    """Walk-forward: 返回准确率"""
    n = len(X)
    if n < 60: return 0, 0
    correct = 0; total = 0
    for ts in range(40, n, retrain):
        te = min(ts+retrain, n)
        rf = RandomForestClassifier(**params, n_jobs=-1)
        rf.fit(X[:ts], y[:ts])
        preds = rf.predict(X[ts:te])
        correct += np.sum(preds == y[ts:te])
        total += len(preds)
    return correct, total

def test_param_set(stock_data, params, label, n_stocks=30):
    """在一组参数上测试"""
    tc = 0; tp = 0
    codes = list(stock_data.keys())[:n_stocks]
    for code in codes:
        df = stock_data[code]
        c=df['close'].values; h=df['high'].values; l=df['low'].values
        o=df['open'].values; v=df['volume'].values
        X, y = build_XY_from_arrays(c,h,l,o,v)
        if X is None: continue
        corr, tot = walk_forward_score(X, y, params)
        tc += corr; tp += tot
    acc = round(tc/tp*100, 2) if tp>0 else 0
    print(f"  {label}: {acc}% ({tp} preds)")
    return {'label': label, 'acc': acc, 'preds': tp, 'params': params}

def main():
    print("="*50)
    print("RF Walk-Forward 调参 (内存优化)")
    print("="*50)
    
    # Pre-load
    with open('/Users/wgfu/work/a-stock-trading/eval_result/fast_codes.json') as f:
        codes = json.load(f)
    print(f"加载 {len(codes)} 只股票...")
    t0 = time.time()
    stock_data = preload_stocks(codes)
    print(f"  加载完成: {len(stock_data)}只 ({time.time()-t0:.0f}s)")
    
    tune_codes = dict(list(stock_data.items())[:30])
    
    all_results = []
    
    # R1: 5组参数
    print("\n--- R1: 深度+树数 ---")
    t0 = time.time()
    for label, params in [
        ('d2_n100', {'n_estimators':100,'max_depth':2,'min_samples_leaf':20,'max_features':'sqrt','class_weight':'balanced'}),
        ('d3_n100', {'n_estimators':100,'max_depth':3,'min_samples_leaf':15,'max_features':'sqrt','class_weight':'balanced'}),
        ('d4_n150', {'n_estimators':150,'max_depth':4,'min_samples_leaf':20,'max_features':'sqrt','class_weight':'balanced'}),
        ('d5_n200', {'n_estimators':200,'max_depth':5,'min_samples_leaf':25,'max_features':'sqrt','class_weight':'balanced'}),
        ('dNone_n100', {'n_estimators':100,'max_depth':None,'min_samples_leaf':10,'max_features':'sqrt','class_weight':'balanced'}),
    ]:
        r = test_param_set(tune_codes, params, label, 30)
        all_results.append(r)
    print(f"  R1耗时: {time.time()-t0:.0f}s")
    
    # R2: 正则化
    print("\n--- R2: 正则化 ---")
    t0 = time.time()
    for label, params in [
        ('leaf10', {'n_estimators':150,'max_depth':4,'min_samples_leaf':10,'max_features':'sqrt','class_weight':'balanced'}),
        ('leaf25', {'n_estimators':150,'max_depth':4,'min_samples_leaf':25,'max_features':'sqrt','class_weight':'balanced'}),
        ('leaf40', {'n_estimators':150,'max_depth':4,'min_samples_leaf':40,'max_features':'sqrt','class_weight':'balanced'}),
        ('log2', {'n_estimators':150,'max_depth':4,'min_samples_leaf':20,'max_features':'log2','class_weight':'balanced'}),
        ('f0.4', {'n_estimators':150,'max_depth':4,'min_samples_leaf':20,'max_features':0.4,'class_weight':'balanced'}),
    ]:
        r = test_param_set(tune_codes, params, label, 30)
        all_results.append(r)
    print(f"  R2耗时: {time.time()-t0:.0f}s")
    
    all_results.sort(key=lambda x: x['acc'], reverse=True)
    best = all_results[0]
    bp = best['params']
    
    # R3: 微调
    print(f"\n--- R3: 微调 (best={best['label']} {best['acc']}%) ---")
    t0 = time.time()
    for label, params in [
        ('n+50', {**bp, 'n_estimators': min(bp['n_estimators']+50, 400)}),
        ('n-30', {**bp, 'n_estimators': max(bp['n_estimators']-30, 50)}),
        ('l+10', {**bp, 'min_samples_leaf': bp['min_samples_leaf']+10}),
        ('l-5', {**bp, 'min_samples_leaf': max(bp['min_samples_leaf']-5, 5)}),
    ]:
        r = test_param_set(tune_codes, params, label, 30)
        all_results.append(r)
    print(f"  R3耗时: {time.time()-t0:.0f}s")
    
    all_results.sort(key=lambda x: x['acc'], reverse=True)
    champion = all_results[0]
    cp = champion['params']
    
    # Final: all 80 stocks
    print(f"\n{'='*50}")
    print(f"最终: 80股, {champion['label']} {champion['acc']}%")
    print(f"{'='*50}")
    t0 = time.time()
    tc=0; tp=0
    for code in list(stock_data.keys())[:80]:
        df = stock_data[code]
        X, y = build_XY_from_arrays(df['close'].values, df['high'].values, df['low'].values, df['open'].values, df['volume'].values)
        if X is None: continue
        c, t = walk_forward_score(X, y, cp)
        tc+=c; tp+=t
    
    final_acc = round(tc/tp*100, 2)
    print(f"80股准确率: {final_acc}% ({tp} preds, {time.time()-t0:.0f}s)")
    
    # Also run rule baseline on same 80
    print(f"\n规则引擎基线 (同80股):")
    rc=0; rp=0
    for code in list(stock_data.keys())[:80]:
        df = stock_data[code]
        c=df['close'].values; n=len(c)
        for i in range(60, n-5):
            score=0
            m5=(c[i]/c[i-5]-1)*100 if i>=5 else 0
            m20=(c[i]/c[i-20]-1)*100 if i>=20 else 0
            if m5>5: score+=8
            elif m5>2: score+=4
            elif m5<-5: score-=8
            if m20>30: score-=5
            elif m20>15: score+=3
            elif m20>5: score+=6
            elif m20<-20: score+=8
            if i>=4 and i>=19:
                if np.mean(c[i-4:i+1])>np.mean(c[i-19:i+1]): score+=12
                else: score-=12
            if i>=14:
                d=np.diff(c[i-14:i+1])
                g=np.sum(d[d>0]) if np.any(d>0) else 0
                ll=abs(np.sum(d[d<0])) if np.any(d<0) else 1e-10
                rsi=100-100/(1+g/ll)
                if rsi<=25: score+=15
                elif rsi>=80: score-=12
            pred=1 if score>0 else 0
            actual=1 if c[i+5]>c[i] else 0
            rc+=1 if pred==actual else 0; rp+=1
    
    rule_acc = round(rc/rp*100, 2)
    print(f"  规则基线: {rule_acc}%")
    print(f"  RF提升: {final_acc - rule_acc:+.1f}pp")
    
    # Save
    out = {'rf_acc': final_acc, 'rule_acc': rule_acc, 'improvement': round(final_acc-rule_acc,2),
           'champion': champion['label'], 'params': {k:v for k,v in cp.items()},
           'rounds': [{'label':r['label'],'acc':r['acc']} for r in all_results]}
    with open(os.path.join(os.path.dirname(__file__), 'eval_result', 'rf_results.json'), 'w') as f:
        json.dump(out, f, indent=2)
    print(f"\n结果已保存")

if __name__ == '__main__':
    main()
