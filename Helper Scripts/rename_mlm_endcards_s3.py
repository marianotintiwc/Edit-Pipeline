#!/usr/bin/env python3
"""
Rename MLM Endcards in S3 to match Google Drive names and update CSV
"""

import boto3
import csv
import os
from urllib.parse import quote

# S3 Configuration
BUCKET = "meli-ai.filmmaker"
PREFIX = "MP-Users/Assets/"
REGION = "us-east-2"

# Mapping: old name -> new name (from Google Drive)
RENAME_MAP = {
    "MLM- 60_de_regalo Endcard.mov": "MLM- Ahorra con tu cuenta digital .mov",
    "MLM- cuenta_pro Endcard.mov": "MLM- Activa tus ganancias.mov",
    "MLM- participa_por_50_000 Endcard.mov": "MLM- Participa ahora.mov",
    "MLM- prestamo_personal Endcard.mov": "MLM- Solicita tu Préstamo Personal.mov",
    "MLM- tarjeta_de_credito Endcard.mov": "MLM- Pide tu Tarjeta de Crédito.mov",
    "MLM- tarjeta_debit_mastercard Endcard.mov": "MLM- Pide tu Tarjeta ahora.mov",
}

# Product to new endcard name mapping
PRODUCT_ENDCARD_MAP = {
    "60_de_regalo": "MLM- Ahorra con tu cuenta digital .mov",
    "paga_tus_servicios": "MLM- Ahorra con tu cuenta digital .mov",  # Same as 60_de_regalo
    "cuenta_pro": "MLM- Activa tus ganancias.mov",
    "participa_por_50_000": "MLM- Participa ahora.mov",
    "participa_por_50_00o": "MLM- Participa ahora.mov",  # Typo variant
    "prestamo_personal": "MLM- Solicita tu Préstamo Personal.mov",
    "tarjeta_de_credito": "MLM- Pide tu Tarjeta de Crédito.mov",
    "tarjeta_debit_mastercard": "MLM- Pide tu Tarjeta ahora.mov",
}

def rename_files_in_s3():
    """Rename files in S3 by copying to new name and deleting old"""
    s3 = boto3.client('s3', region_name=REGION)
    
    print("=" * 60)
    print("RENAMING MLM ENDCARDS IN S3")
    print("=" * 60)
    
    for old_name, new_name in RENAME_MAP.items():
        old_key = f"{PREFIX}{old_name}"
        new_key = f"{PREFIX}{new_name}"
        
        try:
            # Check if old file exists
            s3.head_object(Bucket=BUCKET, Key=old_key)
            
            # Copy to new name
            print(f"\n📋 Copying: {old_name}")
            print(f"   → {new_name}")
            
            s3.copy_object(
                Bucket=BUCKET,
                CopySource={'Bucket': BUCKET, 'Key': old_key},
                Key=new_key
            )
            
            # Delete old file
            s3.delete_object(Bucket=BUCKET, Key=old_key)
            print(f"   ✓ Renamed successfully")
            
        except s3.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                print(f"\n⚠️  File not found: {old_name}")
                # Check if new name already exists
                try:
                    s3.head_object(Bucket=BUCKET, Key=new_key)
                    print(f"   ✓ New name already exists: {new_name}")
                except:
                    print(f"   ✗ Neither old nor new name exists")
            else:
                print(f"\n❌ Error with {old_name}: {e}")

def update_csv():
    """Update the CSV with correct S3 URLs for endcards"""
    csv_path = "/Users/marianotinti/Desktop/UGC EDITOR/Edit-Pipeline/Files for Edit - MLM_Approved.s3.csv"
    
    print("\n" + "=" * 60)
    print("UPDATING CSV WITH NEW ENDCARD URLS")
    print("=" * 60)
    
    rows = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)
    
    updated_count = 0
    for row in rows:
        product = row['Product']
        
        # Find the correct endcard for this product
        endcard_name = PRODUCT_ENDCARD_MAP.get(product)
        if endcard_name:
            # URL encode the filename (spaces become %20)
            encoded_name = quote(endcard_name)
            new_url = f"https://s3.us-east-2.amazonaws.com/{BUCKET}/{PREFIX}{encoded_name}"
            row['ENDCARD S3'] = new_url
            updated_count += 1
    
    # Write updated CSV
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"✓ Updated {updated_count} rows")
    print(f"✓ Saved to: {csv_path}")
    
    # Show the mapping
    print("\nENDCARD URL MAPPING:")
    for product, endcard in PRODUCT_ENDCARD_MAP.items():
        encoded = quote(endcard)
        print(f"  {product} → {endcard}")

def verify_s3_files():
    """List the renamed files to verify"""
    s3 = boto3.client('s3', region_name=REGION)
    
    print("\n" + "=" * 60)
    print("VERIFYING S3 FILES")
    print("=" * 60)
    
    response = s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX)
    
    mlm_files = []
    for obj in response.get('Contents', []):
        key = obj['Key']
        filename = key.replace(PREFIX, '')
        if 'MLM' in filename:
            size_mb = obj['Size'] / (1024 * 1024)
            mlm_files.append((filename, size_mb))
    
    print("\nMLM files in S3:")
    for filename, size in sorted(mlm_files):
        print(f"  {filename} ({size:.1f} MB)")

if __name__ == "__main__":
    rename_files_in_s3()
    update_csv()
    verify_s3_files()
