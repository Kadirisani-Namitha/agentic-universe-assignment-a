from __future__ import annotations
import csv,json
from collections import defaultdict
from pathlib import Path
from .db import connect
from .security import PIIProtector

def _catalogue(schema_dir):
 out={}
 with (schema_dir/"dispositions.csv").open(encoding="utf-8",newline="") as f:
  for r in csv.DictReader(f):out[(r["workflow_id"],r["code"])]=(r["is_terminal"].lower()=="true",r["is_success"].lower()=="true")
 return out
def _write(path,headers,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=headers,lineterminator="\n");w.writeheader();w.writerows(rows)
def generate_reports(out_dir:Path,db_path:Path|None=None,schema_dir:Path|None=None):
 out_dir=Path(out_dir);schema_dir=schema_dir or Path(__file__).resolve().parents[1]/"assignment-a-data"/"schemas";protect=PIIProtector();conn=connect(db_path)
 try:
  leads=conn.execute("SELECT * FROM leads ORDER BY workflow_id,external_ref").fetchall(); events=conn.execute("SELECT * FROM interaction_events ORDER BY workflow_id,occurred_at_ist,event_id").fetchall();catalogue=_catalogue(schema_dir)
  by_id={(l["workflow_id"],l["phone_hash"]):l for l in leads}; groups=defaultdict(list)
  for e in events:groups[(e["workflow_id"],e["call_id"])].append(e)
  # A call is anchored by its linked call.initiated event. Overrides have no
  # phone, so they inherit this link through call_id.
  call_to_lead={}
  for (wf,cid),evs in groups.items():
   initiated=sorted((e for e in evs if e["event_type"]=="call.initiated"),key=lambda e:(e["occurred_at_ist"] or "",e["event_id"]))
   if initiated and initiated[0]["phone_hash"] and (wf,initiated[0]["phone_hash"]) in by_id:
    call_to_lead[(wf,cid)]=by_id[(wf,initiated[0]["phone_hash"])]["id"]
  # Count orphan events at event level, not just calls: an event without a phone
  # can still link through its call_id if another event in that call has a phone.
  orphan_ids=set(); unknown_ids=set(); calls_by_lead=defaultdict(list)
  for e in events:
   wf=e["workflow_id"]
   linked=bool(e["phone_hash"] and (wf,e["phone_hash"]) in by_id)
   if not linked and e["event_type"]=="disposition.override" and e["call_id"] is not None:
    linked=(wf,e["call_id"]) in call_to_lead
   if not linked:orphan_ids.add(e["event_id"])
   if linked and e["event_type"].startswith("disposition."):
    code=json.loads(e["payload_json"]).get("disposition_code")
    if code and (wf,code) not in catalogue:unknown_ids.add(e["event_id"])
  for (wf,cid),evs in groups.items():
   lead_id=call_to_lead.get((wf,cid))
   if lead_id is None:continue
   init=sorted((e for e in evs if e["event_type"]=="call.initiated" and e["phone_hash"] and (wf,e["phone_hash"]) in by_id),key=lambda e:(e["occurred_at_ist"] or "",e["event_id"]))
   if not init:continue
   disp=[]
   for e in evs:
    if e["event_type"] not in ("disposition.set","disposition.override"):continue
    code=json.loads(e["payload_json"]).get("disposition_code")
    if code and (wf,code) in catalogue:
     disp.append((e["event_type"],e["occurred_at_ist"] or "",code,e["event_id"]))
   overrides=[d for d in disp if d[0]=="disposition.override"]
   sets=[d for d in disp if d[0]=="disposition.set"]
   eff=max(overrides,key=lambda d:(d[1],d[3])) if overrides else (max(sets,key=lambda d:(d[1],d[3])) if sets else None)
   calls_by_lead[lead_id].append({"workflow":wf,"call_id":cid,"initiated":init[0]["occurred_at_ist"] or "","connected":any(e["event_type"]=="call.connected" for e in evs),"telephony_failed":any(e["event_type"]=="call.telephony_failed" for e in evs),"disposition":eff[2] if eff else None})
  batch_counts=defaultdict(lambda:defaultdict(int));daily=defaultdict(lambda:{"total":0,"connected":0,"success":set()});lead_rows=[]
  for l in leads:
   calls=sorted(calls_by_lead[l["id"]],key=lambda c:(c["initiated"],c["call_id"]));n=len(calls);connected=sum(c["connected"] for c in calls)
   if n==0:bucket="yet_to_reach_out"
   elif any(c["disposition"] and catalogue[(l["workflow_id"],c["disposition"])][0] for c in calls):bucket="completed"
   elif all(c["telephony_failed"] for c in calls):bucket="in_progress_telephony_failed"
   else:bucket="in_progress_dialed"
   batch_counts[(l["workflow_id"],l["batch_id"])][bucket]+=1
   for c in calls:
    day=c["initiated"][:10]
    if not day:continue
    d=daily[(l["workflow_id"],day)];d["total"]+=1;d["connected"]+=int(c["connected"])
    if c["disposition"] and catalogue[(l["workflow_id"],c["disposition"])][1]:d["success"].add(l["id"])
   latest_disp=next((c["disposition"] for c in reversed(calls) if c["disposition"]),"")
   phone=protect.decrypt(l["phone_ciphertext"])
   lead_rows.append({"workflow_id":l["workflow_id"],"external_ref":l["external_ref"],"batch_id":l["batch_id"],"phone_masked":protect.mask_phone(phone),"bucket":bucket,"total_calls":n,"connected_calls":connected,"last_call_at":calls[-1]["initiated"] if calls else "","current_disposition":latest_disp,"ever_success":"true" if any(c["disposition"] and catalogue[(l["workflow_id"],c["disposition"])][1] for c in calls) else "false"})
  batch_rows=[]
  for (wf,batch),counts in sorted(batch_counts.items()):batch_rows.append({"workflow_id":wf,"batch_id":batch,"total_leads":sum(counts.values()),"yet_to_reach_out":counts["yet_to_reach_out"],"in_progress_telephony_failed":counts["in_progress_telephony_failed"],"in_progress_dialed":counts["in_progress_dialed"],"completed":counts["completed"]})
  daily_rows=[]
  for (wf,day),d in sorted(daily.items()):daily_rows.append({"workflow_id":wf,"date":day,"total_calls":d["total"],"connected_calls":d["connected"],"connectivity_rate":f'{d["connected"]/d["total"]:.4f}',"success_leads":len(d["success"])})
  lead_rows.sort(key=lambda r:(r["workflow_id"],r["external_ref"] or ""))
  rejections=[dict(r) for r in conn.execute("SELECT workflow_id,batch_id,row_number,reason FROM lead_rejections ORDER BY workflow_id,batch_id,row_number")]
  q={r["key"]:r["value"] for r in conn.execute("SELECT key,value FROM data_quality_counters")}; reasons=defaultdict(int)
  for r in rejections:reasons[r["reason"]]+=1
  quality={"lead_rows_total":q.get("lead_rows_total",0),"lead_rows_rejected":q.get("lead_rows_rejected",0),"rejections_by_reason":dict(sorted(reasons.items())),"duplicate_lead_rows_merged":q.get("duplicate_lead_rows_merged",0),"field_warnings":q.get("field_warnings",0),"events_total":q.get("events_total",0),"malformed_events":q.get("malformed_events",0),"duplicate_events_dropped":q.get("duplicate_events_dropped",0),"orphan_events":len(orphan_ids),"unknown_disposition_events":len(unknown_ids)}
  _write(out_dir/"batch_summary.csv",["workflow_id","batch_id","total_leads","yet_to_reach_out","in_progress_telephony_failed","in_progress_dialed","completed"],batch_rows)
  _write(out_dir/"daily_overview.csv",["workflow_id","date","total_calls","connected_calls","connectivity_rate","success_leads"],daily_rows)
  _write(out_dir/"lead_report.csv",["workflow_id","external_ref","batch_id","phone_masked","bucket","total_calls","connected_calls","last_call_at","current_disposition","ever_success"],lead_rows)
  _write(out_dir/"rejections.csv",["workflow_id","batch_id","row_number","reason"],rejections)
  (out_dir/"data_quality.json").write_text(json.dumps(quality,indent=2)+"\n",encoding="utf-8")
  return quality
 finally:conn.close()
