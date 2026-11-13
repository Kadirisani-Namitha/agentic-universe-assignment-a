from solution.security import PIIProtector
def test_encryption_and_hmac():
 p=PIIProtector(key=b"MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=");cipher=p.encrypt("+919876543210")
 assert cipher!=b"+919876543210";assert p.decrypt(cipher)=="+919876543210";assert p.phone_hash("+919876543210")==p.phone_hash("+919876543210");assert p.mask_phone("+919876543210")=="+91******3210"

def test_ciphertext_is_randomised():
    p = PIIProtector(key=b"MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
    assert p.encrypt("same") != p.encrypt("same")
