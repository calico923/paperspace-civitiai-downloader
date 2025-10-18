# Civitai API エンドポイント リファレンス

ComfyUI-Lora-Managerのログ分析に基づく、実際に使用されているCivitai APIエンドポイントの詳細です。

## 認証

### APIキーの取得

1. [Civitai.com](https://civitai.com) にログイン
2. プロフィール設定 → API Keys
3. 新しいAPIキーを生成

### 認証ヘッダー

```http
Authorization: Bearer {YOUR_API_KEY}
Content-Type: application/json
```

## 主要エンドポイント

### 1. ハッシュベースモデル検索

**エンドポイント:** `GET /api/v1/model-versions/by-hash/{hash}`

**説明:** SHA256ハッシュを使用してモデルバージョンを検索

**パラメータ:**
- `hash` (string, required): モデルファイルのSHA256ハッシュ

**レスポンス例:**
```json
{
  "id": 2130994,
  "modelId": 1882733,
  "name": "v1.0 for IL",
  "nsfwLevel": 1,
  "createdAt": "2025-08-20T03:30:26.952Z",
  "updatedAt": "2025-08-20T04:49:13.017Z",
  "status": "Published",
  "publishedAt": "2025-08-20T04:49:12.992Z",
  "trainedWords": [
    "exusiai_the_new_covenant_\\(arknights\\), red hair, orange eyes..."
  ],
  "baseModel": "Illustrious",
  "baseModelType": "Standard",
  "files": [
    {
      "id": 2024928,
      "sizeKB": 56081.76171875,
      "name": "Robertlu1021_exusiai_the_new_covenant_arknights_v1.0-000010.safetensors",
      "type": "Model",
      "primary": true,
      "downloadUrl": "https://civitai.com/api/download/models/2130994"
    }
  ],
  "images": [
    {
      "url": "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/c19feb3f-7fda-4882-a339-b0dd93fd9983/original=true/95349645.jpeg",
      "nsfwLevel": 1,
      "width": 1536,
      "height": 2688,
      "hash": "UCGHb$Io8^~BEKtRX-IA00wIKOEl=GM{iwxu",
      "type": "image"
    }
  ]
}
```

### 2. モデル詳細情報取得

**エンドポイント:** `GET /api/v1/models/{modelId}`

**説明:** モデルIDから詳細情報を取得

**パラメータ:**
- `modelId` (integer, required): モデルID

**レスポンス例:**
```json
{
  "id": 1882733,
  "name": "Exusiai The New Covenant (Arknights)",
  "description": "A LoRA model for Exusiai from Arknights...",
  "type": "LORA",
  "nsfw": false,
  "tags": ["anime", "arknights", "exusiai"],
  "creator": {
    "username": "robertlu1021",
    "image": "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/eb7b7975-4c26-4b57-88d2-f2f2f8176fab/width=96/robertlu1021.jpeg"
  },
  "stats": {
    "downloadCount": 1234,
    "favoriteCount": 567,
    "commentCount": 89
  }
}
```

### 3. モデル一覧取得

**エンドポイント:** `GET /api/v1/models`

**説明:** モデル一覧を取得（ページネーション対応）

**クエリパラメータ:**
- `limit` (integer, optional): 取得件数（デフォルト: 10, 最大: 100）
- `page` (integer, optional): ページ番号（デフォルト: 1）
- `types` (string, optional): モデルタイプ（LORA, Checkpoint, etc.）
- `nsfw` (boolean, optional): NSFWコンテンツの包含
- `sort` (string, optional): ソート順（Most Downloaded, Newest, etc.）

**レスポンス例:**
```json
{
  "items": [
    {
      "id": 1882733,
      "name": "Exusiai The New Covenant (Arknights)",
      "type": "LORA",
      "nsfw": false,
      "creator": {
        "username": "robertlu1021"
      },
      "stats": {
        "downloadCount": 1234
      }
    }
  ],
  "metadata": {
    "totalItems": 1000,
    "currentPage": 1,
    "pageSize": 10,
    "totalPages": 100
  }
}
```

## ダウンロードURL構造

### プライマリダウンロードURL

```
https://civitai.com/api/download/models/{versionId}
```

**例:**
```
https://civitai.com/api/download/models/2130994
```

### ミラーURL

一部のモデルにはミラーURLが提供される場合があります：

```json
{
  "files": [
    {
      "id": 2024928,
      "type": "Model",
      "primary": true,
      "downloadUrl": "https://civitai.com/api/download/models/2130994",
      "mirrors": [
        {
          "url": "https://mirror1.example.com/download",
          "deletedAt": null
        },
        {
          "url": "https://mirror2.example.com/download",
          "deletedAt": null
        }
      ]
    }
  ]
}
```

## エラーレスポンス

### 一般的なエラーコード

| ステータスコード | 説明 | 対応方法 |
|----------------|------|----------|
| 200 | 成功 | - |
| 400 | 不正なリクエスト | パラメータを確認 |
| 401 | 認証エラー | APIキーを確認 |
| 403 | アクセス拒否 | 権限を確認 |
| 404 | リソース未発見 | モデルが存在しない |
| 429 | レート制限 | リクエスト間隔を調整 |
| 500 | サーバーエラー | しばらく待ってから再試行 |

### エラーレスポンス例

```json
{
  "error": "Model not found",
  "message": "The requested model version does not exist",
  "statusCode": 404
}
```

## レート制限

### 制限事項

- **認証済みユーザー**: 1分間に60リクエスト
- **未認証ユーザー**: 1分間に10リクエスト
- **バースト制限**: 短時間での大量リクエストは制限される

### レート制限ヘッダー

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1640995200
```

### レート制限対応

```python
import asyncio
import time

class RateLimiter:
    def __init__(self, max_requests=60, time_window=60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    async def wait_if_needed(self):
        now = time.time()
        # 古いリクエストを削除
        self.requests = [req_time for req_time in self.requests 
                        if now - req_time < self.time_window]
        
        if len(self.requests) >= self.max_requests:
            sleep_time = self.time_window - (now - self.requests[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        self.requests.append(now)
```

## 実装例

### Python (aiohttp)

```python
import aiohttp
import asyncio

async def get_model_by_hash(api_key: str, model_hash: str):
    url = f"https://civitai.com/api/v1/model-versions/by-hash/{model_hash}"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"Error: {response.status}")
                return None

# 使用例
async def main():
    api_key = "your_api_key"
    model_hash = "40a4971c6866cf919734b2036ac44a6c657b66a0350724b35dbeb572790826ff"
    
    result = await get_model_by_hash(api_key, model_hash)
    if result:
        print(f"Model: {result['name']}")
        print(f"Download URL: {result['files'][0]['downloadUrl']}")

asyncio.run(main())
```

### Python (requests)

```python
import requests

def get_model_by_hash(api_key: str, model_hash: str):
    url = f"https://civitai.com/api/v1/model-versions/by-hash/{model_hash}"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        return None

# 使用例
api_key = "your_api_key"
model_hash = "40a4971c6866cf919734b2036ac44a6c657b66a0350724b35dbeb572790826ff"

result = get_model_by_hash(api_key, model_hash)
if result:
    print(f"Model: {result['name']}")
    print(f"Download URL: {result['files'][0]['downloadUrl']}")
```

## ベストプラクティス

### 1. エラーハンドリング

```python
async def safe_api_call(url, headers):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    # レート制限 - 指数バックオフ
                    await asyncio.sleep(60)
                    return await safe_api_call(url, headers)
                else:
                    logger.error(f"API Error: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return None
```

### 2. キャッシュ機能

```python
import json
from pathlib import Path

class APICache:
    def __init__(self, cache_dir="cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    def get_cache_path(self, key):
        return self.cache_dir / f"{key}.json"
    
    def get(self, key):
        cache_path = self.get_cache_path(key)
        if cache_path.exists():
            with open(cache_path, 'r') as f:
                return json.load(f)
        return None
    
    def set(self, key, data):
        cache_path = self.get_cache_path(key)
        with open(cache_path, 'w') as f:
            json.dump(data, f)
```

### 3. バッチ処理

```python
async def process_models_batch(api_key, model_hashes, batch_size=5):
    semaphore = asyncio.Semaphore(batch_size)
    
    async def process_single(hash_value):
        async with semaphore:
            return await get_model_by_hash(api_key, hash_value)
    
    tasks = [process_single(hash_value) for hash_value in model_hashes]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return [r for r in results if not isinstance(r, Exception)]
```

## まとめ

このリファレンスを使用して、Civitai APIを効率的に活用できます。主要なポイント：

1. **認証**: Bearer トークンを使用
2. **ハッシュ検索**: SHA256ハッシュでモデルを特定
3. **レート制限**: 適切な間隔でリクエスト
4. **エラーハンドリング**: 堅牢なエラー処理
5. **キャッシュ**: 重複リクエストの回避

ComfyUI-Lora-Managerの実装を参考に、同様の機能を構築できます。
