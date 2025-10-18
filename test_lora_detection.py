#!/usr/bin/env python3
"""
LoRA検出テストスクリプト

lorasディレクトリのファイルが正しくloraタイプとして検出されるかテストする
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

async def test_lora_detection():
    """LoRA検出テスト"""
    
    print("🚀 LoRA検出テスト開始！")
    
    # テスト対象ファイル（lorasディレクトリ内）
    test_file = "/Users/kuniaki-k/Code/paperspace/civitai_downloader/downloads/loras/qos_tattoo_v0.1-illu_done.safetensors"
    
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
                print(f"📁 ファイルパス: {metadata.file_path}")
                print(f"🏷️  検出されたモデルタイプ: {metadata.model_type}")
                print(f"🎯 ベースモデル: {metadata.base_model}")
                
                # モデルタイプの検証
                if metadata.model_type == "lora":
                    print(f"✅ 正しくloraタイプとして検出されました！")
                else:
                    print(f"❌ モデルタイプが間違っています: {metadata.model_type} (期待値: lora)")
                
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
                
            else:
                print(f"❌ メタデータ抽出に失敗しました")
                
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            import traceback
            print(f"詳細エラー: {traceback.format_exc()}")

async def main():
    """メイン関数"""
    await test_lora_detection()

if __name__ == "__main__":
    asyncio.run(main())
