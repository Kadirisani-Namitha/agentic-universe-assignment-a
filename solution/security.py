from __future__ import annotations
import hashlib,hmac
from cryptography.fernet import Fernet
from .config import get_pii_key
class PIIProtector:
 def __init__(self,key:bytes|None=None):
  self.key=key or get_pii_key(); self.fernet=Fernet(self.key); self.hash_key=hashlib.sha256(self.key+b":phone-match").digest()
 def encrypt(self,value:str)->bytes:return self.fernet.encrypt(value.encode())
 def decrypt(self,value:bytes)->str:return self.fernet.decrypt(value).decode()
 def phone_hash(self,phone:str)->str:return hmac.new(self.hash_key,phone.encode(),hashlib.sha256).hexdigest()
 @staticmethod
 def mask_phone(phone:str)->str:return "+91******"+phone[-4:]
