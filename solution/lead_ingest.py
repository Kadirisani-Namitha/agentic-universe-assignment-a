from __future__ import annotations
import csv,json
from pathlib import Path
from .normalization import ValidationError,normalise_header,normalize_phone,parse_date,parse_decimal

def load_schema(schema_dir:Path,workflow_id:str):
 p=schema_dir/f"{workflow_id}.json"
 if not p.exists():raise ValueError(f"No schema for workflow: {workflow_id}")
 return json.loads(p.read_text(encoding="utf-8"))
def _convert(field,raw):
 value=str(raw or "").strip()
 if not value:return None
 kind=field["type"]
 if kind=="string":return value
 if kind=="phone":return normalize_phone(value)
 if kind=="date":return parse_date(value)
 if kind=="decimal":return parse_decimal(value)
 if kind=="enum":
  candidate=value.lower()
  if candidate not in {str(x).lower() for x in field.get("values",[])}:raise ValidationError("invalid_enum")
  return candidate
 raise ValueError(f"Unsupported type: {kind}")
def ingest_lead_file(conn,path:Path,workflow_id:str,batch_id:str,schema_dir:Path,protector):
 schema=load_schema(schema_dir,workflow_id); fields=schema["fields"]
 counts={"rows_total":0,"rows_rejected":0,"duplicates":0,"warnings":0}; rejects=[]
 with path.open("r",newline="",encoding="utf-8-sig") as f:
  reader=csv.DictReader(f)
  aliases={}
  for field in fields:
   aliases[normalise_header(field["name"])]=field["name"]
   for alias in field.get("aliases",[]):aliases[normalise_header(alias)]=field["name"]
  mapping={}
  for header in reader.fieldnames or []:
   target=aliases.get(normalise_header(header))
   if target and target not in mapping:mapping[target]=header
  row_no=0
  for row in reader:
   if all(not str(v or "").strip() for v in row.values()):continue
   row_no+=1; counts["rows_total"]+=1; source={target:row.get(src) for target,src in mapping.items()}
   values={f["name"]:None for f in fields}; reason=None; warnings=0
   for field in fields:
    name=field["name"]; raw=source.get(name); blank=raw is None or not str(raw).strip()
    if blank:
     if field.get("required"):reason=f"missing_required:{name}";break
     continue
    try:values[name]=_convert(field,raw)
    except ValidationError:
     if field["type"]=="phone":reason="invalid_phone";break
     if field.get("required"):reason=f"invalid_required:{name}";break
     values[name]=None;warnings+=1
   if reason:
    counts["rows_rejected"]+=1;rejects.append((workflow_id,batch_id,row_no,reason));continue
   phone_hash=protector.phone_hash(values["phone"])
   ref=next((values[f["name"]] for f in fields if f.get("reference")),None)
   non_pii={f["name"]:values.get(f["name"]) for f in fields if not f.get("pii") and f["name"]!="phone"}
   old=conn.execute("SELECT id,fields_json,external_ref FROM leads WHERE workflow_id=? AND phone_hash=?",(workflow_id,phone_hash)).fetchone()
   if old:
    counts["duplicates"]+=1; merged=json.loads(old["fields_json"])
    for k,v in non_pii.items():
     if v is not None:merged[k]=v
    # Defaults are applied after merging; applying them here is equivalent because
    # a later non-null duplicate overwrites the default.
    for field in fields:
     if not field.get("pii") and field["name"] != "phone" and merged.get(field["name"]) is None and "default" in field:
      merged[field["name"]] = field["default"]
    conn.execute("UPDATE leads SET fields_json=?,external_ref=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(json.dumps(merged,sort_keys=True),ref or old["external_ref"],old["id"]))
    conn.execute("UPDATE leads SET customer_name_ciphertext=? WHERE id=?",(protector.encrypt(values["customer_name"]),old["id"]))
   else:
    for field in fields:
     if not field.get("pii") and field["name"] != "phone" and non_pii.get(field["name"]) is None and "default" in field:
      non_pii[field["name"]] = field["default"]
    conn.execute("INSERT INTO leads(workflow_id,phone_hash,phone_ciphertext,customer_name_ciphertext,external_ref,batch_id,fields_json) VALUES(?,?,?,?,?,?,?)",(workflow_id,phone_hash,protector.encrypt(values["phone"]),protector.encrypt(values["customer_name"]),ref,batch_id,json.dumps(non_pii,sort_keys=True)))
   counts["warnings"]+=warnings
 conn.executemany("INSERT OR IGNORE INTO lead_rejections(workflow_id,batch_id,row_number,reason) VALUES(?,?,?,?)",rejects)
 return counts
