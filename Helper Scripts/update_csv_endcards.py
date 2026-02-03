#!/usr/bin/env python3
"""Update CSV with correct endcard URLs"""
import csv
from urllib.parse import quote

csv_path = "/Users/marianotinti/Desktop/UGC EDITOR/Edit-Pipeline/Files for Edit - MLM_Approved.s3.csv"
BUCKET = "meli-ai.filmmaker"
PREFIX = "MP-Users/Assets/"

PRODUCT_ENDCARD_MAP = {
    "60_de_regalo": "MLM- Ahorra con tu cuenta digital .mov",
    "paga_tus_servicios": "MLM- Ahorra con tu cuenta digital .mov",
    "cuenta_pro": "MLM- Activa tus ganancias.mov",
    "participa_por_50_000": "MLM- Participa ahora.mov",
    "participa_por_50_00o": "MLM- Participa ahora.mov",
    "prestamo_personal": "MLM- Solicita tu Préstamo Personal.mov",
    "tarjeta_de_credito": "MLM- Pide tu Tarjeta de Crédito.mov",
    "tarjeta_debit_mastercard": "MLM- Pide tu Tarjeta ahora.mov",
}

rows = []
with open(csv_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        rows.append(row)

for row in rows:
    product = row["Product"]
    endcard_name = PRODUCT_ENDCARD_MAP.get(product)
    if endcard_name:
        encoded_name = quote(endcard_name)
        row["ENDCARD S3"] = f"https://s3.us-east-2.amazonaws.com/{BUCKET}/{PREFIX}{encoded_name}"

with open(csv_path, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Updated {len(rows)} rows in CSV")
print()
print("ENDCARD MAPPING:")
for p, e in PRODUCT_ENDCARD_MAP.items():
    print(f"  {p} -> {e}")
