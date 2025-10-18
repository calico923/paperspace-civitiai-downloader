# Civitai メタデータ抽出実装ガイド

ComfyUI-Lora-Managerのログ分析に基づいて、civitai_downloaderに同様の機能を実装するためのガイドです。

## 実装アーキテクチャ

### 1. コアコンポーネント

```
civitai_downloader/
├── metadata_extractor.py      # メタデータ抽出器
├── hash_calculator.py         # SHA256ハッシュ計算
├── api_client.py             # Civitai API クライアント
├── download_url_extractor.py  # ダウンロードURL抽出器
└── metadata_cache.py         # メタデータキャッシュ
```

### 2. データフロー

```
モデルファイル → SHA256ハッシュ → API検索 → メタデータ取得 → ダウンロードURL抽出
```

## 実装手順

### Step 1: SHA256ハッシュ計算器

```python
# hash_calculator.py
import hashlib
import os
from pathlib import Path

class HashCalculator:
    def __init__(self):
        self.chunk_size = 8192
    
    def calculate_sha256(self, file_path: str) -> str:
        """ファイルのSHA256ハッシュを計算"""
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(self.chunk_size), b""):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
    
    def is_model_file(self, file_path: str) -> bool:
        """モデルファイルかどうかを判定"""
        model_extensions = ['.safetensors', '.ckpt', '.pt', '.pth']
        return Path(file_path).suffix.lower() in model_extensions
```

### Step 2: Civitai API クライアント

```python
# api_client.py
import aiohttp
import asyncio
import logging
from typing import Dict, Optional, Tuple

class CivitaiAPIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://civitai.com/api/v1"
        self.session = None
        self.logger = logging.getLogger(__name__)
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_model_by_hash(self, model_hash: str) -> Tuple[bool, Optional[Dict]]:
        """ハッシュでモデルを検索"""
        url = f"{self.base_url}/model-versions/by-hash/{model_hash}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return True, data
                else:
                    self.logger.error(f"API Error: {response.status}")
                    return False, None
        except Exception as e:
            self.logger.error(f"Request failed: {e}")
            return False, None
    
    async def get_model_details(self, model_id: int) -> Tuple[bool, Optional[Dict]]:
        """モデル詳細情報を取得"""
        url = f"{self.base_url}/models/{model_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return True, data
                else:
                    self.logger.error(f"API Error: {response.status}")
                    return False, None
        except Exception as e:
            self.logger.error(f"Request failed: {e}")
            return False, None
```

### Step 3: ダウンロードURL抽出器

```python
# download_url_extractor.py
from typing import List, Optional, Dict

class DownloadURLExtractor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def extract_download_urls(self, model_version: Dict) -> List[str]:
        """モデルバージョンからダウンロードURLを抽出"""
        download_urls = []
        
        try:
            files = model_version.get('files', [])
            for file_info in files:
                if self._is_primary_model_file(file_info):
                    # プライマリダウンロードURL
                    primary_url = file_info.get('downloadUrl')
                    if primary_url:
                        download_urls.append(primary_url)
                    
                    # ミラーURL
                    mirrors = file_info.get('mirrors', [])
                    for mirror in mirrors:
                        if mirror.get('url') and not mirror.get('deletedAt'):
                            download_urls.append(mirror['url'])
            
            self.logger.info(f"Extracted {len(download_urls)} download URLs")
            return download_urls
            
        except Exception as e:
            self.logger.error(f"Error extracting download URLs: {e}")
            return []
    
    def _is_primary_model_file(self, file_info: Dict) -> bool:
        """プライマリモデルファイルかどうかを判定"""
        return (
            file_info.get('type') == 'Model' and 
            file_info.get('primary', False)
        )
    
    def get_file_info(self, model_version: Dict) -> Optional[Dict]:
        """ファイル情報を取得"""
        files = model_version.get('files', [])
        for file_info in files:
            if self._is_primary_model_file(file_info):
                return {
                    'id': file_info.get('id'),
                    'name': file_info.get('name'),
                    'sizeKB': file_info.get('sizeKB'),
                    'downloadUrl': file_info.get('downloadUrl')
                }
        return None
```

### Step 4: メタデータ抽出器

```python
# metadata_extractor.py
import asyncio
from typing import Dict, List, Optional, Tuple
from pathlib import Path

class MetadataExtractor:
    def __init__(self, api_client, url_extractor):
        self.api_client = api_client
        self.url_extractor = url_extractor
        self.logger = logging.getLogger(__name__)
    
    async def extract_metadata(self, file_path: str) -> Optional[Dict]:
        """ファイルからメタデータを抽出"""
        try:
            # SHA256ハッシュを計算
            from hash_calculator import HashCalculator
            hash_calc = HashCalculator()
            model_hash = hash_calc.calculate_sha256(file_path)
            
            # APIからメタデータを取得
            success, model_version = await self.api_client.get_model_by_hash(model_hash)
            if not success or not model_version:
                self.logger.warning(f"No metadata found for hash: {model_hash[:16]}...")
                return None
            
            # ダウンロードURLを抽出
            download_urls = self.url_extractor.extract_download_urls(model_version)
            
            # メタデータを統合
            metadata = {
                'file_path': file_path,
                'model_hash': model_hash,
                'model_id': model_version.get('modelId'),
                'version_id': model_version.get('id'),
                'name': model_version.get('name'),
                'description': model_version.get('description'),
                'nsfw_level': model_version.get('nsfwLevel'),
                'trained_words': model_version.get('trainedWords', []),
                'base_model': model_version.get('baseModel'),
                'base_model_type': model_version.get('baseModelType'),
                'created_at': model_version.get('createdAt'),
                'updated_at': model_version.get('updatedAt'),
                'download_urls': download_urls,
                'file_info': self.url_extractor.get_file_info(model_version)
            }
            
            self.logger.info(f"Metadata extracted for: {Path(file_path).name}")
            return metadata
            
        except Exception as e:
            self.logger.error(f"Error extracting metadata: {e}")
            return None
    
    async def extract_batch(self, file_paths: List[str]) -> List[Dict]:
        """複数ファイルのメタデータを一括抽出"""
        tasks = [self.extract_metadata(path) for path in file_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # エラーを除外して有効な結果のみを返す
        valid_results = []
        for result in results:
            if isinstance(result, dict) and result is not None:
                valid_results.append(result)
            elif isinstance(result, Exception):
                self.logger.error(f"Batch extraction error: {result}")
        
        return valid_results
```

