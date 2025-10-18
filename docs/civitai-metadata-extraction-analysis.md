# Civitai メタデータ抽出分析

ComfyUI-Lora-Managerのログデータを解析して、Civitai APIからメタデータを取得する実際の方法をドキュメント化しました。

## 概要

ComfyUI-Lora-Managerは、モデルファイルのSHA256ハッシュを使用してCivitai APIからメタデータを取得し、ダウンロードURLを抽出しています。

## 取得されたログ統計

- **APIリクエスト**: 29回
- **メタデータ抽出**: 29回  
- **ダウンロードURL抽出**: 14回
- **ログファイルサイズ**: 1.2MB（26,887行）

## API呼び出しパターン

### 1. ハッシュベースのモデル検索

```
GET https://civitai.com/api/v1/model-versions/by-hash/{SHA256_HASH}
Authorization: Bearer {API_KEY}
```

**例:**
```
GET https://civitai.com/api/v1/model-versions/by-hash/40a4971c6866cf919734b2036ac44a6c657b66a0350724b35dbeb572790826ff
```

### 2. モデル詳細情報の取得

```
GET https://civitai.com/api/v1/models/{MODEL_ID}
Authorization: Bearer {API_KEY}
```

**例:**
```
GET https://civitai.com/api/v1/models/1882733
```

## メタデータ構造

### モデルバージョン情報

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
  "trainingStatus": null,
  "trainingDetails": null,
  "baseModel": "Illustrious",
  "baseModelType": "Standard"
}
```

### ファイル情報

```json
{
  "files": [
    {
      "id": 2024928,
      "sizeKB": 56081.76171875,
      "name": "Robertlu1021_exusiai_the_new_covenant_arknights_v1.0-000010.safetensors",
      "type": "Model",
      "primary": true,
      "downloadUrl": "https://civitai.com/api/download/models/2130994"
    }
  ]
}
```

## ダウンロードURL抽出ロジック

### 1. プライマリファイルの特定

```python
def extract_download_urls(model_version):
    download_urls = []
    
    files = model_version.get('files', [])
    for file_info in files:
        if file_info.get('type') == 'Model' and file_info.get('primary'):
            # プライマリダウンロードURL
            if 'downloadUrl' in file_info and file_info['downloadUrl']:
                download_urls.append(file_info['downloadUrl'])
            
            # ミラーURL
            if 'mirrors' in file_info:
                for mirror in file_info['mirrors']:
                    if mirror.get('url') and not mirror.get('deletedAt'):
                        download_urls.append(mirror['url'])
    
    return download_urls
```

### 2. 抽出されたダウンロードURL例

```
Primary URL: https://civitai.com/api/download/models/2130994
Primary URL: https://civitai.com/api/download/models/2046073
Primary URL: https://civitai.com/api/download/models/2258841
```

## 認証とレート制限

### 認証ヘッダー

```
Authorization: Bearer {CIVITAI_API_KEY}
Content-Type: application/json
```

### レート制限対応

- リクエスト間隔の制御
- エラーハンドリング
- リトライ機能

## メタデータ抽出フロー

1. **SHA256ハッシュ計算** - モデルファイルのハッシュを計算
2. **API検索** - ハッシュでCivitai APIを検索
3. **モデル情報取得** - モデルIDから詳細情報を取得
4. **ダウンロードURL抽出** - プライマリファイルとミラーURLを抽出
5. **メタデータ統合** - 全ての情報を統合して保存

## 実装上の重要なポイント

### 1. ハッシュベース検索の利点

- ファイル名に依存しない
- バージョン固有の情報を取得
- 正確なモデル特定

### 2. ダウンロードURLの構造

```
https://civitai.com/api/download/models/{VERSION_ID}
```

### 3. ファイル情報の重要フィールド

- `type: "Model"` - モデルファイル
- `primary: true` - プライマリファイル
- `downloadUrl` - ダウンロードURL
- `sizeKB` - ファイルサイズ
- `name` - ファイル名

## エラーハンドリング

### 一般的なエラー

1. **認証エラー** (401)
2. **レート制限** (429)
3. **モデル未発見** (404)
4. **サーバーエラー** (500)

### 対応策

- 指数バックオフ
- リトライ機能
- エラーログ記録

## パフォーマンス最適化

### 1. バッチ処理

- 複数モデルの同時処理
- 非同期リクエスト

### 2. キャッシュ機能

- 取得済みメタデータのキャッシュ
- 重複リクエストの回避

### 3. レート制限対応

- リクエスト間隔の制御
- 並行処理数の制限

## セキュリティ考慮事項

### 1. APIキーの管理

- 環境変数での管理
- ログへの出力禁止

### 2. データ保護

- 個人情報の除外
- 機密情報のマスキング

## 今後の改善点

### 1. 機能拡張

- ミラーURLの活用
- バッチダウンロード対応
- 進捗表示の改善

### 2. エラー処理

- より詳細なエラー情報
- 自動復旧機能

### 3. パフォーマンス

- 並行処理の最適化
- キャッシュ戦略の改善

## 結論

ComfyUI-Lora-Managerは、SHA256ハッシュベースの検索とCivitai APIを活用して、効率的にメタデータを取得し、ダウンロードURLを抽出しています。この手法は、ファイル名に依存せず、正確なモデル特定を可能にする優れたアプローチです。

## 参考資料

- [Civitai API Documentation](https://civitai.com/api-docs)
- [ComfyUI-Lora-Manager Source Code](https://github.com/spacepxl/ComfyUI-Lora-Manager)
- [ログファイル](./logs/civitai_metadata_20251018_181000.log)
