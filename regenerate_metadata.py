#!/usr/bin/env python3
"""
メタデータ再生成スクリプト

修正されたmodel_metadata_scanner.pyを使用して
既存のmodel_metadata_results.jsonを再生成する
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

async def regenerate_metadata():
    """メタデータを再生成"""
    
    print("🚀 メタデータ再生成開始！")
    
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
        print(f"\n🔍 全ディレクトリをスキャン中...")
        
        try:
            # 各ディレクトリをスキャン
            all_metadata = []
            
            # 設定からディレクトリパスを取得
            download_paths = config.get('download_paths', {})
            
            for model_type, directory in download_paths.items():
                print(f"\n📁 {model_type.upper()}ディレクトリをスキャン: {directory}")
                if os.path.exists(directory):
                    metadata_list = await scanner.scan_directory(directory, recursive=True)
                    all_metadata.extend(metadata_list)
                    print(f"✅ {len(metadata_list)}個のファイルを処理")
                    
                    # 各ファイルの結果を表示
                    for metadata in metadata_list:
                        print(f"  📄 {metadata.file_name} -> {metadata.model_type}")
                else:
                    print(f"⚠️  ディレクトリが存在しません: {directory}")
            
            if all_metadata:
                # タイプ別に分類
                classified = scanner.classify_by_type(all_metadata)
                print(f"\n📊 分類結果:")
                for model_type, items in classified.items():
                    if items:
                        print(f"  {model_type.capitalize()}: {len(items)}個")
                
                # 結果をJSONファイルに保存
                output_file = "model_metadata_results.json"
                scanner.save_metadata_to_json(all_metadata, output_file)
                print(f"\n💾 結果を保存しました: {output_file}")
                
                # ダウンロードURLを抽出
                urls_by_type = scanner.extract_download_urls(all_metadata)
                print(f"\n🔗 ダウンロードURL:")
                for model_type, urls in urls_by_type.items():
                    if urls:
                        print(f"  {model_type.capitalize()}: {len(urls)}個")
                
                # CSV形式でも保存
                csv_output = "download_history_updated.csv"
                scanner.save_to_download_history_csv(all_metadata, csv_output)
                print(f"💾 CSV形式でも保存しました: {csv_output}")
                
            else:
                print(f"\n❌ スキャンできるファイルが見つかりませんでした")
                
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            import traceback
            print(f"詳細エラー: {traceback.format_exc()}")

async def main():
    """メイン関数"""
    await regenerate_metadata()

if __name__ == "__main__":
    asyncio.run(main())