### Step 5: メイン統合クラス

```python
# civitai_metadata_extractor.py
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional

class CivitaiMetadataExtractor:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
    
    async def process_directory(self, directory_path: str) -> List[Dict]:
        """ディレクトリ内のモデルファイルを処理"""
        directory = Path(directory_path)
        model_files = []
        
        # モデルファイルを検索
        for ext in ['*.safetensors', '*.ckpt', '*.pt', '*.pth']:
            model_files.extend(directory.rglob(ext))
        
        self.logger.info(f"Found {len(model_files)} model files")
        
        # メタデータを抽出
        async with CivitaiAPIClient(self.api_key) as api_client:
            url_extractor = DownloadURLExtractor()
            metadata_extractor = MetadataExtractor(api_client, url_extractor)
            
            results = await metadata_extractor.extract_batch([str(f) for f in model_files])
            
            self.logger.info(f"Successfully extracted metadata for {len(results)} files")
            return results
    
    async def process_single_file(self, file_path: str) -> Optional[Dict]:
        """単一ファイルのメタデータを抽出"""
        async with CivitaiAPIClient(self.api_key) as api_client:
            url_extractor = DownloadURLExtractor()
            metadata_extractor = MetadataExtractor(api_client, url_extractor)
            
            return await metadata_extractor.extract_metadata(file_path)
```

## 使用例

### 基本的な使用方法

```python
import asyncio
from civitai_metadata_extractor import CivitaiMetadataExtractor

async def main():
    # APIキーを設定
    api_key = "your_civitai_api_key"
    
    # メタデータ抽出器を初期化
    extractor = CivitaiMetadataExtractor(api_key)
    
    # ディレクトリを処理
    results = await extractor.process_directory("/path/to/models")
    
    # 結果を表示
    for metadata in results:
        print(f"Model: {metadata['name']}")
        print(f"Download URLs: {metadata['download_urls']}")
        print("---")

if __name__ == "__main__":
    asyncio.run(main())
```

### 設定ファイルとの統合

```python
# config.json
{
    "civitai_api_key": "your_api_key_here",
    "model_directories": [
        "/path/to/loras",
        "/path/to/checkpoints"
    ],
    "output_format": "json",
    "cache_enabled": true
}
```

## エラーハンドリング

### 一般的なエラーと対応

1. **認証エラー (401)**
   ```python
   if response.status == 401:
       logger.error("Invalid API key")
       return None
   ```

2. **レート制限 (429)**
   ```python
   if response.status == 429:
       await asyncio.sleep(60)  # 1分待機
       return await retry_request()
   ```

3. **モデル未発見 (404)**
   ```python
   if response.status == 404:
       logger.warning("Model not found on Civitai")
       return None
   ```

## パフォーマンス最適化

### 1. 並行処理制限

```python
# セマフォで並行数を制限
semaphore = asyncio.Semaphore(5)

async def limited_request():
    async with semaphore:
        return await api_client.get_model_by_hash(hash)
```

### 2. キャッシュ機能

```python
# メタデータキャッシュ
cache = {}

async def get_cached_metadata(hash):
    if hash in cache:
        return cache[hash]
    
    metadata = await extract_metadata(hash)
    cache[hash] = metadata
    return metadata
```

## ログ設定

```python
import logging

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('metadata_extraction.log'),
        logging.StreamHandler()
    ]
)
```

## テスト

### 単体テスト

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_metadata_extraction():
    # モックデータ
    mock_response = {
        "id": 12345,
        "modelId": 67890,
        "name": "Test Model",
        "files": [{"type": "Model", "primary": True, "downloadUrl": "https://test.com"}]
    }
    
    # APIクライアントをモック
    with patch('api_client.CivitaiAPIClient.get_model_by_hash', return_value=(True, mock_response)):
        extractor = CivitaiMetadataExtractor("test_key")
        result = await extractor.process_single_file("test.safetensors")
        
        assert result is not None
        assert result['name'] == "Test Model"
        assert len(result['download_urls']) == 1
```

## まとめ

この実装ガイドに従って、ComfyUI-Lora-Managerと同様のメタデータ抽出機能をcivitai_downloaderに実装できます。主要なポイントは：

1. **SHA256ハッシュベース検索** - ファイル名に依存しない正確な特定
2. **非同期処理** - 効率的なAPI呼び出し
3. **エラーハンドリング** - 堅牢なエラー処理
4. **キャッシュ機能** - パフォーマンス最適化
5. **ログ機能** - デバッグとモニタリング

この実装により、ComfyUI-Lora-Managerと同等の機能を持つメタデータ抽出システムを構築できます。
