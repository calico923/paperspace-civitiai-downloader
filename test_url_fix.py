#!/usr/bin/env python3
"""
URL修正テストスクリプト

修正されたCivitai URL生成ロジックをテストする
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# 現在のディレクトリをPythonパスに追加
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from model_metadata_scanner import ModelMetadataScanner

async def test_url_fix():
    """URL修正テスト"""
    
    print("🚀 Civitai URL修正テスト開始！")
    
    # テスト対象ファイル
    test_file = "/Users/kuniaki-k/Code/paperspace/civitai_downloader/downloads/checkpoints/waiIllustriousSDXL_v150.safetensors"
    
    print(f"📁 テストファイル: {test_file}")
    
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
            
            if metadata:
                print(f"✅ メタデータ抽出成功！")
                print(f"📄 ファイル名: {metadata.file_name}")
                print(f"🆔 モデルID: {metadata.model_id}")
                print(f"🔢 バージョンID: {metadata.version_id}")
                print(f"🔗 Civitai URL: {metadata.civitai_url}")
                
                # URL形式の検証
                expected_url = f"https://civitai.com/models/{metadata.model_id}?modelVersionId={metadata.version_id}"
                if metadata.civitai_url == expected_url:
                    print(f"✅ URL形式が正しく生成されました！")
                    print(f"   期待値: {expected_url}")
                    print(f"   実際値: {metadata.civitai_url}")
                else:
                    print(f"❌ URL形式が間違っています")
                    print(f"   期待値: {expected_url}")
                    print(f"   実際値: {metadata.civitai_url}")
                
                # CSV出力テスト
                print(f"\n📝 CSV出力テスト...")
                csv_output = "test_url_fix.csv"
                scanner.save_to_download_history_csv([metadata], csv_output)
                print(f"✅ CSV保存完了: {csv_output}")
                
                # CSVの内容を表示
                print(f"\n📄 保存されたCSVの内容:")
                with open(csv_output, 'r', encoding='utf-8') as f:
                    content = f.read()
                    print(content)
                
                # 詳細メタデータもテスト
                print(f"\n📋 詳細メタデータテスト...")
                detailed_entries = scanner.extract_detailed_metadata_for_csv([metadata])
                if detailed_entries:
                    print(f"✅ 詳細メタデータ抽出成功！")
                    for entry in detailed_entries:
                        print(f"  🔗 URL: {entry['url']}")
                        print(f"  🆔 モデルID: {entry['model_id']}")
                        print(f"  🔢 バージョンID: {entry['version_id']}")
                
            else:
                print(f"❌ メタデータ抽出に失敗しました")
                
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            import traceback
            print(f"詳細エラー: {traceback.format_exc()}")

async def main():
    """メイン関数"""
    await test_url_fix()

if __name__ == "__main__":
    asyncio.run(main())
