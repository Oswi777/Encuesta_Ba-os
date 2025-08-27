import qrcode, os

BASE = os.environ.get("QR_BASE_URL", "http://localhost:8000/qr")
os.makedirs("qr_out", exist_ok=True)

def make_one(id_bano: str):
    url = f"{BASE}?r={id_bano}"
    img = qrcode.make(url)
    img.save(f"qr_out/{id_bano}.png")

for idb in ["B-A1-H1","B-A1-M1","B-A2-H2"]:
    make_one(idb)

print("QRs generados en ./qr_out")
