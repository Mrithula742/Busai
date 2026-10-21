"""Small explicit grammar. Never calls or claims an LLM."""
import re
from datetime import datetime,timedelta
from .ai_journey_service import IST

PRIORITIES=[('less_crowd',r'low(?:est)? crowd|less crowd|least crowded'),('fewer_transfers',r'fewer transfers|less transfers|direct(?: only)?'),('most_reliable',r'most reliable|reliability'),('faster',r'fastest|quickest|faster')]


def interpret(text,stops,context_time=None,now=None):
    now=(now or datetime.now(IST)).astimezone(IST)
    aliases={}
    for i,stop in enumerate(stops):
        for name in [stop['stop_id'],stop['stop_name'],f'Stop {chr(65+i)}']:aliases[name.casefold()]=stop['stop_id']
    def resolve(raw):return aliases.get(raw.strip(' .,!?').casefold()) if raw else None
    def phrase(raw):
        return re.split(r'\s+(?:with|at|after|before|by|tomorrow|today|and|please|low|fewer)\b',raw,flags=re.I)[0].strip(' .,!?')
    origin_match=re.search(r'\bfrom\s+(.+?)\s+to\s+',text,re.I)
    destination_match=re.search(r'\b(?:to|towards)\s+(.+)',text,re.I)
    origin_raw=origin_match.group(1).strip() if origin_match else None
    dest_raw=phrase(destination_match.group(1)) if destination_match else None
    origin,destination=resolve(origin_raw),resolve(dest_raw)
    missing=[];warnings=[]
    if not origin:missing.append('origin')
    if not destination:missing.append('destination')
    if origin_raw and not origin:warnings.append(f'Unknown origin: {origin_raw}')
    if dest_raw and not destination:warnings.append(f'Unknown destination: {dest_raw}')
    priorities=sorted([(m.start(),key) for key,pattern in PRIORITIES if (m:=re.search(pattern,text,re.I))],key=lambda p:p[0])
    preferences=[p[1] for p in priorities]
    departure=context_time.astimezone(IST) if context_time else None
    if re.search(r'\bnow\b',text,re.I):departure=now
    time_match=re.search(r'\b(at|after|before|by)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b',text,re.I)
    deadline=None
    if time_match:
        kind,hour,minute,period=time_match.groups();hour=int(hour);minute=int(minute or 0)
        if minute>59 or (period and not 1<=hour<=12) or (not period and hour>23):warnings.append('Invalid clock time');missing.append('departure_time')
        else:
            if period:hour=hour%12+(12 if period.casefold()=='pm' else 0)
            day=(departure or now).date()
            if re.search(r'\btomorrow\b',text,re.I):day=now.date()+timedelta(days=1)
            elif re.search(r'\btoday\b',text,re.I):day=now.date()
            parsed=datetime.combine(day,datetime.min.time(),tzinfo=IST).replace(hour=hour,minute=minute)
            if kind.casefold() in ('before','by'):deadline=parsed
            else:departure=parsed
    elif re.search(r'\btomorrow\b',text,re.I) and departure:departure=departure.replace(year=(now+timedelta(days=1)).year,month=(now+timedelta(days=1)).month,day=(now+timedelta(days=1)).day)
    if departure is None:missing.append('departure_time')
    if deadline and departure and deadline<departure:warnings.append('Arrival deadline is earlier than departure');missing.append('departure_time')
    if re.search(r'\b(?:around|about|between|until)\b',text,re.I):warnings.append('Approximate times/time ranges are unsupported; confirm exact departure in the planner')
    wait=re.search(r'\b(?:wait|waiting)\s+(?:no more than |up to )?(\d+)\s*(?:min|minute)',text,re.I)
    if wait and int(wait.group(1))>180:warnings.append('Maximum wait must be at most 180 minutes');missing.append('max_wait_minutes')
    payload=dict(origin=origin,destination=destination,departure_time=departure.isoformat() if departure else None,preference=preferences[0] if preferences else 'faster',secondary_preferences=preferences[1:],max_transfers=0 if re.search(r'\bdirect(?: only)?\b',text,re.I) else 2)
    if deadline:payload['arrival_deadline']=deadline.isoformat()
    if wait and int(wait.group(1))<=180:payload['max_wait_minutes']=int(wait.group(1))
    return dict(parser='RULE_BASED',parameters=payload,missing_fields=list(dict.fromkeys(missing)),warnings=warnings,ready=not missing,aliases={f'Stop {chr(65+i)}':s['stop_name'] for i,s in enumerate(stops)},message='Confirm these interpreted parameters before planning.' if not missing else 'Please supply '+', '.join(dict.fromkeys(missing))+'.')
