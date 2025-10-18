#!/usr/bin/env python3
"""
履歴ファイルをCSV形式に変換するスクリプト

既存のテキスト形式の履歴ファイルをCSV形式に変換します。
"""

import os
import re
import csv
from datetime import datetime
from typing import List, Dict, Optional


def parse_old_history_line(line: str) -> Optional[Dict]:
    """
    古い形式の履歴行を解析
    
    Args:
        line: 履歴行
        
    Returns:
        Optional[Dict]: 解析されたデータ、失敗時はNone
    """
    # パターン: [timestamp] | Type: type | URL: url | File: filename | ModelID: id | VersionID: id | Size: size
    pattern = r'\[([^\]]+)\] \| Type: ([^|]+) \| URL: ([^|]+) \| File: ([^|]+)(?:\| ModelID: (\d+))?(?:\| VersionID: (\d+))?(?:\| Size: ([^|]+))?'
    
    match = re.match(pattern, line.strip())
    if not match:
        return None
    
    timestamp, model_type, url, filename, model_id, version_id, size = match.groups()
    
    return {
        'timestamp': timestamp.strip(),
        'model_type': model_type.strip(),
        'url': url.strip(),
        'filename': filename.strip(),
        'model_id': model_id.strip() if model_id else '',
        'version_id': version_id.strip() if version_id else '',
        'file_size': size.strip() if size else '',
        'file_size_bytes': ''  # 古い形式ではバイト数が不明
    }


def migrate_history_file(old_file: str, new_file: str) -> bool:
    """
    履歴ファイルをCSV形式に変換
    
    Args:
        old_file: 古い履歴ファイルのパス
        new_file: 新しいCSVファイルのパス
        
    Returns:
        bool: 変換成功時True
    """
    if not os.path.exists(old_file):
        print(f"❌ 古い履歴ファイルが見つかりません: {old_file}")
        return False
    
    # CSVヘッダー
    headers = [
        'timestamp', 'model_type', 'url', 'filename', 
        'model_id', 'version_id', 'file_size', 'file_size_bytes'
    ]
    
    try:
        # 古いファイルを読み込み
        with open(old_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # データを解析
        parsed_data = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            data = parse_old_history_line(line)
            if data:
                parsed_data.append(data)
            else:
                print(f"⚠️  解析できない行をスキップ: {line}")
        
        # CSVファイルに書き込み
        with open(new_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for data in parsed_data:
                writer.writerow([
                    data['timestamp'],
                    data['model_type'],
                    data['url'],
                    data['filename'],
                    data['model_id'],
                    data['version_id'],
                    data['file_size'],
                    data['file_size_bytes']
                ])
        
        print(f"✅ 履歴ファイルを変換しました: {len(parsed_data)}件")
        print(f"📁 新しいファイル: {new_file}")
        return True
        
    except Exception as e:
        print(f"❌ 変換に失敗しました: {str(e)}")
        return False


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='履歴ファイルをCSV形式に変換',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用例:
  python migrate_history.py -i download_history.txt -o download_history.csv
  python migrate_history.py -i download_history.txt  # 自動で.csv拡張子を追加
        '''
    )
    
    parser.add_argument(
        '-i', '--input',
        required=True,
        help='古い履歴ファイルのパス'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='新しいCSVファイルのパス（省略時は自動生成）'
    )
    
    parser.add_argument(
        '--backup',
        action='store_true',
        help='古いファイルをバックアップする'
    )
    
    args = parser.parse_args()
    
    # 出力ファイル名を決定
    if args.output:
        output_file = args.output
    else:
        # 入力ファイル名から拡張子を変更
        base_name = os.path.splitext(args.input)[0]
        output_file = f"{base_name}.csv"
    
    print(f"🔄 履歴ファイル変換開始")
    print(f"📁 入力: {args.input}")
    print(f"📁 出力: {output_file}")
    print(f"{'='*50}")
    
    # 変換実行
    success = migrate_history_file(args.input, output_file)
    
    if success:
        # バックアップ作成
        if args.backup:
            backup_file = f"{args.input}.backup"
            try:
                import shutil
                shutil.copy2(args.input, backup_file)
                print(f"💾 バックアップ作成: {backup_file}")
            except Exception as e:
                print(f"⚠️  バックアップ作成に失敗: {str(e)}")
        
        print(f"\n🎉 変換完了！")
        print(f"💡 新しいCSVファイルを使用してダウンロードを再実行できます")
    else:
        print(f"\n❌ 変換に失敗しました")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
