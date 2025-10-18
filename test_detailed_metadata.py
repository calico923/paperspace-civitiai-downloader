#!/usr/bin/env python3
"""
詳細メタデータ抽出テストスクリプト

拡張フィールド付きの詳細メタデータを抽出してCSV出力をテストする
"""

import asyncio
import json
import os
import sys
import csv
from pathlib import Path

# 現在のディレクトリをPythonパスに追加
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from model_metadata_scanner import ModelMetadataScanner

async def test_detailed_metadata():
    """詳細メタデータ抽出テスト"""
    
    print("🚀 詳細メタデータ抽出テスト開始！")
    
    # テスト対象ファイル
    test_file = "/Users/kuniaki-k/Code/paperspace/civitai_downloader/downloads/checkpoints/waiIllustriousSDXL_v150.safetensors"
    
    # 設定ファイルからAPIキーを読み込み
    config_path = "config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        api_key = config.get('civitai_api_key', 'YOUR_API_KEY_HERE')
        
        if api_key == 'YOUR_API_KEY_HERE':
            print("❌ APIキーが設定されていません")
            return
            
    except Exception as e:
        print(f"❌ 設定読み込みエラー: {e}")
        return
    
    # スキャナーを初期化してテスト実行
    async with ModelMetadataScanner(api_key=api_key) as scanner:
        print(f"\n🔍 メタデータ抽出開始...")
        
        try:
            # 単一ファイルをスキャン
            metadata = await scanner.scan_model_file(test_file)
            
            if metadata and metadata.download_urls:
                print(f"✅ メタデータ抽出成功！")
                
                # 詳細メタデータを抽出
                detailed_entries = scanner.extract_detailed_metadata_for_csv([metadata])
                
                if detailed_entries:
                    print(f"\n📋 詳細メタデータ ({len(detailed_entries)}個):")
                    for i, entry in enumerate(detailed_entries, 1):
                        print(f"  {i}. {entry['model_name']} ({entry['creator']})")
                        print(f"     📁 ファイル: {entry['filename']}")
                        print(f"     🏷️  タイプ: {entry['model_type']}")
                        print(f"     🎯 ベースモデル: {entry['base_model']}")
                        print(f"     🔗 URL: {entry['url']}")
                        print(f"     📥 ダウンロードURL: {entry['download_url']}")
                        print(f"     📊 サイズ: {entry['file_size']}")
                        print(f"     🔐 SHA256: {entry['sha256'][:16]}...")
                        print(f"     ⚠️  NSFW: {entry['nsfw_level']}")
                        print(f"     🏷️  タグ: {entry['tags']}")
                        print(f"     📝 説明: {entry['description'][:100]}..." if entry['description'] else "     📝 説明: なし")
                        print()
                    
                    # 詳細CSVを保存
                    detailed_csv = "detailed_metadata.csv"
                    with open(detailed_csv, 'w', newline='', encoding='utf-8') as f:
                        if detailed_entries:
                            fieldnames = detailed_entries[0].keys()
                            writer = csv.DictWriter(f, fieldnames=fieldnames)
                            writer.writeheader()
                            writer.writerows(detailed_entries)
                    
                    print(f"💾 詳細メタデータをCSV保存: {detailed_csv}")
                    
                    # CSVの内容を表示
                    print(f"\n📄 保存されたCSVの内容:")
                    with open(detailed_csv, 'r', encoding='utf-8') as f:
                        content = f.read()
                        print(content)
                
            else:
                print(f"❌ メタデータ抽出に失敗しました")
                
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            import traceback
            print(f"詳細エラー: {traceback.format_exc()}")

async def main():
    """メイン関数"""
    await test_detailed_metadata()

if __name__ == "__main__":
    asyncio.run(main())
