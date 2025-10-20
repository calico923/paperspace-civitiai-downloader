# ComfyUI-Lora-Manager ログ出力実装計画

## 概要

ComfyUI-Lora-Managerに、civitai_downloaderと同じ形式の詳細なログ出力機能を追加し、`/Users/kuniaki-k/Code/paperspace/civitai_downloader/logs/`ディレクトリに出力する。

## 目的

- API呼び出しの詳細なトレース
- デバッグ効率の向上
- 問題発生時の原因究明を容易に
- civitai_downloaderとの統一的なログ管理

---

## 現状分析

### ComfyUI-Lora-Manager の現状

**ロギング設定:**
- **場所:** `standalone.py:106-108`
- **現在の実装:**
  ```python
  logging.basicConfig(level=logging.INFO,
                      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
  logger = logging.getLogger("lora-manager-standalone")
  ```
- **問題点:**
  - コンソール出力のみ（ファイル出力なし）
  - 基本的なフォーマットのみ
  - API詳細がログに含まれない

**既存のロガー使用状況:**
- 74個のファイルで`logger = logging.getLogger(__name__)`を使用
- 主要サービス:
  - `py/services/civitai_client.py` - Civitai API クライアント
  - `py/services/metadata_service.py` - メタデータ取得
  - `py/services/download_coordinator.py` - ダウンロード管理
  - `py/services/model_scanner.py` - モデルスキャン

### civitai_downloader の参考実装

**ログディレクトリ:**
```
/Users/kuniaki-k/Code/paperspace/civitai_downloader/logs/
├── civitai_metadata_20251018_181000.log  (1.2MB)
├── civitai_metadata_20251019_035253.log  (535KB)
└── ...
```

**ログフォーマット例:**
```
[2025-10-18T18:10:17.600226] API REQUEST: GET https://civitai.com/api/v1/model-versions/by-hash/40a4971c6866cf919734b2036ac44a6c657b66a0350724b35dbeb572790826ff
  Auth: True

[2025-10-18T18:10:18.075238] API RESPONSE: SUCCESS
  Data: {
  "id": 2130994,
  "modelId": 1882733,
  "name": "v1.0 for IL",
  "nsfwLevel": 1,
  ...
}
```

**ファイル名規則:**
- パターン: `civitai_metadata_YYYYMMDD_HHMMSS.log`
- タイムスタンプ: ISO 8601形式（マイクロ秒付き）

---

## 実装計画

### Phase 1: 共通ログユーティリティの作成

#### 1.1 ファイル: `py/utils/logging_config.py`

**責務:**
- ログ設定の一元管理
- ファイルハンドラーの作成
- カスタムフォーマッターの提供

**実装内容:**

```python
"""
Logging configuration for ComfyUI-Lora-Manager
Outputs to civitai_downloader/logs/ directory
"""
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

class CivitaiLogFormatter(logging.Formatter):
    """Civitai API style log formatter"""

    def format(self, record: logging.LogRecord) -> str:
        # ISO 8601 timestamp with microseconds
        timestamp = datetime.fromtimestamp(record.created).isoformat()

        # Format: [TIMESTAMP] LEVEL: message
        if hasattr(record, 'log_type'):
            # Special formatting for API logs
            return f"[{timestamp}] {record.log_type}: {record.getMessage()}"
        else:
            # Standard format
            return f"[{timestamp}] {record.levelname}: {record.getMessage()}"

def get_log_file_path(base_name: str = "lora_manager") -> str:
    """
    Generate log file path in civitai_downloader/logs/

    Args:
        base_name: Base name for log file (default: "lora_manager")

    Returns:
        Absolute path to log file
    """
    # Get civitai_downloader logs directory
    current_dir = Path(__file__).resolve().parent.parent.parent
    logs_dir = current_dir.parent / "civitai_downloader" / "logs"

    # Create directory if it doesn't exist
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{base_name}_{timestamp}.log"

    return str(logs_dir / log_filename)

def setup_logging(
    log_level: int = logging.INFO,
    log_file: Optional[str] = None,
    console: bool = True
) -> str:
    """
    Setup logging configuration for ComfyUI-Lora-Manager

    Args:
        log_level: Logging level (default: INFO)
        log_file: Custom log file path (default: auto-generated)
        console: Enable console output (default: True)

    Returns:
        Path to log file
    """
    # Get or generate log file path
    if log_file is None:
        log_file = get_log_file_path()

    # Create formatter
    formatter = CivitaiLogFormatter()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # File handler
    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Failed to create log file {log_file}: {e}")
        print("Falling back to console-only logging")

    # Console handler
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # Log startup message
    root_logger.info(f"Logging initialized: {log_file}")

    return log_file

def log_api_request(logger: logging.Logger, method: str, url: str, auth: bool = False):
    """
    Log API request in Civitai format

    Args:
        logger: Logger instance
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        auth: Whether authentication is used
    """
    extra = {'log_type': 'API REQUEST'}
    logger.info(f"{method} {url}\n  Auth: {auth}", extra=extra)

def log_api_response(logger: logging.Logger, status: str, data: Optional[dict] = None):
    """
    Log API response in Civitai format

    Args:
        logger: Logger instance
        status: Response status (SUCCESS, ERROR, etc.)
        data: Optional response data summary
    """
    extra = {'log_type': 'API RESPONSE'}
    message = status
    if data:
        import json
        # Truncate large responses
        data_str = json.dumps(data, indent=2, ensure_ascii=False)
        if len(data_str) > 5000:
            data_str = data_str[:5000] + "\n  ... (truncated)"
        message = f"{status}\n  Data: {data_str}"
    logger.info(message, extra=extra)
```

