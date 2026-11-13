from __future__ import annotations
import re
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
IST=timezone(timedelta(hours=5,minutes=30))
class ValidationError(ValueError): pass
def normalise_header(value:str)->str: return re.sub(r"[_\s]+"," ",(value or "").strip().lower())
def normalize_phone(value)->str:
 if value is None: raise ValidationError("invalid_phone")
 digits=re.sub(r"\D","",str(value))
 if len(digits)==12 and digits.startswith("91"): digits=digits[2:]
 elif len(digits)==11 and digits.startswith("0"): digits=digits[1:]
 if len(digits)!=10 or digits[0] not in "6789": raise ValidationError("invalid_phone")
 return "+91"+digits
def parse_date(value)->str:
 s=str(value or "").strip()
 for fmt in ("%Y-%m-%d","%d/%m/%Y","%d-%m-%Y","%d-%b-%Y"):
  try:return datetime.strptime(s,fmt).date().isoformat()
  except ValueError:pass
 raise ValidationError("invalid_date")
def parse_decimal(value)->str:
 s=str(value or "").strip(); s=re.sub(r"^(?:₹|rs\.?|inr)\s*","",s,flags=re.I).replace(",","").strip()
 try:n=Decimal(s)
 except InvalidOperation as e:raise ValidationError("invalid_decimal") from e
 if not n.is_finite() or n<0:raise ValidationError("invalid_decimal")
 return str(n.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))
def parse_timestamp(value)->datetime:
 s=str(value or "").strip()
 try: dt=datetime.fromisoformat(s[:-1]+"+00:00" if s.endswith("Z") else s)
 except ValueError:
  try:dt=datetime.strptime(s,"%Y-%m-%d %H:%M:%S")
  except ValueError as e:raise ValidationError("invalid_timestamp") from e
 if dt.tzinfo is None:dt=dt.replace(tzinfo=IST)
 return dt.astimezone(IST)
def iso_ist(dt:datetime)->str:return dt.astimezone(IST).isoformat(timespec="seconds")
