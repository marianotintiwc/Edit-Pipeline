#!/usr/bin/env python3
"""Update MLM CSV with correct S3 URLs for B-rolls and Endcards."""
import csv
import os
from urllib.parse import quote

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_CSV = os.path.join(BASE_DIR, "Files for Edit - MLM_Approved.csv")
OUTPUT_CSV = os.path.join(BASE_DIR, "Files for Edit - MLM_Approved.s3.csv")

S3_BASE = "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Users/Assets"

# B-roll mapping: product -> S3 filename (exact names from S3)
BROLL_MAPPING = {
    "60_de_regalo": "60-PESOS-REGALO-MLM.mov",
    "cuenta_pro": "GANANCIAS-DIARIAS-MLM.mov",
    "paga_tus_servicios": "INGRESO-APP-MLM.mov",
    "participa_por_50_000": "INGRESO-APP-MLM.mov",
    "participa_por_50_00o": "INGRESO-APP-MLM.mov",
    "prestamo_personal": "INGRESO-APP-MLM.mov",
    "tarjeta_de_credito": "TARJETA-DE-CREDITO-MLM.mp4",
    "tarjeta_debit_mastercard": "TARJETA-DEBIT-MASTERCARD-MLM.mov",
}

# Endcard mapping: product -> S3 filename (exact names from S3)
ENDCARD_MAPPING = {
    "60_de_regalo": "MLM- 60_de_regalo Endcard.mov",
    "cuenta_pro": "MLM- cuenta_pro Endcard.mov",
    "paga_tus_servicios": "MLM- 60_de_regalo Endcard.mov",
    "participa_por_50_000": "MLM- participa_por_50_000 Endcard.mov",
    "participa_por_50_00o": "MLM- participa_por_50_000 Endcard.mov",
    "prestamo_personal": "MLM- prestamo_personal Endcard.mov",
    "tarjeta_de_credito": "MLM- tarjeta_de_credito Endcard.mov",
    "tarjeta_debit_mastercard": "MLM- tarjeta_debit_mastercard Endcard.mov",
}


def get_s3_url(filename):
    """Build S3 URL with proper URL encoding."""
    encoded = quote(filename, safe="-_.~")
    return f"{S3_BASE}/{encoded}"


def main():
    print("=" * 60)
    print("Updating MLM CSV with S3 URLs")
    print("=" * 60)
    
    # Read CSV
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames)
    
    # Add S3 columns if not present
    if "BROLL S3" not in fieldnames:
        fieldnames.append("BROLL S3")
    if "ENDCARD S3" not in fieldnames:
        fieldnames.append("ENDCARD S3")
    
    print(f"\nProcessing {len(rows)} rows...")
    
    # Update rows
    for row in rows:
        product = row["Product"]
        
        # Set B-roll S3 URL
        broll_file = BROLL_MAPPING.get(product)
        if broll_file:
            row["BROLL S3"] = get_s3_url(broll_file)
        else:
            print(f"  WARNING: No B-roll mapping for: {product}")
        
        # Set Endcard S3 URL
        endcard_file = ENDCARD_MAPPING.get(product)
        if endcard_file:
            row["ENDCARD S3"] = get_s3_url(endcard_file)
        else:
            print(f"  WARNING: No Endcard mapping for: {product}")
    
    # Write updated CSV
    with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"\n✓ Updated {len(rows)} rows")
    print(f"✓ Saved to: {OUTPUT_CSV}")
    
    # Show mapping summary
    print("\n" + "=" * 60)
    print("B-ROLL MAPPING")
    print("=" * 60)
    for product, filename in BROLL_MAPPING.items():
        url = get_s3_url(filename)
        print(f"  {product}:")
        print(f"    -> {url}")
    
    print("\n" + "=" * 60)
    print("ENDCARD MAPPING")
    print("=" * 60)
    for product, filename in ENDCARD_MAPPING.items():
        url = get_s3_url(filename)
        print(f"  {product}:")
        print(f"    -> {url}")


if __name__ == "__main__":
    main()
