"""
Model Metadata Scanner

モデルファイルからCivitaiのメタデータを取得し、ダウンロードURLを抽出・分類する機能
ComfyUI-Lora-Managerの実装を参考に簡略化
"""

import os
import json
import hashlib
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import aiohttp
import asyncio
import time
import random

# ログレベルを設定
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ModelMetadata:
    """モデルメタデータの基本構造"""
    file_name: str
    file_path: str
    file_size: int
    sha256: str
    model_type: str  # lora, checkpoint, embedding
    base_model: str
    civitai_url: Optional[str] = None
    download_urls: List[str] = None
    model_id: Optional[int] = None
    version_id: Optional[int] = None
    model_name: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = None
    creator: Optional[str] = None
    nsfw_level: int = 0
    from_civitai: bool = False
    
    def __post_init__(self):
        if self.download_urls is None:
            self.download_urls = []
        if self.tags is None:
            self.tags = []

class ModelMetadataScanner:
    """モデルファイルからメタデータをスキャンするクラス"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初期化
        
        Args:
            api_key: Civitai APIキー（オプション）
        """
        self.api_key = api_key
        self.base_url = "https://civitai.com/api/v1"
        self.session: Optional[aiohttp.ClientSession] = None
        
        # サポートするファイル拡張子
        self.supported_extensions = {
            '.safetensors', '.ckpt', '.pt', '.pth', '.bin'
        }
        
        # モデルタイプの判定キーワード
        self.model_type_keywords = {
            'lora': ['lora', 'locon', 'loha'],
            'checkpoint': ['checkpoint', 'model'],
            'embedding': ['embedding', 'textualinversion', 'ti']
        }
    
    async def __aenter__(self):
        """非同期コンテキストマネージャーのエントリー"""
        await self._create_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャーの終了"""
        await self.close()
    
    async def _create_session(self):
        """HTTP sessionを作成"""
        connector = aiohttp.TCPConnector(
            ssl=True,
            limit=8,
            ttl_dns_cache=300,
            force_close=False,
            enable_cleanup_closed=True
        )
        
        timeout = aiohttp.ClientTimeout(
            total=None,
            connect=60,
            sock_read=300
        )
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        )
    
    async def close(self):
        """HTTP sessionを閉じる"""
        if self.session:
            await self.session.close()
    
    def _get_headers(self, use_auth: bool = True) -> Dict[str, str]:
        """リクエストヘッダーを取得"""
        headers = {
            'User-Agent': 'Model-Metadata-Scanner/1.0'
        }
        
        if use_auth and self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
            headers['Content-Type'] = 'application/json'
        
        return headers
    
    def _calculate_sha256(self, file_path: str) -> str:
        """ファイルのSHA256ハッシュを計算"""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"SHA256計算エラー {file_path}: {e}")
            return ""
    
    def _detect_model_type(self, file_path: str, file_name: str) -> str:
        """ファイル名とディレクトリ構造からモデルタイプを判定"""
        file_name_lower = file_name.lower()
        file_path_lower = file_path.lower()
        
        # まずディレクトリ構造から判定
        if '/loras/' in file_path_lower or '\\loras\\' in file_path_lower:
            return "lora"
        elif '/checkpoints/' in file_path_lower or '\\checkpoints\\' in file_path_lower:
            return "checkpoint"
        elif '/embeddings/' in file_path_lower or '\\embeddings\\' in file_path_lower:
            return "embedding"
        
        # ディレクトリ構造で判定できない場合はファイル名から判定
        for model_type, keywords in self.model_type_keywords.items():
            for keyword in keywords:
                if keyword in file_name_lower:
                    return model_type
        
        # デフォルトはcheckpoint
        return "checkpoint"
    
    def _detect_base_model(self, file_path: str, file_name: str) -> str:
        """ファイル名からベースモデルを判定"""
        file_name_lower = file_name.lower()
        
        if 'sdxl' in file_name_lower:
            return 'SDXL'
        elif 'sd3' in file_name_lower:
            return 'SD3'
        elif 'sd2' in file_name_lower:
            return 'SD2.1'
        elif 'sd1' in file_name_lower or 'sd15' in file_name_lower:
            return 'SD1.5'
        else:
            return 'Unknown'
    
    async def _search_model_by_hash(self, sha256: str) -> Optional[Dict]:
        """SHA256ハッシュでCivitaiからモデルを検索（複数プロバイダー対応）"""
        if not self.session or not sha256:
            return None
        
        # プロバイダーリスト（Civitai API → CivArchive）
        providers = [
            ("Civitai API", self._search_civitai_api),
            ("CivArchive", self._search_civarchive_api)
        ]
        
        last_error = None
        
        for provider_name, search_func in providers:
            try:
                logger.info(f"{provider_name}で検索中: {sha256[:16]}...")
                result = await search_func(sha256)
                
                if result:
                    logger.info(f"{provider_name}で検索成功!")
                    return result
                else:
                    logger.warning(f"{provider_name}で検索失敗")
                    
            except Exception as e:
                logger.warning(f"{provider_name}でエラー: {e}")
                last_error = str(e)
                continue
        
        logger.warning(f"すべてのプロバイダーで検索失敗: {last_error}")
        return None
    
    async def _search_civitai_api(self, sha256: str) -> Optional[Dict]:
        """Civitai APIで検索（レート制限対応）"""
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                url = f"{self.base_url}/model-versions/by-hash/{sha256}"
                async with self.session.get(url, headers=self._get_headers()) as response:
                    if response.status == 200:
                        version_info = await response.json()
                        
                        # モデル情報も取得
                        model_id = version_info.get('modelId')
                        if model_id:
                            model_url = f"{self.base_url}/models/{model_id}"
                            async with self.session.get(model_url, headers=self._get_headers()) as model_response:
                                if model_response.status == 200:
                                    model_data = await model_response.json()
                                    if 'model' not in version_info:
                                        version_info['model'] = {}
                                    version_info['model']['description'] = model_data.get('description')
                                    version_info['model']['tags'] = model_data.get('tags', [])
                                    version_info['creator'] = model_data.get('creator')
                        
                        return version_info
                    elif response.status == 404:
                        logger.debug(f"Civitai API: ハッシュ {sha256[:16]}... のモデルが見つかりません")
                        return None
                    elif response.status == 401:
                        logger.warning(f"Civitai API: 認証エラー")
                        return None
                    elif response.status == 429:
                        # レート制限の場合はリトライ
                        retry_after = int(response.headers.get('Retry-After', 60))
                        delay = min(retry_after, 300)  # 最大5分
                        logger.warning(f"Civitai API: レート制限 (試行 {attempt + 1}/{max_retries}), {delay}秒待機")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(delay)
                            continue
                        else:
                            return None
                    elif response.status == 500:
                        # サーバーエラーの場合は短い待機後にリトライ
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(f"Civitai API: サーバーエラー (試行 {attempt + 1}/{max_retries}), {delay:.1f}秒待機")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(delay)
                            continue
                        else:
                            return None
                    else:
                        logger.warning(f"Civitai API: エラー {response.status}")
                        return None
            except Exception as e:
                logger.error(f"Civitai API検索エラー (試行 {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(delay)
                    continue
                else:
                    return None
        
        return None
    
    async def _search_civarchive_api(self, sha256: str) -> Optional[Dict]:
        """CivArchive APIで検索（フォールバック）"""
        try:
            # CivArchiveのエンドポイント
            url = f"https://civarchive.com/api/sha256/{sha256.lower()}"
            async with self.session.get(url, headers=self._get_headers(use_auth=False)) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"CivArchiveで検索成功: {data.get('name', 'Unknown')}")
                    
                    # レスポンス構造をデバッグ出力
                    logger.debug(f"CivArchiveレスポンス構造: {list(data.keys())}")
                    if 'files' in data:
                        logger.debug(f"files配列: {len(data['files'])}個")
                        for i, file_info in enumerate(data['files']):
                            logger.debug(f"ファイル {i}: {file_info}")
                    
                    return data
                elif response.status == 404:
                    logger.debug(f"CivArchive: ハッシュ {sha256[:16]}... のモデルが見つかりません")
                    return None
                else:
                    logger.warning(f"CivArchive: エラー {response.status}")
                    return None
        except Exception as e:
            logger.error(f"CivArchive検索エラー: {e}")
            return None
    
    async def _get_model_version_info(self, model_id: int, version_id: Optional[int] = None) -> Optional[Dict]:
        """モデルバージョン情報を取得"""
        if not self.session:
            return None
        
        try:
            if version_id:
                url = f"{self.base_url}/model-versions/{version_id}"
            else:
                url = f"{self.base_url}/models/{model_id}"
            
            async with self.session.get(url, headers=self._get_headers()) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"モデル情報取得エラー: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"モデル情報取得エラー: {e}")
            return None
    
    def _extract_download_urls(self, model_info: Dict) -> List[str]:
        """モデル情報からダウンロードURLを抽出"""
        download_urls = []
        
        try:
            logger.debug(f"ダウンロードURL抽出開始: {list(model_info.keys())}")
            
            # バージョン情報からファイル情報を取得
            if 'files' in model_info:
                logger.debug(f"files配列: {len(model_info['files'])}個")
                for i, file_info in enumerate(model_info['files']):
                    logger.debug(f"ファイル {i}: {file_info.get('name', 'Unknown')} (type: {file_info.get('type')}, primary: {file_info.get('primary')})")
                    
                    if file_info.get('type') == 'Model' and file_info.get('primary'):
                        # メインのダウンロードURL
                        if 'downloadUrl' in file_info and file_info['downloadUrl']:
                            download_urls.append(file_info['downloadUrl'])
                            logger.debug(f"メインURL追加: {file_info['downloadUrl']}")
                        
                        # ミラーURL
                        if 'mirrors' in file_info:
                            logger.debug(f"ミラー数: {len(file_info['mirrors'])}")
                            for j, mirror in enumerate(file_info['mirrors']):
                                if mirror.get('url') and not mirror.get('deletedAt'):
                                    download_urls.append(mirror['url'])
                                    logger.debug(f"ミラーURL追加: {mirror['url']}")
            
            # CivArchiveの場合は異なる構造の可能性
            if not download_urls and 'downloadUrl' in model_info:
                download_urls.append(model_info['downloadUrl'])
                logger.debug(f"CivArchiveメインURL追加: {model_info['downloadUrl']}")
            
            # 重複を除去
            download_urls = list(set(download_urls))
            
            logger.info(f"抽出されたダウンロードURL: {len(download_urls)}個")
            for i, url in enumerate(download_urls):
                logger.info(f"  {i+1}. {url}")
            
        except Exception as e:
            logger.error(f"ダウンロードURL抽出エラー: {e}")
            import traceback
            logger.error(f"詳細エラー: {traceback.format_exc()}")
        
        return download_urls
    
    async def scan_model_file(self, file_path: str) -> Optional[ModelMetadata]:
        """
        単一のモデルファイルをスキャン
        
        Args:
            file_path: モデルファイルのパス
            
        Returns:
            ModelMetadata: メタデータ、取得失敗時はNone
        """
        if not os.path.exists(file_path):
            logger.error(f"ファイルが存在しません: {file_path}")
            return None
        
        # ファイル情報を取得
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        # 拡張子チェック
        _, ext = os.path.splitext(file_name)
        if ext.lower() not in self.supported_extensions:
            logger.warning(f"サポートされていない拡張子: {ext}")
            return None
        
        # モデルタイプとベースモデルを判定
        model_type = self._detect_model_type(file_path, file_name)
        base_model = self._detect_base_model(file_path, file_name)
        
        # SHA256ハッシュを計算
        sha256 = self._calculate_sha256(file_path)
        
        # 基本メタデータを作成
        metadata = ModelMetadata(
            file_name=file_name,
            file_path=file_path,
            file_size=file_size,
            sha256=sha256,
            model_type=model_type,
            base_model=base_model
        )
        
        # Civitaiからメタデータを取得
        if sha256 and self.session:
            try:
                logger.info(f"Civitai検索開始: SHA256={sha256[:16]}...")
                
                # ハッシュでモデルを検索
                model_info = await self._search_model_by_hash(sha256)
                
                if model_info:
                    logger.info(f"Civitai検索成功: {model_info.get('name', 'Unknown')}")
                    metadata.from_civitai = True
                    metadata.model_id = model_info.get('modelId')
                    metadata.model_name = model_info.get('name')
                    metadata.description = model_info.get('model', {}).get('description')
                    metadata.tags = model_info.get('model', {}).get('tags', [])
                    metadata.creator = model_info.get('creator', {}).get('username') if model_info.get('creator') else None
                    metadata.nsfw_level = model_info.get('nsfw', 0)
                    metadata.version_id = model_info.get('id')
                    
                    if metadata.model_id and metadata.version_id:
                        metadata.civitai_url = f"https://civitai.com/models/{metadata.model_id}?modelVersionId={metadata.version_id}"
                    
                    # ダウンロードURLを抽出
                    metadata.download_urls = self._extract_download_urls(model_info)
                    logger.info(f"ダウンロードURL抽出: {len(metadata.download_urls)}個")
                else:
                    logger.info(f"Civitai検索失敗: SHA256={sha256[:16]}...")
                
            except Exception as e:
                logger.error(f"Civitaiメタデータ取得エラー: {e}")
        else:
            if not sha256:
                logger.warning(f"SHA256ハッシュが空です: {file_path}")
            if not self.session:
                logger.warning(f"HTTPセッションが初期化されていません")
        
        return metadata
    
    async def scan_directory(self, directory_path: str, recursive: bool = True) -> List[ModelMetadata]:
        """
        ディレクトリ内のモデルファイルをスキャン
        
        Args:
            directory_path: スキャンするディレクトリ
            recursive: 再帰的にスキャンするか
            
        Returns:
            List[ModelMetadata]: メタデータのリスト
        """
        if not os.path.exists(directory_path):
            logger.error(f"ディレクトリが存在しません: {directory_path}")
            return []
        
        metadata_list = []
        
        try:
            if recursive:
                for root, dirs, files in os.walk(directory_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        _, ext = os.path.splitext(file)
                        if ext.lower() in self.supported_extensions:
                            metadata = await self.scan_model_file(file_path)
                            if metadata:
                                metadata_list.append(metadata)
            else:
                for file in os.listdir(directory_path):
                    file_path = os.path.join(directory_path, file)
                    if os.path.isfile(file_path):
                        _, ext = os.path.splitext(file)
                        if ext.lower() in self.supported_extensions:
                            metadata = await self.scan_model_file(file_path)
                            if metadata:
                                metadata_list.append(metadata)
        
        except Exception as e:
            logger.error(f"ディレクトリスキャンエラー: {e}")
        
        return metadata_list
    
    def classify_by_type(self, metadata_list: List[ModelMetadata]) -> Dict[str, List[ModelMetadata]]:
        """メタデータをモデルタイプ別に分類"""
        classified = {
            'lora': [],
            'checkpoint': [],
            'embedding': [],
            'unknown': []
        }
        
        for metadata in metadata_list:
            model_type = metadata.model_type.lower()
            if model_type in classified:
                classified[model_type].append(metadata)
            else:
                classified['unknown'].append(metadata)
        
        return classified
    
    def extract_download_urls(self, metadata_list: List[ModelMetadata]) -> Dict[str, List[str]]:
        """メタデータからダウンロードURLを抽出・分類"""
        urls_by_type = {
            'lora': [],
            'checkpoint': [],
            'embedding': [],
            'unknown': []
        }
        
        for metadata in metadata_list:
            model_type = metadata.model_type.lower()
            if model_type in urls_by_type:
                urls_by_type[model_type].extend(metadata.download_urls)
            else:
                urls_by_type['unknown'].extend(metadata.download_urls)
        
        # 重複を除去
        for model_type in urls_by_type:
            urls_by_type[model_type] = list(set(urls_by_type[model_type]))
        
        return urls_by_type
    
    def save_metadata_to_json(self, metadata_list: List[ModelMetadata], output_path: str):
        """メタデータをJSONファイルに保存"""
        try:
            data = []
            for metadata in metadata_list:
                data.append(asdict(metadata))
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"メタデータを保存しました: {output_path}")
        
        except Exception as e:
            logger.error(f"メタデータ保存エラー: {e}")
    
    def load_metadata_from_json(self, input_path: str) -> List[ModelMetadata]:
        """JSONファイルからメタデータを読み込み"""
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            metadata_list = []
            for item in data:
                metadata = ModelMetadata(**item)
                metadata_list.append(metadata)
            
            logger.info(f"メタデータを読み込みました: {input_path}")
            return metadata_list
        
        except Exception as e:
            logger.error(f"メタデータ読み込みエラー: {e}")
            return []
    
    def save_to_download_history_csv(self, metadata_list: List[ModelMetadata], output_path: str):
        """メタデータをdownload_history.csv形式で保存"""
        try:
            import csv
            from datetime import datetime
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # ヘッダー行
                writer.writerow([
                    'timestamp', 'model_type', 'url', 'filename', 'model_id', 
                    'version_id', 'file_size', 'file_size_bytes'
                ])
                
                # データ行
                for metadata in metadata_list:
                    if metadata.download_urls:
                        for download_url in metadata.download_urls:
                            # ファイルサイズをGBとバイトで表示
                            file_size_gb = metadata.file_size / (1024**3)
                            file_size_str = f"{file_size_gb:.2f} GB"
                            
                            # Civitai URLを取得（model_idとversion_idがある場合は正しいURL形式で生成）
                            if metadata.civitai_url:
                                civitai_url = metadata.civitai_url
                            elif metadata.model_id and metadata.version_id:
                                civitai_url = f"https://civitai.com/models/{metadata.model_id}?modelVersionId={metadata.version_id}"
                            else:
                                civitai_url = download_url
                            
                            writer.writerow([
                                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                metadata.model_type,
                                civitai_url,
                                metadata.file_name,
                                metadata.model_id or '',
                                metadata.version_id or '',
                                file_size_str,
                                str(metadata.file_size)
                            ])
            
            logger.info(f"ダウンロード履歴をCSV形式で保存しました: {output_path}")
        
        except Exception as e:
            logger.error(f"CSV保存エラー: {e}")
    
    def extract_download_urls_for_csv(self, metadata_list: List[ModelMetadata]) -> List[Dict]:
        """CSV出力用のダウンロードURL情報を抽出（download_history.csv形式）"""
        download_entries = []
        
        for metadata in metadata_list:
            if metadata.download_urls:
                for download_url in metadata.download_urls:
                    # ファイルサイズをGBとバイトで表示
                    file_size_gb = metadata.file_size / (1024**3)
                    file_size_str = f"{file_size_gb:.2f} GB"
                    
                    # Civitai URLを取得（model_idとversion_idがある場合は正しいURL形式で生成）
                    if metadata.civitai_url:
                        civitai_url = metadata.civitai_url
                    elif metadata.model_id and metadata.version_id:
                        civitai_url = f"https://civitai.com/models/{metadata.model_id}?modelVersionId={metadata.version_id}"
                    else:
                        civitai_url = download_url
                    
                    entry = {
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'model_type': metadata.model_type,
                        'url': civitai_url,
                        'filename': metadata.file_name,
                        'model_id': metadata.model_id or '',
                        'version_id': metadata.version_id or '',
                        'file_size': file_size_str,
                        'file_size_bytes': str(metadata.file_size)
                    }
                    download_entries.append(entry)
        
        return download_entries
    
    def extract_detailed_metadata_for_csv(self, metadata_list: List[ModelMetadata]) -> List[Dict]:
        """詳細メタデータをCSV出力用に抽出（拡張フィールド付き）"""
        detailed_entries = []
        
        for metadata in metadata_list:
            if metadata.download_urls:
                for download_url in metadata.download_urls:
                    # ファイルサイズをGBとバイトで表示
                    file_size_gb = metadata.file_size / (1024**3)
                    file_size_str = f"{file_size_gb:.2f} GB"
                    
                    # Civitai URLを取得（model_idがある場合）
                    civitai_url = metadata.civitai_url or download_url
                    
                    entry = {
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'model_type': metadata.model_type,
                        'url': civitai_url,
                        'filename': metadata.file_name,
                        'model_id': metadata.model_id or '',
                        'version_id': metadata.version_id or '',
                        'file_size': file_size_str,
                        'file_size_bytes': str(metadata.file_size),
                        'model_name': metadata.model_name or '',
                        'creator': metadata.creator or '',
                        'base_model': metadata.base_model or '',
                        'sha256': metadata.sha256,
                        'download_url': download_url,
                        'nsfw_level': metadata.nsfw_level,
                        'tags': ', '.join(metadata.tags) if metadata.tags else '',
                        'description': metadata.description or ''
                    }
                    detailed_entries.append(entry)
        
        return detailed_entries


# 使用例
async def main():
    """使用例"""
    import json
    
    # config.jsonから設定を読み込み
    config_path = "config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        api_key = config.get('civitai_api_key', 'YOUR_API_KEY_HERE')
        download_paths = config.get('download_paths', {})
        
        print(f"🔑 APIキー: {'設定済み' if api_key != 'YOUR_API_KEY_HERE' else '未設定'}")
        print(f"📁 ダウンロードパス: {download_paths}")
        
    except FileNotFoundError:
        print(f"❌ config.jsonが見つかりません: {config_path}")
        return
    except Exception as e:
        print(f"❌ 設定読み込みエラー: {e}")
        return
    
    # スキャナーを初期化
    async with ModelMetadataScanner(api_key=api_key) as scanner:
        # 各ディレクトリをスキャン
        all_metadata = []
        
        for model_type, directory in download_paths.items():
            print(f"\n🔍 {model_type.upper()}ディレクトリをスキャン: {directory}")
            if os.path.exists(directory):
                metadata_list = await scanner.scan_directory(directory, recursive=True)
                all_metadata.extend(metadata_list)
                print(f"✅ {len(metadata_list)}個のファイルを処理")
            else:
                print(f"⚠️  ディレクトリが存在しません: {directory}")
        
        if all_metadata:
            # タイプ別に分類
            classified = scanner.classify_by_type(all_metadata)
            print(f"\n📊 分類結果:")
            for model_type, items in classified.items():
                if items:
                    print(f"  {model_type.capitalize()}: {len(items)}個")
            
            # ダウンロードURLを抽出
            urls_by_type = scanner.extract_download_urls(all_metadata)
            print(f"\n🔗 ダウンロードURL:")
            for model_type, urls in urls_by_type.items():
                if urls:
                    print(f"  {model_type.capitalize()}: {len(urls)}個")
            
            # 結果をJSONファイルに保存
            output_file = "model_metadata_results.json"
            scanner.save_metadata_to_json(all_metadata, output_file)
            print(f"\n💾 結果を保存しました: {output_file}")
        else:
            print(f"\n❌ スキャンできるファイルが見つかりませんでした")


if __name__ == "__main__":
    asyncio.run(main())
