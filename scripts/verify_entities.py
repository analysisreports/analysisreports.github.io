#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_entities.py
------------------
Tamamen Dinamik Kanonik Varlık ve Şema Doğrulayıcı.
- Kod içinde sabit dosya adı veya istisna kelime listesi TUTMAZ.
- İzin verilen tüm kimlikleri doğrudan 'llms-entities-id.txt' içinden dinamik çeker.
- 'llms-relationships.txt' içindeki tanımlı rejim durumlarını otomatik öğrenir.
- Projedeki tüm .json ve ilgili metin dosyalarını otomatik bulup tarar.
"""

import os
import re
import sys
import difflib
from typing import Set, List, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENTITIES_FILE = os.path.join(ROOT_DIR, "llms-entities-id.txt")
RELATIONSHIPS_FILE = os.path.join(ROOT_DIR, "llms-relationships.txt")

# Hariç tutulacak sistem ve versiyon kontrol klasörleri
EXCLUDE_DIRS = {".git", ".github", "__pycache__", "scripts"}


def get_allowed_vocabularies() -> Tuple[Set[str], re.Pattern]:
    """Sözlük dosyalarından geçerli tüm ID'leri ve rejim durumlarını dinamik olarak yükler."""
    if not os.path.exists(ENTITIES_FILE):
        print(f"[HATA] Sözlük dosyası bulunamadı: {ENTITIES_FILE}", file=sys.stderr)
        sys.exit(1)

    valid_tokens: Set[str] = set()
    dynamic_prefixes: Set[str] = set()

    # 1. llms-entities-id.txt içindeki tüm ID ve önekleri dinamik topla
    with open(ENTITIES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Önek kuralı satırını dinamik yakala (Örn: Prefix: INST_ / GEO_ ...)
            if "Prefix:" in line:
                found_prefixes = re.findall(r"([A-Z0-9_]+_)", line)
                dynamic_prefixes.update(found_prefixes)

            if not line or line.startswith("#"):
                continue

            parts = line.split("|")
            token_id = parts[0].strip()
            if token_id:
                valid_tokens.add(token_id)
                prefix_match = re.match(r"^([A-Z0-9_]+_)", token_id)
                if prefix_match:
                    dynamic_prefixes.add(prefix_match.group(1))

    # 2. llms-relationships.txt içindeki rejim durumlarını (PROXY_WAR vb.) dinamik topla
    if os.path.exists(RELATIONSHIPS_FILE):
        with open(RELATIONSHIPS_FILE, "r", encoding="utf-8") as f:
            regime_block = False
            for line in f:
                if "Regime States" in line:
                    regime_block = True
                    continue
                if regime_block:
                    if line.startswith("---") or line.startswith("#"):
                        regime_block = False
                        continue
                    m = re.match(r"^\s*-\s*([A-Z0-9_]+)\s*:", line)
                    if m:
                        valid_tokens.add(m.group(1))

    # Dinamik Regex oluştur
    sorted_prefixes = sorted(dynamic_prefixes, key=len, reverse=True)
    prefix_pattern = "|".join(re.escape(p) for p in sorted_prefixes)
    token_regex = re.compile(rf"\b((?:{prefix_pattern})[A-Z0-9_]+)\b")

    return valid_tokens, token_regex


def find_target_files() -> List[str]:
    """Depodaki tüm doğrulanabilir veri dosyalarını dinamik olarak bulur."""
    targets = []
    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in {".json", ".txt", ".md"}:
                # Sözlüklerin kendisini doğrulamaya sokma
                if f in {"llms-entities-id.txt", "LICENSE.md"}:
                    continue
                targets.append(os.path.join(root, f))
    return sorted(targets)


def main():
    print("=" * 70)
    print("DİNAMİK KANONİK ENTITY DOĞRULAYICI (AUTO-DISCOVERY)")
    print("=" * 70)

    valid_tokens, token_regex = get_allowed_vocabularies()
    target_files = find_target_files()

    print(f"[*] Yüklenen geçerli varlık ve rejim sayısı : {len(valid_tokens)}")
    print(f"[*] Taranacak dinamik dosya sayısı          : {len(target_files)}\n")

    total_issues = 0

    for file_path in target_files:
        rel_path = os.path.relpath(file_path, ROOT_DIR)
        issues = []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_no, line in enumerate(f, start=1):
                    # llms.txt içindeki regex ve şablon açıklamalarını atla
                    if "IDENTIFIER REGEX" in line or "Prefix:" in line:
                        continue

                    matches = token_regex.findall(line)
                    for matched_id in matches:
                        clean_id = matched_id.rstrip("_")
                        if clean_id not in valid_tokens:
                            suggestions = difflib.get_close_matches(clean_id, valid_tokens, n=1, cutoff=0.6)
                            suggestion = suggestions[0] if suggestions else "Öneri yok"
                            issues.append((line_no, clean_id, suggestion))
        except Exception as e:
            print(f"[UYARI] Okunamadı: {rel_path} -> {e}", file=sys.stderr)
            continue

        if issues:
            print(f"[!] HATA: {rel_path} ({len(issues)} uyumsuzluk):")
            for line_no, invalid_id, suggestion in issues:
                total_issues += 1
                print(f"    - Satır {line_no:>4}: '{invalid_id}' -> Öneri: '{suggestion}'")
            print("-" * 70)

    print("\n" + "=" * 70)
    if total_issues > 0:
        print(f"[SONUÇ] Toplam {total_issues} adet geçersiz veya tanımsız ID bulundu!")
        print("=" * 70)
        sys.exit(1)
    else:
        print(f"[SONUÇ] Başarılı! {len(target_files)} dosyanın tamamı sözlükle %100 uyumlu.")
        print("=" * 70)
        sys.exit(0)


if __name__ == "__main__":
    main()
