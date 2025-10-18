#!/usr/bin/env python3
"""
統合テスト: 実際のdownload_history.csvに新しいエントリを追加

既存のdownload_history.csvに新しいメタデータエントリを追加して
完全な統合テストを実行する
"""

import asyncio
import json
import os
import sys
import csv
from datetime import datetime
from pathlib import Path

# 現在のディレクトリをPythonパスに追加
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from model_metadata_scanner import ModelMetadataScanner

async def integration_test():
    """統合テスト: 実際のdownload_history.csvに新しいエントリを追加"""
    
    print("🚀 統合テスト開始！")
    print("📋 既存のdownload_history.csvに新しいエントリを追加します")
    
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
    
    # 既存のdownload_history.csvをバックアップ
    history_file = "download_history.csv"
    backup_file = "download_history.csv.backup"
    
    if os.path.exists(history_file):
        import shutil
        shutil.copy2(history_file, backup_file)
        print(f"📁 既存の履歴をバックアップ: {backup_file}")
    
    # スキャナーを初期化してテスト実行
    async with ModelMetadataScanner(api_key=api_key) as scanner:
        print(f"\n🔍 メタデータ抽出開始...")
        
        try:
            # 単一ファイルをスキャン
            metadata = await scanner.scan_model_file(test_file)
            
            if metadata and metadata.download_urls:
                print(f"✅ メタデータ抽出成功！")
                print(f"📄 ファイル名: {metadata.file_name}")
                print(f"🆔 モデルID: {metadata.model_id}")
                print(f"🔢 バージョンID: {metadata.version_id}")
                print(f"🔗 ダウンロードURL: {len(metadata.download_urls)}個")
                
                # 既存のdownload_history.csvに新しいエントリを追加
                print(f"\n📝 既存のdownload_history.csvに新しいエントリを追加...")
                
                # 既存のCSVを読み込み
                existing_entries = []
                if os.path.exists(history_file):
                    with open(history_file, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        existing_entries = list(reader)
                    print(f"📊 既存エントリ数: {len(existing_entries)}")
                
                # 新しいエントリを作成
                new_entries = scanner.extract_download_urls_for_csv([metadata])
                print(f"🆕 新しいエントリ数: {len(new_entries)}")
                
                # 既存のエントリと新しいエントリを結合
                all_entries = existing_entries + new_entries
                print(f"📈 合計エントリ数: {len(all_entries)}")
                
                # 更新されたCSVを保存
                with open(history_file, 'w', newline='', encoding='utf-8') as f:
                    if all_entries:
                        fieldnames = all_entries[0].keys()
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(all_entries)
                
                print(f"✅ download_history.csvを更新しました: {history_file}")
                
                # 更新されたCSVの内容を表示
                print(f"\n📋 更新されたdownload_history.csvの内容:")
                with open(history_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    print(content)
                
                # 統計情報を表示
                print(f"\n📊 統計情報:")
                print(f"  📁 総エントリ数: {len(all_entries)}")
                
                # モデルタイプ別の統計
                type_counts = {}
                for entry in all_entries:
                    model_type = entry.get('model_type', 'unknown')
                    type_counts[model_type] = type_counts.get(model_type, 0) + 1
                
                for model_type, count in type_counts.items():
                    print(f"  🏷️  {model_type}: {count}個")
                
                print(f"\n🎉 統合テスト完了！")
                print(f"💾 バックアップファイル: {backup_file}")
                print(f"📄 更新されたファイル: {history_file}")
                
            else:
                print(f"❌ メタデータ抽出に失敗しました")
                
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            import traceback
            print(f"詳細エラー: {traceback.format_exc()}")

async def main():
    """メイン関数"""
    await integration_test()

if __name__ == "__main__":
    asyncio.run(main())
