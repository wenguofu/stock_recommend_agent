#!/usr/bin/env python3
"""随机森林调参 — 精简版: 50股 × 3轮 × 最后1000股验证"""
import sys, os, json, random, sqlite3, time
from datetime import datetime
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
DB = os.path.join(os.path.dirname(__file__), 'database.db')

def get_codes(n=200, min_d=250):
    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT code FROM backtest_data GROUP BY code HAVING COUNT(*)>=? ORDER BY COUNT(*) DESC", (min_d,)).fetchall()
    conn.close()
    codes = [r[0] for r in rows]
    random.seed(42)
    return random.sample(codes, min(n, len(codes)))

def load_df(code):
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("SELECT date,open,high,low,close,volume FROM backtest_data WHERE code=? ORDER BY date", conn, params=(code,))
    conn.close()
    if len(df) < 80: return None
    for c in ['close','high','low','open','volume']: df[c] = df[c].astype(float)
    return df

def build_XY(df):
    c = df['close'].values; h = df['high'].values; l = df['low'].values
    o = df['open'].values; v = df['volume'].values; n = len(c)
    if n < 65: return None, None
    rows = []
    for i in range(60, n-5):
        f = {}
        for p in [1,3,5,10,20]: f[f'r{p}'] = (c[i]/c[i-p]-1)*100 if i>=p else 0
        rets = np.diff(c[i-20:i+1])/c[i-20:i]
        f['vol'] = float(np.std(rets)*100*np.sqrt(252))
        for p in [5,10,20]:
            if i>=p: f[f'ma{p}'] = (c[i]/np.mean(c[i-p+1:i+1])-1)*100
        if i>=14:
            d=np.diff(c[i-14:i+1])
            g=np.sum(d[d>0]) if np.any(d>0) else 0
            ll=abs(np.sum(d[d<0])) if np.any(d<0) else 1e-10
            f['rsi']=100-100/(1+g/ll)
        av=np.mean(v[i-20:i]) if i>=20 else v[i]
        f['vr']=v[i]/av if av>0 else 1.0
        if i>=20:
            m=np.mean(c[i-19:i+1]); s=np.std(c[i-19:i+1])
            if s>0: f['boll']=(c[i]-(m-2*s))/(4*s)*100
            f['dd']=(np.max(c[i-19:i+1])-c[i])/np.max(c[i-19:i+1])*100
        f['amp']=(h[i]-l[i])/o[i]*100
        up=0; down=0
        for j in range(i,max(i-5,0),-1):
            if c[j]>c[j-1]: up+=1
            else: break
        for j in range(i,max(i-5,0),-1):
            if c[j]<c[j-1]: down+=1
            else: break
        f['cup']=up; f['cdn']=down
        rows.append(f)
    X = pd.DataFrame(rows).fillna(0)
    y = np.array([1 if c[i+5]>c[i] else 0 for i in range(60,n-5)])
    return X, y

def walk_forward(X, y, params, retrain=30):
    from sklearn.ensemble import RandomForestClassifier
    n = len(X); correct = 0; total = 0
    for ts in range(30, n, retrain):
        te = min(ts+retrain, n)
        if ts < 30: continue
        rf = RandomForestClassifier(**params, random_state=42, n_jobs=-1)
        rf.fit(X.iloc[:ts], y[:ts])
        preds = rf.predict(X.iloc[ts:te])
        correct += np.sum(preds == y[ts:te])
        total += len(preds)
    return correct/total*100 if total>0 else 0, total

def test_params(codes, param_sets, name, n_stocks=50):
    print(f"\n--- {name} ---")
    results = []
    for label, params in param_sets:
        tc = 0; tp = 0; t0 = time.time()
        for code in codes[:n_stocks]:
            df = load_df(code)
            if df is None: continue
            X, y = build_XY(df)
            if X is None: continue
            acc, n = walk_forward(X, y, params)
            if acc is not None: tc += acc*n/100; tp += n
        avg = round(tc/tp*100, 2) if tp>0 else 0
        elapsed = time.time()-t0
        print(f"  {label}: {avg}%  ({tp} preds, {elapsed:.0f}s)")
        results.append({'label': label, 'acc': avg, 'preds': tp, 'params': params})
    return results

