#!/usr/bin/env python3
"""
Script pour générer le fichier latest.yml nécessaire aux mises à jour automatiques
"""
import hashlib
import os
import json
from datetime import datetime

def calculate_sha512(file_path):
    """Calcule le hash SHA512 d'un fichier"""
    sha512_hash = hashlib.sha512()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha512_hash.update(byte_block)
    return sha512_hash.hexdigest()

def get_file_size(file_path):
    """Retourne la taille du fichier en bytes"""
    return os.path.getsize(file_path)

def generate_latest_yml(exe_path, version, output_path="latest.yml"):
    """Génère le fichier latest.yml"""
    
    if not os.path.exists(exe_path):
        raise FileNotFoundError(f"Le fichier {exe_path} n'existe pas")
    
    # Calcul des métadonnées
    file_size = get_file_size(exe_path)
    sha512 = calculate_sha512(exe_path)
    filename = os.path.basename(exe_path)
    
    # Génération du contenu YAML
    yaml_content = f"""version: {version}
files:
  - url: {filename}
    sha512: {sha512}
    size: {file_size}
path: {filename}
sha512: {sha512}
releaseDate: '{datetime.utcnow().isoformat()}Z'
"""
    
    # Écriture du fichier
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(yaml_content)
    
    print(f"✅ Fichier {output_path} généré avec succès!")
    print(f"   Version: {version}")
    print(f"   Fichier: {filename}")
    print(f"   Taille: {file_size:,} bytes")
    print(f"   SHA512: {sha512[:16]}...")

if __name__ == "__main__":
    # Configuration
    VERSION = "3.6.1"  # À adapter selon votre version
    EXE_PATH = "dist/B2PC.exe"
    
    try:
        generate_latest_yml(EXE_PATH, VERSION)
    except Exception as e:
        print(f"❌ Erreur: {e}")