#### 1.2 テストケース

**ファイル:** `tests/utils/test_logging_config.py`

```python
import pytest
import logging
from pathlib import Path
from py.utils.logging_config import (
    setup_logging,
    get_log_file_path,
    log_api_request,
    log_api_response
)

def test_log_file_path_generation():
    """Test log file path is in civitai_downloader/logs/"""
    log_path = get_log_file_path()
    assert "civitai_downloader/logs" in log_path
    assert log_path.endswith(".log")
    assert "lora_manager_" in log_path

def test_setup_logging_creates_file(tmp_path):
    """Test that logging setup creates log file"""
    log_file = str(tmp_path / "test.log")
    result_path = setup_logging(log_file=log_file)

    assert Path(result_path).exists()
    assert result_path == log_file

def test_api_request_logging(tmp_path):
    """Test API request logging format"""
    log_file = str(tmp_path / "test.log")
    setup_logging(log_file=log_file, console=False)

    logger = logging.getLogger(__name__)
    log_api_request(logger, "GET", "https://civitai.com/api/v1/models", auth=True)

    with open(log_file, 'r') as f:
        content = f.read()
        assert "API REQUEST:" in content
        assert "GET https://civitai.com/api/v1/models" in content
        assert "Auth: True" in content

def test_api_response_logging(tmp_path):
    """Test API response logging format"""
    log_file = str(tmp_path / "test.log")
    setup_logging(log_file=log_file, console=False)

    logger = logging.getLogger(__name__)
    log_api_response(logger, "SUCCESS", {"id": 123, "name": "test"})

    with open(log_file, 'r') as f:
        content = f.read()
        assert "API RESPONSE:" in content
        assert "SUCCESS" in content
```

---

### Phase 2: standalone.py の修正

**ファイル:** `standalone.py`

**変更前 (106-108行):**
```python
# Setup logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("lora-manager-standalone")
```

**変更後:**
```python
# Setup logging
from py.utils.logging_config import setup_logging
log_file = setup_logging(
    log_level=logging.INFO,
    console=True
)
logger = logging.getLogger("lora-manager-standalone")
logger.info(f"ComfyUI-Lora-Manager standalone mode started")
logger.info(f"Log file: {log_file}")
```

---

### Phase 3: 主要サービスへのログ強化

#### 3.1 CivitaiClient の修正

**ファイル:** `py/services/civitai_client.py`

**追加箇所:**
```python
from py.utils.logging_config import log_api_request, log_api_response

class CivitaiClient:
    # ... existing code ...

    async def _make_request(
        self,
        method: str,
        url: str,
        *,
        use_auth: bool = False,
        **kwargs,
    ) -> Tuple[bool, Dict | str]:
        """Wrapper around downloader.make_request that surfaces rate limits."""

        # Log request
        log_api_request(logger, method, url, auth=use_auth)

        downloader = await get_downloader()
        success, result = await downloader.make_request(
            method,
            url,
            use_auth=use_auth,
            **kwargs,
        )

        # Log response
        if success:
            log_api_response(logger, "SUCCESS",
                           result if isinstance(result, dict) else None)
        else:
            log_api_response(logger, f"ERROR: {result}")

        if not success and isinstance(result, RateLimitError):
            if result.provider is None:
                result.provider = "civitai_api"
            raise result
        return success, result
```

#### 3.2 MetadataService の修正

**ファイル:** `py/services/metadata_service.py`

**追加ログポイント:**
- メタデータ取得開始/完了
- ハッシュ計算開始/完了
- API呼び出し結果

```python
async def get_metadata_by_hash(self, file_hash: str) -> Optional[Dict]:
    """Get metadata by file hash"""
    logger.info(f"Getting metadata for hash: {file_hash[:16]}...")

    # ... existing code ...

    if metadata:
        logger.info(f"Metadata found: model_id={metadata.get('modelId')}, "
                   f"version_id={metadata.get('id')}")
    else:
        logger.warning(f"No metadata found for hash: {file_hash[:16]}...")

    return metadata
```

