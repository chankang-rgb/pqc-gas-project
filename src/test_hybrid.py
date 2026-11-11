import os
from hybrid import *

data = os.urandom(100 * 1024)   # 100KB 가상 신원 데이터

ek, dk = ML_KEM_768.keygen()
p = pq_encrypt(ek, data)
assert pq_decrypt(dk, *p) == data

priv = X25519PrivateKey.generate()
c = classic_encrypt(priv.public_key(), data)
assert classic_decrypt(priv, *c) == data

print("Additional byte for key delivery — PQ:", len(p[0]), "/ Classic:", len(c[0]))