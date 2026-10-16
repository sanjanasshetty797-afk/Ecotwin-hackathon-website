"""Fake ESP32: pushes rising fill levels to the API.  python simulator.py BIN02 demo-key-BIN02"""
import random, sys, time, httpx
code, key = sys.argv[1], sys.argv[2]
level = 20.0
while level < 100:
    level = min(100, level + random.uniform(2, 6))
    r = httpx.post("http://localhost:8000/devices/readings", json={"fill_level": round(level, 1)},
                   headers={"X-Device-Key": key})
    print(code, round(level, 1), r.json())
    time.sleep(2)