#### 3.3 ModelScanner の修正

**ファイル:** `py/services/model_scanner.py`

**追加ログポイント:**
- スキャン開始/完了
- ファイル数
- 処理時間

```python
async def scan_models(self, force_refresh: bool = False):
    """Scan for model files"""
    start_time = time.time()
    logger.info(f"Starting model scan (force_refresh={force_refresh})")

    # ... existing code ...

    elapsed = time.time() - start_time
    logger.info(f"Model scan completed: {len(results)} models in {elapsed:.2f}s")

    return results
```

---

## 実装スケジュール

### タスク一覧

1. **Phase 1-1:** `py/utils/logging_config.py` 作成 (30分)
2. **Phase 1-2:** テストケース作成 (20分)
3. **Phase 2:** `standalone.py` 修正 (10分)
4. **Phase 3-1:** `civitai_client.py` 修正 (20分)
5. **Phase 3-2:** `metadata_service.py` 修正 (15分)
6. **Phase 3-3:** `model_scanner.py` 修正 (15分)
7. **統合テスト:** 実機動作確認 (30分)

**合計推定時間:** 2時間20分

---

## テスト計画

### 単体テスト

1. **ログファイル生成テスト**
   - 正しいディレクトリに作成されるか
   - ファイル名形式が正しいか

2. **フォーマットテスト**
   - ISO 8601タイムスタンプ
   - API REQUEST/RESPONSEフォーマット

3. **エラーハンドリングテスト**
   - ログディレクトリ作成失敗時の動作
   - ファイル書き込み失敗時の動作

### 統合テスト

1. **standalone.py起動テスト**
   ```bash
   python standalone.py
   # ログファイルが作成されることを確認
   ls -la ../civitai_downloader/logs/lora_manager_*.log
   ```

2. **API呼び出しログテスト**
   - モデルスキャン実行
   - ログにAPI REQUEST/RESPONSEが記録されることを確認

3. **既存機能テスト**
   - モデル一覧表示
   - メタデータ取得
   - ダウンロード機能
   - すべて正常動作することを確認

---

## ロールバック計画

### 問題発生時の対処

1. **ログファイル作成失敗:**
   - コンソールログのみにフォールバック
   - エラーメッセージを表示して継続

2. **パフォーマンス低下:**
   - ログレベルをWARNINGに変更
   - 詳細ログを無効化

3. **完全ロールバック:**
   ```bash
   git checkout standalone.py
   rm py/utils/logging_config.py
   rm tests/utils/test_logging_config.py
   ```

---

## 完了基準

### 必須要件

- ✅ ログファイルが `/Users/kuniaki-k/Code/paperspace/civitai_downloader/logs/` に作成される
- ✅ ファイル名が `lora_manager_YYYYMMDD_HHMMSS.log` 形式
- ✅ API REQUEST/RESPONSEが civitai_downloader と同じフォーマットで記録される
- ✅ 既存機能がすべて正常動作する
- ✅ テストが全てパスする

### オプション要件

- ⭕ ログローテーション機能
- ⭕ ログレベルの動的変更
- ⭕ ログ検索/フィルタリング機能

---

## 参考資料

### ログサンプル

**civitai_downloader 出力例:**
```
[2025-10-18T18:10:17.600226] API REQUEST: GET https://civitai.com/api/v1/model-versions/by-hash/40a4971c6866cf919734b2036ac44a6c657b66a0350724b35dbeb572790826ff
  Auth: True

[2025-10-18T18:10:18.075238] API RESPONSE: SUCCESS
  Data: {
  "id": 2130994,
  "modelId": 1882733,
  "name": "v1.0 for IL",
  "nsfwLevel": 1,
  "baseModel": "Illustrious",
  ...
}
```

**期待される lora_manager 出力:**
```
[2025-10-19T14:30:45.123456] INFO: Logging initialized: /Users/kuniaki-k/Code/paperspace/civitai_downloader/logs/lora_manager_20251019_143045.log
[2025-10-19T14:30:45.234567] INFO: ComfyUI-Lora-Manager standalone mode started
[2025-10-19T14:30:46.345678] INFO: Starting model scan (force_refresh=False)
[2025-10-19T14:30:47.456789] API REQUEST: GET https://civitai.com/api/v1/model-versions/by-hash/abc123...
  Auth: True
[2025-10-19T14:30:47.567890] API RESPONSE: SUCCESS
  Data: {
  "id": 123456,
  "modelId": 789012,
  ...
}
[2025-10-19T14:30:48.678901] INFO: Model scan completed: 42 models in 2.33s
```

---

## 備考

- Python標準loggingモジュールを使用（外部依存なし）
- 非同期処理に対応
- UTF-8エンコーディングでファイル保存
- 大きなレスポンスは5000文字で切り詰め
