"""
JSON to CSV Converter

model_metadata_results.json を download_history.csv 互換フォーマットに変換
重複チェック付きで既存CSVに追記
"""

import json
import argparse
import sys
import os
from typing import List, Dict, Optional
from datetime import datetime

from download_history import DownloadHistoryManager


class JSONToCSVConverter:
    """JSONをCSVフォーマットに変換するクラス"""

    def __init__(self, history_file: str = "download_history.csv"):
        """
        JSONToCSVConverterを初期化

        Args:
            history_file: 出力先CSVファイルのパス
        """
        self.history_manager = DownloadHistoryManager(history_file)
        self.history_file = history_file

    def _format_file_size(self, size_bytes: int) -> str:
        """ファイルサイズを人間が読みやすい形式に変換"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

    def _check_duplicate(self, model_id: Optional[int], version_id: Optional[int]) -> bool:
        """
        重複チェック（model_id + version_idベース）

        Args:
            model_id: モデルID
            version_id: バージョンID

        Returns:
            bool: 重複している場合True
        """
        if not model_id or not version_id:
            return False

        return self.history_manager.check_model_downloaded(model_id, version_id)

    def load_json(self, json_file: str) -> List[Dict]:
        """
        JSONファイルを読み込む

        Args:
            json_file: JSONファイルのパス

        Returns:
            List[Dict]: メタデータのリスト
        """
        if not os.path.exists(json_file):
            print(f"❌ JSONファイルが見つかりません: {json_file}")
            return []

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            print(f"✅ JSONロード完了: {len(data)}件のエントリ")
            return data if isinstance(data, list) else [data]

        except json.JSONDecodeError as e:
            print(f"❌ JSON解析エラー: {str(e)}")
            return []
        except Exception as e:
            print(f"❌ ファイル読み込みエラー: {str(e)}")
            return []

    def convert_to_csv(self, metadata_list: List[Dict]) -> int:
        """
        JSONメタデータをCSVに変換して追記

        Args:
            metadata_list: メタデータのリスト

        Returns:
            int: 追記されたレコード数
        """
        if not metadata_list:
            print("⚠️ 変換対象のデータがありません")
            return 0

        added_count = 0
        skipped_count = 0

        print(f"\n📋 CSV変換処理を開始...")
        print(f"{'='*60}")

        for i, metadata in enumerate(metadata_list, 1):
            model_id = metadata.get('model_id')
            version_id = metadata.get('version_id')

            # 重複チェック
            if self._check_duplicate(model_id, version_id):
                print(f"⏭️  [{i}/{len(metadata_list)}] スキップ: {metadata.get('file_name')} (重複)")
                skipped_count += 1
                continue

            # CSVに追記
            try:
                self.history_manager.record_download(
                    url=metadata.get('civitai_url', ''),
                    model_type=metadata.get('model_type', 'unknown'),
                    filename=metadata.get('file_name', ''),
                    model_id=model_id,
                    version_id=version_id,
                    file_size=metadata.get('file_size'),
                    api_model_type=metadata.get('api_model_type'),
                    lora_subcategory=metadata.get('lora_subcategory')
                )

                print(f"✅ [{i}/{len(metadata_list)}] 追記完了: {metadata.get('file_name')}")
                added_count += 1

            except Exception as e:
                print(f"❌ [{i}/{len(metadata_list)}] エラー: {str(e)}")
                continue

        # 結果サマリー
        print(f"{'='*60}")
        print(f"\n📊 変換完了:")
        print(f"  ✅ 追記: {added_count}件")
        print(f"  ⏭️  スキップ (重複): {skipped_count}件")
        print(f"  📁 出力: {self.history_file}")

        return added_count


async def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description='JSON形式のメタデータをCSVに変換',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用例:
  python json_to_csv.py -i model_metadata_results.json
  python json_to_csv.py -i model_metadata_results.json -o download_history.csv
        '''
    )

    parser.add_argument(
        '-i', '--input',
        required=True,
        help='入力JSONファイル（model_metadata_results.json）'
    )

    parser.add_argument(
        '-o', '--output',
        default='download_history.csv',
        help='出力CSVファイル (デフォルト: download_history.csv)'
    )

    args = parser.parse_args()

    try:
        # コンバーター初期化
        converter = JSONToCSVConverter(args.output)

        # JSONロード
        metadata_list = converter.load_json(args.input)

        if not metadata_list:
            sys.exit(1)

        # CSV変換・追記
        added_count = converter.convert_to_csv(metadata_list)

        if added_count > 0:
            print(f"\n🎉 成功: {added_count}件のデータを追記しました")
            sys.exit(0)
        else:
            print(f"\n⚠️  警告: 追記されたデータはありません")
            sys.exit(0)

    except Exception as e:
        print(f"\n❌ エラー: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
