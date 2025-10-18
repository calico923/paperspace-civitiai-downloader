#!/usr/bin/env python3
"""
Civitai メタデータ抽出テストスクリプト

実際のモデルファイル（waiIllustriousSDXL_v150.safetensors）を使用して
メタデータ抽出とダウンロードURL取得をテストする
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

async def test_single_model():
    """単一モデルファイルのメタデータ抽出テスト"""
    
    # テスト対象ファイル
    test_file = "/Users/kuniaki-k/Code/paperspace/civitai_downloader/downloads/checkpoints/waiIllustriousSDXL_v150.safetensors"
    
    print("🚀 Civitai メタデータ抽出テスト開始！")
    print(f"📁 テストファイル: {test_file}")
    
    # ファイルの存在確認
    if not os.path.exists(test_file):
        print(f"❌ テストファイルが存在しません: {test_file}")
        return
    
    # 設定ファイルからAPIキーを読み込み
    config_path = "config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        api_key = config.get('civitai_api_key', 'YOUR_API_KEY_HERE')
        
        if api_key == 'YOUR_API_KEY_HERE':
            print("❌ APIキーが設定されていません")
            return
            
        print(f"🔑 APIキー: 設定済み")
        
    except FileNotFoundError:
        print(f"❌ config.jsonが見つかりません: {config_path}")
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
                print(f"\n✅ メタデータ抽出成功！")
                print(f"📄 ファイル名: {metadata.file_name}")
                print(f"📊 ファイルサイズ: {metadata.file_size:,} bytes ({metadata.file_size / (1024**3):.2f} GB)")
                print(f"🔐 SHA256: {metadata.sha256[:16]}...")
                print(f"🏷️  モデルタイプ: {metadata.model_type}")
                print(f"🎯 ベースモデル: {metadata.base_model}")
                
                if metadata.from_civitai:
                    print(f"\n🌐 Civitai情報:")
                    print(f"  📝 モデル名: {metadata.model_name}")
                    print(f"  🆔 モデルID: {metadata.model_id}")
                    print(f"  🔢 バージョンID: {metadata.version_id}")
                    print(f"  👤 作成者: {metadata.creator}")
                    print(f"  🔗 Civitai URL: {metadata.civitai_url}")
                    print(f"  🏷️  タグ: {', '.join(metadata.tags) if metadata.tags else 'なし'}")
                    print(f"  ⚠️  NSFWレベル: {metadata.nsfw_level}")
                    
                    if metadata.download_urls:
                        print(f"\n🔗 ダウンロードURL ({len(metadata.download_urls)}個):")
                        for i, url in enumerate(metadata.download_urls, 1):
                            print(f"  {i}. {url}")
                    else:
                        print(f"\n⚠️  ダウンロードURLが見つかりませんでした")
                else:
                    print(f"\n⚠️  Civitaiからメタデータを取得できませんでした")
                
                # CSV形式でダウンロード履歴を保存
                print(f"\n💾 ダウンロード履歴をCSV形式で保存...")
                csv_output = "test_download_history.csv"
                scanner.save_to_download_history_csv([metadata], csv_output)
                print(f"✅ CSV保存完了: {csv_output}")
                
                # 詳細なダウンロードURL情報を抽出
                download_entries = scanner.extract_download_urls_for_csv([metadata])
                if download_entries:
                    print(f"\n📋 ダウンロードURL詳細:")
                    for i, entry in enumerate(download_entries, 1):
                        print(f"  {i}. {entry['model_name']} ({entry['creator']})")
                        print(f"     URL: {entry['url']}")
                        print(f"     ダウンロードURL: {entry['download_url']}")
                        print(f"     ファイルサイズ: {entry['file_size']}")
                        print(f"     ベースモデル: {entry['base_model']}")
                        print()
                
            else:
                print(f"❌ メタデータ抽出に失敗しました")
                
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            import traceback
            print(f"詳細エラー: {traceback.format_exc()}")

async def main():
    """メイン関数"""
    await test_single_model()

if __name__ == "__main__":
    asyncio.run(main())
