import os
from kyber_py.ml_kem import ML_KEM_768
from Crypto.Cipher import AES
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

# ---- 공통: AES-GCM (데이터를 실제로 잠그는 부분) ----
def aes_encrypt(key, data):
    nonce = os.urandom(12)
    c = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ct, tag = c.encrypt_and_digest(data)
    return nonce, ct, tag

def aes_decrypt(key, nonce, ct, tag):
    return AES.new(key, AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ct, tag)

# ---- 양자 내성 방식: ML-KEM + AES ----
def pq_encrypt(ek, data):
    key, kem_ct = ML_KEM_768.encaps(ek)      # 열쇠 + 캡슐 생성
    return (kem_ct, *aes_encrypt(key, data))

def pq_decrypt(dk, kem_ct, nonce, ct, tag):
    key = ML_KEM_768.decaps(dk, kem_ct)      # 캡슐 열어서 열쇠 획득
    return aes_decrypt(key, nonce, ct, tag)

# ---- 기존 방식: X25519 + AES ----
def derive(shared):
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"did-demo").derive(shared)

def classic_encrypt(receiver_pub, data):
    eph = X25519PrivateKey.generate()        # 일회용 키
    key = derive(eph.exchange(receiver_pub))
    return (eph.public_key().public_bytes_raw(), *aes_encrypt(key, data))

def classic_decrypt(receiver_priv, eph_pub, nonce, ct, tag):
    key = derive(receiver_priv.exchange(X25519PublicKey.from_public_bytes(eph_pub)))
    return aes_decrypt(key, nonce, ct, tag)