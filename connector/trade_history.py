"""Rebuild completed bot positions from MT5 deals, including partial exits."""
from collections import defaultdict
import math
from datetime import datetime,timezone

def empty_history(status='not_loaded',detail=''):
    return dict(status=status,detail=detail,trades=[],stats=dict(count=0,net=0.0,win_rate=0.0,expectancy=0.0,average_win=0.0,average_loss=0.0,profit_factor=None),excluded_mixed=0,excluded_incomplete=0,open_positions=0,window_days=90)

def aggregate_deals(deals,magic,open_ids=(),since=0):
    result=empty_history('ok')
    # Ticket identity, not timestamp, prevents double counting identical imports.
    unique={int(d.ticket):d for d in deals}
    groups=defaultdict(list)
    for d in unique.values():
        if getattr(d,'position_id',0) and d.type in (0,1):groups[int(d.position_id)].append(d)
    live={int(x) for x in open_ids}
    trades=[]
    for pid,rows in groups.items():
        rows.sort(key=lambda d:(getattr(d,'time_msc',d.time*1000),int(d.ticket)))
        if not any(d.magic==magic for d in rows):continue
        ins=[d for d in rows if d.entry==0]
        outs=[d for d in rows if d.entry in (1,3)]
        if any(d.entry==2 for d in rows) or any(d.magic!=magic for d in ins):
            result['excluded_mixed']+=1;continue
        if not ins:
            result['excluded_incomplete']+=1;continue
        vin=sum(d.volume for d in ins);vout=sum(d.volume for d in outs)
        if pid in live or vout<vin-1e-7:
            result['open_positions']+=1;continue
        if not outs or vin<=0 or abs(vout-vin)>1e-7:
            result['excluded_incomplete']+=1;continue
        if max(d.time for d in outs)<since:continue
        if any(not math.isfinite(float(getattr(d,k,0))) for d in rows for k in ('price','volume','profit','commission','swap','fee')):
            result['excluded_incomplete']+=1;continue
        parts={key:sum(float(getattr(d,key,0)) for d in rows) for key in ('profit','commission','swap','fee')}
        trade=dict(id=str(pid),symbol=ins[0].symbol,side='BUY' if ins[0].type==0 else 'SELL',volume=vin,
                   opened=min(d.time for d in ins),closed=max(d.time for d in outs),
                   entry=sum(d.price*d.volume for d in ins)/vin,exit=sum(d.price*d.volume for d in outs)/vout,
                   exit_deals=len(outs),reason={4:'SL',5:'TP',6:'STOP_OUT'}.get(getattr(outs[-1],'reason',0),'AUTRE'),
                   **parts,net=sum(parts.values()))
        trades.append(trade)
    trades.sort(key=lambda t:(t['closed'],t['id']))
    win=[t['net'] for t in trades if t['net']>0];loss=[t['net'] for t in trades if t['net']<0]
    net=sum(t['net'] for t in trades);n=len(trades)
    by_side={side:dict(count=sum(t['side']==side for t in trades),net=sum(t['net'] for t in trades if t['side']==side)) for side in ('BUY','SELL')}
    by_day={}
    for t in trades:
        key=datetime.fromtimestamp(t['closed'],timezone.utc).date().isoformat()
        item=by_day.setdefault(key,dict(count=0,net=0.0));item['count']+=1;item['net']+=t['net']
    result.update(trades=trades,stats=dict(count=n,net=net,win_rate=len(win)/n if n else 0,
        expectancy=net/n if n else 0,average_win=sum(win)/len(win) if win else 0,
        average_loss=sum(loss)/len(loss) if loss else 0,profit_factor=sum(win)/-sum(loss) if loss else None,by_side=by_side,by_day=by_day))
    return result
