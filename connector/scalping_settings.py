"""Validated, per-account settings for the experimental demo scalper."""
import math

DEFAULTS=dict(risk=.005,daily_loss=.02,positions=3,cooldown=60,pivot=2,
              penetration=.10,stop_distance=1.0,max_spread=.50,
              break_even=True,be_trigger=.50,use_sessions=True,
              start1=0,end1=5,start2=13,end2=17)

def validate_settings(values):
    if not isinstance(values,dict) or set(values)-set(DEFAULTS):
        raise ValueError('Réglages inconnus ou invalides.')
    result={**DEFAULTS,**values}
    ints={'positions':(1,3),'cooldown':(0,3600),'pivot':(1,10),
          'start1':(0,23),'end1':(0,24),'start2':(0,23),'end2':(0,24)}
    floats={'risk':(.0001,.01),'daily_loss':(.0001,.03),'penetration':(.01,10),
            'stop_distance':(.05,100),'max_spread':(.01,10),'be_trigger':(.1,.9)}
    for k in ('break_even','use_sessions'):
        if type(result[k]) is not bool:raise ValueError('Choix oui/non requis : '+k)
    for k,(low,high) in ints.items():
        if type(result[k]) is not int or not low<=result[k]<=high:
            raise ValueError('Entier hors limites : '+k)
    for k,(low,high) in floats.items():
        v=result[k]
        if type(v) not in (int,float) or not math.isfinite(v) or not low<=v<=high:
            raise ValueError('Valeur hors limites : '+k)
    if result['risk']>result['daily_loss']:raise ValueError('Le risque par série doit rester inférieur ou égal à la limite quotidienne.')
    if result['use_sessions'] and (result['start1']==result['end1'] or result['start2']==result['end2']):
        raise ValueError('Le début et la fin d’une plage horaire doivent être différents.')
    return result

def session_open(hour,settings):
    if not settings['use_sessions']:return True
    for start,end in ((settings['start1'],settings['end1']),(settings['start2'],settings['end2'])):
        if start<end and start<=hour<end:return True
        if start>end and (hour>=start or hour<end):return True
    return False