def main():
    print("="*50)
    print("随机森林 Walk-Forward 调参")
    print("="*50)
    
    codes50 = get_codes(200, 250)
    print(f"调参池: 50只")
    
    all_r = []
    
    # R1: depth + estimators
    r1 = test_params(codes50, [
        ('d2_n100', {'n_estimators':100,'max_depth':2,'min_samples_leaf':20,'max_features':'sqrt','class_weight':'balanced'}),
        ('d3_n100', {'n_estimators':100,'max_depth':3,'min_samples_leaf':15,'max_features':'sqrt','class_weight':'balanced'}),
        ('d4_n150', {'n_estimators':150,'max_depth':4,'min_samples_leaf':20,'max_features':'sqrt','class_weight':'balanced'}),
        ('d5_n200', {'n_estimators':200,'max_depth':5,'min_samples_leaf':25,'max_features':'sqrt','class_weight':'balanced'}),
        ('dNone_n100', {'n_estimators':100,'max_depth':None,'min_samples_leaf':10,'max_features':'sqrt','class_weight':'balanced'}),
    ], 'R1: 深度+树数')
    all_r.extend(r1)
    
    # R2: regularization
    r2 = test_params(codes50, [
        ('leaf10', {'n_estimators':150,'max_depth':4,'min_samples_leaf':10,'max_features':'sqrt','class_weight':'balanced'}),
        ('leaf25', {'n_estimators':150,'max_depth':4,'min_samples_leaf':25,'max_features':'sqrt','class_weight':'balanced'}),
        ('leaf40', {'n_estimators':150,'max_depth':4,'min_samples_leaf':40,'max_features':'sqrt','class_weight':'balanced'}),
        ('log2', {'n_estimators':150,'max_depth':4,'min_samples_leaf':20,'max_features':'log2','class_weight':'balanced'}),
        ('f0.4', {'n_estimators':150,'max_depth':4,'min_samples_leaf':20,'max_features':0.4,'class_weight':'balanced'}),
    ], 'R2: 正则化')
    all_r.extend(r2)
    
    # Pick best
    all_r.sort(key=lambda x: x['acc'], reverse=True)
    best = all_r[0]
    print(f"\n最优: {best['label']} {best['acc']}%")
    
    # R3: fine-tune around best
    bp = best['params']
    r3 = test_params(codes50, [
        ('best_n+50', {**bp, 'n_estimators': min(bp['n_estimators']+50, 400)}),
        ('best_n-30', {**bp, 'n_estimators': max(bp['n_estimators']-30, 50)}),
        ('best_leaf+10', {**bp, 'min_samples_leaf': bp['min_samples_leaf']+10}),
        ('best_leaf-5', {**bp, 'min_samples_leaf': max(bp['min_samples_leaf']-5, 5)}),
    ], 'R3: 微调')
    all_r.extend(r3)
    
    all_r.sort(key=lambda x: x['acc'], reverse=True)
    champion = all_r[0]
    cp = champion['params']
    
    # Final: 1000 stocks
    print(f"\n{'='*50}")
    print(f"最终验证: 1000股, {champion['label']}")
    print(f"{'='*50}")
    
    codes1k = get_codes(1000, 250)
    tc = 0; tp = 0
    for i, code in enumerate(codes1k):
        df = load_df(code)
        if df is None: continue
        X, y = build_XY(df)
        if X is None: continue
        acc, n = walk_forward(X, y, cp)
        if acc is not None: tc += acc*n/100; tp += n
        if (i+1)%200==0: print(f"  [{i+1}/1000] {tc/tp*100:.2f}%")
    
    final_acc = round(tc/tp*100, 2)
    print(f"\n最终准确率: {final_acc}% ({tp} preds)")
    print(f"最优参数: {champion['label']}")
    print(f"提升: {final_acc - 49:.1f}pp vs 规则基线~49%")
    
    # Also do timing+PF backtest
    print(f"\n--- 择时+PF (RF信号) ---")
    trades = []
    for code in codes1k:
        df = load_df(code)
        if df is None: continue
        X, y = build_XY(df)
        if X is None: continue
        from sklearn.ensemble import RandomForestClassifier
        n = len(X)
        for ts in range(60, n, 40):
            if ts < 60: continue
            rf = RandomForestClassifier(**cp, random_state=42, n_jobs=-1)
            rf.fit(X.iloc[:ts], y[:ts])
            te = min(ts+40, n)
            proba = rf.predict_proba(X.iloc[ts:te])
            for j in range(len(proba)):
                up_p = proba[j][1]
                idx = 60 + ts + j
                if idx + 5 >= len(df): continue
                # Only trade high conviction
                if up_p < 0.58: continue
                entry = df['close'].values[idx]
                exit_px = entry; stopped=False
                for k in range(1,6):
                    if idx+k>=len(df): break
                    if df['low'].values[idx+k] <= entry*0.92:
                        exit_px=entry*0.92; stopped=True; break
                    elif k==5: exit_px=df['close'].values[idx+k]
                pnl = round((exit_px/entry-1)*100, 2)
                trades.append({'pnl':pnl, 'stopped':stopped, 'prob':up_p})
    
    if trades:
        pnls = [t['pnl'] for t in trades]
        wins = [p for p in pnls if p>0]
        losses = [p for p in pnls if p<0]
        pf = sum(wins)/abs(sum(losses)) if losses else 999
        print(f"  RF交易: {len(trades)}笔  PF={pf:.2f}  胜率={len(wins)/len(trades)*100:.1f}%  均收益={np.mean(pnls):.2f}%")

if __name__ == '__main__':
    main()
