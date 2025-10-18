"""
Download History Manager Module

ダウンロード履歴の記録と管理（CSV形式対応）
"""

import os
import csv
from datetime import datetime
from typing import Optional, List, Dict


class DownloadHistoryManager:
    """ダウンロード履歴を管理するクラス（CSV形式対応）"""
    
    # CSVのヘッダー
    CSV_HEADERS = [
        'timestamp', 'model_type', 'url', 'filename', 
        'model_id', 'version_id', 'file_size', 'file_size_bytes'
    ]
    
    def __init__(self, history_file: str):
        """
        DownloadHistoryManagerを初期化
        
        Args:
            history_file: 履歴ファイルのパス
        """
        self.history_file = history_file
        
        # 履歴ファイルのディレクトリが存在しない場合は作成
        history_dir = os.path.dirname(history_file)
        if history_dir and not os.path.exists(history_dir):
            os.makedirs(history_dir, exist_ok=True)
        
        # CSVファイルが存在しない場合はヘッダーを作成
        self._ensure_csv_headers()
    
    def _ensure_csv_headers(self):
        """CSVファイルにヘッダーが存在しない場合は追加"""
        if not os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(self.CSV_HEADERS)
            except Exception as e:
                print(f"⚠️  CSVヘッダーの作成に失敗: {str(e)}")
    
    def record_download(
        self,
        url: str,
        model_type: str,
        filename: str,
        model_id: Optional[int] = None,
        version_id: Optional[int] = None,
        file_size: Optional[int] = None
    ) -> None:
        """
        ダウンロード成功を履歴に記録（CSV形式）
        
        Args:
            url: ダウンロード元URL
            model_type: モデルタイプ
            filename: 保存されたファイル名
            model_id: モデルID
            version_id: バージョンID
            file_size: ファイルサイズ（バイト）
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # ファイルサイズを人間が読みやすい形式に変換
        size_str = self._format_file_size(file_size) if file_size else "Unknown"
        
        # CSV行データを作成
        row_data = [
            timestamp,
            model_type,
            url,
            filename,
            str(model_id) if model_id else "",
            str(version_id) if version_id else "",
            size_str,
            str(file_size) if file_size else ""
        ]
        
        # CSVファイルに追記
        try:
            with open(self.history_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row_data)
            print(f"✅ 履歴に記録しました: {self.history_file}")
        except Exception as e:
            print(f"⚠️  履歴の記録に失敗しました: {str(e)}")
    
    def _format_file_size(self, size_bytes: int) -> str:
        """
        ファイルサイズを人間が読みやすい形式に変換
        
        Args:
            size_bytes: バイト単位のファイルサイズ
            
        Returns:
            str: フォーマットされたファイルサイズ (例: "1.23 GB")
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    def _remove_duplicates(self, downloads: List[Dict]) -> List[Dict]:
        """
        ダウンロード履歴から重複を除去（model_id + version_idで判定）
        
        Args:
            downloads: ダウンロード履歴のリスト
            
        Returns:
            List[Dict]: 重複除去されたダウンロード履歴のリスト
        """
        seen = set()
        unique_downloads = []
        
        for download in downloads:
            model_id = download.get('model_id', '')
            version_id = download.get('version_id', '')
            
            # model_id + version_idの組み合わせで一意性を判定
            key = f"{model_id}_{version_id}"
            
            if key not in seen and model_id and version_id:
                seen.add(key)
                unique_downloads.append(download)
            elif not model_id or not version_id:
                # model_idやversion_idが空の場合はURLで判定
                url = download.get('url', '')
                if url and url not in seen:
                    seen.add(url)
                    unique_downloads.append(download)
        
        return unique_downloads
    
    def get_recent_downloads(self, count: int = 10) -> List[Dict]:
        """
        最近のダウンロード履歴を取得（CSV形式）
        
        Args:
            count: 取得する履歴の数
            
        Returns:
            List[Dict]: 最近のダウンロード履歴のリスト
        """
        if not os.path.exists(self.history_file):
            return []
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            # 最後のcount行を返す
            return rows[-count:] if len(rows) > count else rows
        except Exception as e:
            print(f"履歴の読み込みに失敗: {str(e)}")
            return []
    
    def get_all_downloads(self, remove_duplicates: bool = True) -> List[Dict]:
        """
        全てのダウンロード履歴を取得
        
        Args:
            remove_duplicates: 重複を除去するかどうか
        
        Returns:
            List[Dict]: 全てのダウンロード履歴のリスト
        """
        if not os.path.exists(self.history_file):
            return []
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                downloads = list(reader)
            
            if remove_duplicates:
                return self._remove_duplicates(downloads)
            return downloads
        except Exception as e:
            print(f"履歴の読み込みに失敗: {str(e)}")
            return []
    
    def get_downloads_by_type(self, model_type: str) -> List[Dict]:
        """
        指定されたモデルタイプのダウンロード履歴を取得
        
        Args:
            model_type: モデルタイプ
            
        Returns:
            List[Dict]: 該当するダウンロード履歴のリスト
        """
        all_downloads = self.get_all_downloads()
        return [download for download in all_downloads if download.get('model_type') == model_type]
    
    def check_url_downloaded(self, url: str) -> bool:
        """
        URLが既にダウンロード済みかチェック
        
        Args:
            url: チェックするURL
            
        Returns:
            bool: ダウンロード済みの場合True
        """
        all_downloads = self.get_all_downloads(remove_duplicates=False)
        return any(download.get('url') == url for download in all_downloads)
    
    def check_model_downloaded(self, model_id: int, version_id: int) -> bool:
        """
        モデル（model_id + version_id）が既にダウンロード済みかチェック
        
        Args:
            model_id: モデルID
            version_id: バージョンID
            
        Returns:
            bool: ダウンロード済みの場合True
        """
        all_downloads = self.get_all_downloads(remove_duplicates=False)
        for download in all_downloads:
            if (download.get('model_id') == str(model_id) and 
                download.get('version_id') == str(version_id)):
                return True
        return False
    
    def get_download_info(self, url: str) -> Optional[Dict]:
        """
        指定されたURLのダウンロード情報を取得
        
        Args:
            url: ダウンロードURL
            
        Returns:
            Optional[Dict]: ダウンロード情報、見つからない場合はNone
        """
        all_downloads = self.get_all_downloads()
        for download in all_downloads:
            if download.get('url') == url:
                return download
        return None
    
    def list_downloads_for_redownload(self) -> List[Dict]:
        """
        再ダウンロード可能な履歴を取得（URLとtypeのみ）
        
        Returns:
            List[Dict]: 再ダウンロード用の情報リスト
        """
        all_downloads = self.get_all_downloads()
        return [
            {
                'url': download.get('url'),
                'model_type': download.get('model_type'),
                'filename': download.get('filename'),
                'timestamp': download.get('timestamp')
            }
            for download in all_downloads
        ]
    
    def clean_duplicates(self) -> int:
        """
        履歴ファイルから重複を除去して新しいファイルに保存
        
        Returns:
            int: 除去された重複の数
        """
        if not os.path.exists(self.history_file):
            return 0
        
        try:
            # 元の履歴を読み込み
            with open(self.history_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                original_downloads = list(reader)
            
            # 重複除去
            unique_downloads = self._remove_duplicates(original_downloads)
            
            # 重複数計算
            duplicates_removed = len(original_downloads) - len(unique_downloads)
            
            if duplicates_removed > 0:
                # バックアップファイル作成
                backup_file = self.history_file + '.backup'
                with open(backup_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(self.CSV_HEADERS)
                    for download in original_downloads:
                        writer.writerow([download.get(header, '') for header in self.CSV_HEADERS])
                
                # 新しいファイルに書き込み
                with open(self.history_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(self.CSV_HEADERS)
                    for download in unique_downloads:
                        writer.writerow([download.get(header, '') for header in self.CSV_HEADERS])
                
                print(f"✅ 重複除去完了: {duplicates_removed}件の重複を除去")
                print(f"📁 バックアップファイル: {backup_file}")
            else:
                print("✅ 重複は見つかりませんでした")
            
            return duplicates_removed
            
        except Exception as e:
            print(f"❌ 重複除去に失敗: {str(e)}")
            return 0


if __name__ == "__main__":
    # テスト
    manager = DownloadHistoryManager("./test_history.txt")
    
    # ダウンロード記録のテスト
    manager.record_download(
        url="https://civitai.com/models/649516?modelVersionId=726676",
        model_type="lora",
        filename="test_model.safetensors",
        model_id=649516,
        version_id=726676,
        file_size=123456789
    )
    
    # 最近の履歴を表示
    print("\n最近のダウンロード:")
    for entry in manager.get_recent_downloads(5):
        print(f"  {entry}")
    
    # 重複チェック
    is_downloaded = manager.check_url_downloaded("https://civitai.com/models/649516?modelVersionId=726676")
    print(f"\nURL already downloaded: {is_downloaded}")

