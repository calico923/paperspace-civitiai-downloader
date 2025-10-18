"""
Civitai Model Downloader

Civitai.comからモデルをダウンロードするメインスクリプト
ComfyUI-Lora-Managerの実装を参考に簡略化
"""

import asyncio
import aiohttp
import os
import sys
import argparse
from typing import Optional, Dict, Tuple, List
from datetime import datetime
import time

from url_parser import CivitaiURLParser
from config_manager import ConfigManager
from download_history import DownloadHistoryManager
from model_type_classifier import ModelTypeClassifier


class CivitaiDownloader:
    """Civitaiからモデルをダウンロードするクラス"""
    
    def __init__(self, config: ConfigManager):
        """
        CivitaiDownloaderを初期化
        
        Args:
            config: 設定マネージャー
        """
        self.config = config
        self.api_key = config.get_api_key()
        self.base_url = "https://civitai.com/api/v1"
        self.session: Optional[aiohttp.ClientSession] = None
        self.chunk_size = 4 * 1024 * 1024  # 4MB chunks
        self.type_classifier = ModelTypeClassifier()
    
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
            'User-Agent': 'Civitai-Downloader/1.0'
        }
        
        if use_auth and self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
            headers['Content-Type'] = 'application/json'
        
        return headers
    
    async def get_model_version_info(
        self,
        model_id: Optional[int] = None,
        version_id: Optional[int] = None
    ) -> Optional[Dict]:
        """
        モデルバージョン情報を取得
        
        Args:
            model_id: モデルID
            version_id: バージョンID
            
        Returns:
            Dict: モデル情報、取得失敗時はNone
        """
        try:
            # version_idが指定されている場合は直接取得
            if version_id:
                url = f"{self.base_url}/model-versions/{version_id}"
                async with self.session.get(url, headers=self._get_headers()) as response:
                    if response.status == 200:
                        version_info = await response.json()
                        
                        # モデル情報も取得
                        model_id_from_version = version_info.get('modelId')
                        if model_id_from_version:
                            model_url = f"{self.base_url}/models/{model_id_from_version}"
                            async with self.session.get(model_url, headers=self._get_headers()) as model_response:
                                if model_response.status == 200:
                                    model_data = await model_response.json()
                                    if 'model' not in version_info:
                                        version_info['model'] = {}
                                    version_info['model']['description'] = model_data.get('description')
                                    version_info['model']['tags'] = model_data.get('tags', [])
                                    version_info['creator'] = model_data.get('creator')
                        
                        return version_info
                    elif response.status == 401:
                        print(f"❌ 認証エラー: APIキーが無効です")
                        return None
                    elif response.status == 404:
                        print(f"❌ モデルが見つかりません (Version ID: {version_id})")
                        return None
                    else:
                        print(f"❌ APIエラー (Status: {response.status})")
                        return None
            
            # model_idのみの場合
            elif model_id:
                url = f"{self.base_url}/models/{model_id}"
                async with self.session.get(url, headers=self._get_headers()) as response:
                    if response.status == 200:
                        model_data = await response.json()
                        
                        # 最新バージョンを取得
                        model_versions = model_data.get('modelVersions', [])
                        if not model_versions:
                            print(f"❌ モデルにバージョンが存在しません")
                            return None
                        
                        latest_version = model_versions[0]
                        version_id = latest_version.get('id')
                        
                        # 詳細なバージョン情報を取得
                        return await self.get_model_version_info(version_id=version_id)
                    else:
                        print(f"❌ モデル情報の取得に失敗 (Status: {response.status})")
                        return None
            
        except Exception as e:
            print(f"❌ エラー: {str(e)}")
            return None
    
    async def download_file(
        self,
        url: str,
        save_path: str,
        use_auth: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        ファイルをダウンロード
        
        Args:
            url: ダウンロードURL
            save_path: 保存先パス
            use_auth: 認証を使用するか
            
        Returns:
            Tuple[bool, Optional[str]]: (成功/失敗, エラーメッセージ)
        """
        part_path = save_path + '.part'
        
        # リジューム用: 既存の.partファイルのサイズを取得
        resume_offset = 0
        if os.path.exists(part_path):
            resume_offset = os.path.getsize(part_path)
            print(f"📥 レジューム: {resume_offset:,} バイトから再開")
        
        try:
            headers = self._get_headers(use_auth)
            
            # Range headerでリジュームをサポート
            if resume_offset > 0:
                headers['Range'] = f'bytes={resume_offset}-'
            
            async with self.session.get(url, headers=headers, allow_redirects=True) as response:
                # ステータスコードチェック
                if response.status == 401:
                    return False, "認証エラー: APIキーが無効または必要です"
                elif response.status == 403:
                    return False, "アクセス拒否: Early Accessモデルの可能性があります"
                elif response.status == 404:
                    return False, "ファイルが見つかりません"
                elif response.status not in (200, 206):
                    return False, f"ダウンロード失敗 (Status: {response.status})"
                
                # ファイルサイズ取得
                total_size = int(response.headers.get('content-length', 0))
                if response.status == 206:
                    total_size += resume_offset
                
                # ディレクトリ作成
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                
                # ダウンロード開始
                mode = 'ab' if resume_offset > 0 else 'wb'
                downloaded = resume_offset
                start_time = time.time()
                last_print_time = start_time
                
                print(f"📥 ダウンロード開始: {os.path.basename(save_path)}")
                print(f"📦 サイズ: {self._format_size(total_size)}")
                
                with open(part_path, mode) as f:
                    async for chunk in response.content.iter_chunked(self.chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # 進捗表示（1秒ごと）
                            current_time = time.time()
                            if current_time - last_print_time >= 1.0:
                                elapsed = current_time - start_time
                                speed = (downloaded - resume_offset) / elapsed if elapsed > 0 else 0
                                percent = (downloaded / total_size * 100) if total_size > 0 else 0
                                
                                print(f"⏳ {percent:.1f}% | {self._format_size(downloaded)}/{self._format_size(total_size)} | {self._format_size(speed)}/s", end='\r')
                                last_print_time = current_time
                
                # 完了したら.partを削除してリネーム
                if os.path.exists(save_path):
                    os.remove(save_path)
                os.rename(part_path, save_path)
                
                elapsed = time.time() - start_time
                avg_speed = (downloaded - resume_offset) / elapsed if elapsed > 0 else 0
                
                print(f"\n✅ ダウンロード完了!")
                print(f"⏱️  時間: {elapsed:.1f}秒 | 平均速度: {self._format_size(avg_speed)}/s")
                
                return True, None
                
        except Exception as e:
            return False, f"ダウンロードエラー: {str(e)}"
    
    def _format_size(self, size_bytes: float) -> str:
        """ファイルサイズを読みやすい形式に変換"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    async def download_model(
        self,
        url: str,
        model_type: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        モデルをダウンロード
        
        Args:
            url: Civitai URL
            model_type: モデルタイプ ('lora', 'checkpoint', 'embedding') - Noneの場合は自動判定
            
        Returns:
            Tuple[bool, Optional[str], Optional[Dict]]: (成功/失敗, エラーメッセージ, ダウンロード情報)
        """
        print(f"\n{'='*60}")
        print(f"🚀 Civitai Model Downloader")
        print(f"{'='*60}")
        print(f"📍 URL: {url}")
        print(f"📂 Type: {model_type or '自動判定'}")
        print(f"{'='*60}\n")
        
        # URLを解析
        try:
            model_id, version_id = CivitaiURLParser.parse_url(url)
            print(f"🔍 Model ID: {model_id}, Version ID: {version_id}")
        except ValueError as e:
            return False, str(e), None
        
        # モデル情報を取得
        print(f"📡 モデル情報を取得中...")
        version_info = await self.get_model_version_info(model_id, version_id)
        
        if not version_info:
            return False, "モデル情報の取得に失敗しました", None
        
        # モデルタイプの自動判定または検証
        if model_type is None:
            # 自動判定
            print(f"🤖 モデルタイプを自動判定中...")
            detected_type, reason = self.type_classifier.classify_from_metadata(version_info)
            
            if detected_type is None:
                return False, f"モデルタイプの自動判定に失敗: {reason}", None
            
            model_type = detected_type
            print(f"✅ 自動判定結果: {model_type} ({reason})")
        else:
            # 手動指定されたタイプの検証
            actual_type = version_info.get('model', {}).get('type', '').lower()
            
            # モデルタイプのマッピング
            type_mapping = {
                'lora': ['lora', 'locon', 'loha'],
                'checkpoint': ['checkpoint'],
                'embedding': ['textualinversion']
            }
            
            valid_types = type_mapping.get(model_type, [])
            if actual_type not in valid_types:
                return False, f"モデルタイプが一致しません。期待: {model_type}, 実際: {actual_type}", None
        
        print(f"✅ モデル名: {version_info.get('name', 'Unknown')}")
        print(f"✅ ベースモデル: {version_info.get('baseModel', 'Unknown')}")
        
        # ダウンロードURLを取得
        files = version_info.get('files', [])
        primary_file = next((f for f in files if f.get('primary') and f.get('type') == 'Model'), None)
        
        if not primary_file:
            return False, "ダウンロード可能なファイルが見つかりません", None
        
        download_url = primary_file.get('downloadUrl')
        filename = primary_file.get('name')
        file_size = primary_file.get('sizeKB', 0) * 1024
        
        if not download_url or not filename:
            return False, "ダウンロードURL またはファイル名が見つかりません", None
        
        # 保存先パス
        download_path = self.config.get_download_path(model_type)
        save_path = os.path.join(download_path, filename)
        
        print(f"💾 保存先: {save_path}")
        
        # ダウンロード実行
        success, error = await self.download_file(download_url, save_path, use_auth=True)
        
        if not success:
            return False, error, None
        
        # ダウンロード情報を返す
        download_info = {
            'url': url,
            'model_type': model_type,
            'filename': filename,
            'save_path': save_path,
            'model_id': model_id,
            'version_id': version_id or version_info.get('id'),
            'file_size': file_size
        }
        
        return True, None, download_info


async def redownload_all(downloads: List[Dict], config: ConfigManager, force: bool = False):
    """
    全件再ダウンロードを実行
    
    Args:
        downloads: ダウンロード履歴のリスト
        config: 設定マネージャー
        force: 強制上書きフラグ
    """
    total = len(downloads)
    success_count = 0
    error_count = 0
    
    print(f"\n🚀 全件ダウンロード開始: {total}件")
    print(f"{'='*60}")
    
    async with CivitaiDownloader(config) as downloader:
        for i, download in enumerate(downloads, 1):
            url = download.get('url')
            model_type = download.get('model_type')
            filename = download.get('filename')
            
            print(f"\n📥 [{i}/{total}] {filename}")
            print(f"🔗 URL: {url}")
            print(f"📂 Type: {model_type}")
            print(f"{'-'*40}")
            
            try:
                # 重複チェック（forceがFalseの場合のみ）
                if not force:
                    # URLを解析してmodel_idとversion_idを取得
                    try:
                        model_id, version_id = CivitaiURLParser.parse_url(url)
                        # 履歴マネージャーを取得
                        history_manager = DownloadHistoryManager(config.get_history_file())
                        model_duplicate = history_manager.check_model_downloaded(model_id, version_id)
                        if model_duplicate:
                            print(f"⚠️  スキップ: 既にダウンロード済み")
                            continue
                    except ValueError:
                        pass
                
                # ダウンロード実行
                success, error, download_info = await downloader.download_model(url, model_type)
                
                if success:
                    print(f"✅ 成功: {filename}")
                    success_count += 1
                else:
                    print(f"❌ 失敗: {error}")
                    error_count += 1
                    
            except Exception as e:
                print(f"❌ エラー: {str(e)}")
                error_count += 1
    
    # 結果サマリー
    print(f"\n{'='*60}")
    print(f"🎉 全件ダウンロード完了!")
    print(f"{'='*60}")
    print(f"✅ 成功: {success_count}件")
    print(f"❌ 失敗: {error_count}件")
    print(f"📊 合計: {total}件")


async def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description='Civitai.comからモデルをダウンロード',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用例:
  python downloader.py -u "https://civitai.com/models/649516?modelVersionId=726676"  # 自動判定
  python downloader.py -u "https://civitai.com/models/649516?modelVersionId=726676" -t lora  # 手動指定
  python downloader.py -u "https://civitai.com/models/123456" -t checkpoint
  python downloader.py -u "https://civitai.com/models/789012" -t embedding -c custom_config.json
  python downloader.py -u "https://civitai.com/models/123456" -y  # 非対話型（ipynb対応）
        '''
    )
    
    parser.add_argument(
        '-u', '--url',
        help='Civitai モデルURL'
    )
    
    parser.add_argument(
        '-t', '--type',
        choices=['lora', 'checkpoint', 'embedding'],
        help='モデルタイプ（指定しない場合は自動判定）'
    )
    
    parser.add_argument(
        '-c', '--config',
        default='config.json',
        help='設定ファイルのパス (デフォルト: config.json)'
    )
    
    parser.add_argument(
        '--list-history',
        action='store_true',
        help='ダウンロード履歴を表示'
    )
    
    parser.add_argument(
        '--redownload',
        type=int,
        metavar='INDEX',
        help='履歴から指定されたインデックスのアイテムを再ダウンロード'
    )
    
    parser.add_argument(
        '--redownload-url',
        nargs='?',
        const='all',
        help='指定されたURLを再ダウンロード（履歴から自動検出）。引数なしの場合は全件ダウンロード'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='既存ファイルの上書きを強制（確認なし）'
    )
    
    parser.add_argument(
        '-y', '--yes',
        action='store_true',
        help='すべての確認をスキップ（非対話型モード）'
    )
    
    parser.add_argument(
        '--clean-duplicates',
        action='store_true',
        help='履歴ファイルから重複を除去'
    )
    
    args = parser.parse_args()
    
    try:
        # 設定ファイル読み込み
        print(f"📋 設定ファイル読み込み: {args.config}")
        config = ConfigManager(args.config)
        
        if not config.validate():
            print("❌ 設定ファイルの検証に失敗しました")
            sys.exit(1)
        
        # 履歴マネージャー初期化
        history_manager = DownloadHistoryManager(config.get_history_file())
        
        # 重複除去
        if args.clean_duplicates:
            print(f"\n{'='*60}")
            print(f"🧹 履歴の重複除去")
            print(f"{'='*60}")
            
            duplicates_removed = history_manager.clean_duplicates()
            if duplicates_removed > 0:
                print(f"✅ {duplicates_removed}件の重複を除去しました")
            else:
                print("✅ 重複は見つかりませんでした")
            sys.exit(0)
        
        # 履歴表示
        if args.list_history:
            print(f"\n{'='*60}")
            print(f"📋 ダウンロード履歴")
            print(f"{'='*60}")
            
            downloads = history_manager.get_all_downloads(remove_duplicates=True)
            if not downloads:
                print("履歴がありません")
                sys.exit(0)
            
            print(f"📊 表示件数: {len(downloads)}件（重複除去済み）")
            print()
            
            for i, download in enumerate(downloads, 1):
                print(f"{i:2d}. [{download.get('timestamp', 'Unknown')}]")
                print(f"    Type: {download.get('model_type', 'Unknown')}")
                print(f"    URL: {download.get('url', 'Unknown')}")
                print(f"    File: {download.get('filename', 'Unknown')}")
                print(f"    Size: {download.get('file_size', 'Unknown')}")
                print()
            
            print(f"💡 再ダウンロード: --redownload <INDEX> または --redownload-url <URL>")
            print(f"💡 重複除去: --clean-duplicates")
            sys.exit(0)
        
        # 再ダウンロード（インデックス指定）
        if args.redownload is not None:
            downloads = history_manager.get_all_downloads(remove_duplicates=True)
            if not downloads:
                print("❌ 履歴がありません")
                sys.exit(1)
            
            if args.redownload < 1 or args.redownload > len(downloads):
                print(f"❌ 無効なインデックス: {args.redownload} (1-{len(downloads)})")
                sys.exit(1)
            
            download = downloads[args.redownload - 1]
            url = download.get('url')
            model_type = download.get('model_type')
            
            print(f"🔄 再ダウンロード: {url}")
            print(f"📂 Type: {model_type}")
            
            # 通常のダウンロード処理に移行
            args.url = url
            args.type = model_type
        
        # 再ダウンロード（URL指定）
        elif args.redownload_url:
            if args.redownload_url == 'all':
                # 全件ダウンロード
                print(f"\n{'='*60}")
                print(f"🔄 全件再ダウンロード")
                print(f"{'='*60}")
                
                downloads = history_manager.get_all_downloads(remove_duplicates=True)
                if not downloads:
                    print("❌ 履歴がありません")
                    sys.exit(1)
                
                print(f"📊 ダウンロード対象: {len(downloads)}件")
                
                # 確認
                if not args.force and not args.yes:
                    choice = input("全件ダウンロードを実行しますか？ (y/N): ")
                    if choice.lower() != 'y':
                        print("キャンセルしました")
                        sys.exit(0)
                
                # 全件ダウンロード実行
                await redownload_all(downloads, config, args.force)
                sys.exit(0)
            else:
                # 引数が数値かどうかチェック
                try:
                    index = int(args.redownload_url)
                    # 数値の場合はインデックス指定として処理
                    downloads = history_manager.get_all_downloads(remove_duplicates=True)
                    if not downloads:
                        print("❌ 履歴がありません")
                        sys.exit(1)
                    
                    if index < 1 or index > len(downloads):
                        print(f"❌ 無効なインデックス: {index} (1-{len(downloads)})")
                        sys.exit(1)
                    
                    download = downloads[index - 1]
                    url = download.get('url')
                    model_type = download.get('model_type')
                    
                    print(f"🔄 再ダウンロード: {url}")
                    print(f"📂 Type: {model_type}")
                    
                    # 通常のダウンロード処理に移行
                    args.url = url
                    args.type = model_type
                    
                except ValueError:
                    # 数値でない場合はURLとして処理
                    download_info = history_manager.get_download_info(args.redownload_url)
                    if not download_info:
                        print(f"❌ 履歴にURLが見つかりません: {args.redownload_url}")
                        sys.exit(1)
                    
                    url = download_info.get('url')
                    model_type = download_info.get('model_type')
                    
                    print(f"🔄 再ダウンロード: {url}")
                    print(f"📂 Type: {model_type}")
                    
                    # 通常のダウンロード処理に移行
                    args.url = url
                    args.type = model_type
        
        # URLが指定されていない場合はエラー
        if not args.url:
            print("❌ URLを指定してください")
            print("💡 履歴表示: --list-history")
            print("💡 再ダウンロード: --redownload <INDEX> または --redownload-url <URL>")
            print("💡 モデルタイプは自動判定されます（-t で手動指定も可能）")
            sys.exit(1)
        
        # 重複チェック（URLとmodel_id+version_idの両方でチェック）
        url_duplicate = history_manager.check_url_downloaded(args.url)
        
        # URLを解析してmodel_idとversion_idを取得
        try:
            model_id, version_id = CivitaiURLParser.parse_url(args.url)
            model_duplicate = history_manager.check_model_downloaded(model_id, version_id)
        except ValueError:
            model_duplicate = False
        
        if (url_duplicate or model_duplicate) and not args.force and not args.yes:
            print(f"⚠️  このモデルは既にダウンロード済みです:")
            if url_duplicate:
                print(f"   URL: {args.url}")
            if model_duplicate:
                print(f"   Model ID: {model_id}, Version ID: {version_id}")
            choice = input("続行しますか？ (y/N): ")
            if choice.lower() != 'y':
                print("キャンセルしました")
                sys.exit(0)
        
        # ダウンローダー実行
        async with CivitaiDownloader(config) as downloader:
            success, error, download_info = await downloader.download_model(args.url, args.type)
            
            if success and download_info:
                print(f"\n{'='*60}")
                print(f"🎉 ダウンロード成功!")
                print(f"{'='*60}")
                
                # 履歴に記録
                history_manager.record_download(
                    url=download_info['url'],
                    model_type=download_info['model_type'],
                    filename=download_info['filename'],
                    model_id=download_info['model_id'],
                    version_id=download_info['version_id'],
                    file_size=download_info.get('file_size')
                )
                
                sys.exit(0)
            else:
                print(f"\n{'='*60}")
                print(f"❌ ダウンロード失敗")
                print(f"{'='*60}")
                print(f"エラー: {error}")
                sys.exit(1)
    
    except FileNotFoundError as e:
        print(f"\n❌ {str(e)}")
        sys.exit(1)
    except ValueError as e:
        print(f"\n❌ {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n\n⚠️  ユーザーによって中断されました")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 予期しないエラー: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

