import pytest
from datetime import timedelta
from solution.normalization import normalize_phone,parse_date,parse_decimal,parse_timestamp,ValidationError
@pytest.mark.parametrize("raw",["9876543210","+91 98765 43210","91-98765-43210","(+91) 9876543210"])
def test_valid_phone_formats(raw):assert normalize_phone(raw)=="+919876543210"
@pytest.mark.parametrize("raw",["123456789","5123456789","022-2345-6789","N/A"])
def test_invalid_phones(raw):
 with pytest.raises(ValidationError):normalize_phone(raw)
@pytest.mark.parametrize("raw",["2026-12-01","01/12/2026","01-12-2026","01-Dec-2026"])
def test_dates(raw):assert parse_date(raw)=="2026-12-01"
def test_impossible_date():
 with pytest.raises(ValidationError):parse_date("31/02/2026")
@pytest.mark.parametrize("raw,expected",[("₹12,345","12345.00"),("Rs. 1,250.5","1250.50"),("INR 99","99.00")])
def test_decimals(raw,expected):assert parse_decimal(raw)==expected
def test_negative_decimal():
 with pytest.raises(ValidationError):parse_decimal("-1")
def test_naive_ts_is_ist():assert parse_timestamp("2026-10-03 10:01:00").utcoffset()==timedelta(hours=5,minutes=30)
