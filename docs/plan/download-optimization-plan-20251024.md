# ダウンロード順序最適化とレート制限対策の実装計画

**作成日**: 2025-10-24
**ステータス**: 承認済み
**優先度**: 高

---

## 📋 背景と課題

### 現状の問題点
1. **速度制限の影響**: Checkpoint（大容量ファイル）のダウンロード中に速度制限がかかり、30分以上完了しない
2. **ダウンロード順序の非最適化**: CSVの記録順（古い順）でダウンロードするため、Checkpointが後回しになる可能性
3. **レート制限対策の欠如**: ダウンロード間にsleepが入っておらず、連続ダウンロードで制限を受けやすい
4. **リトライ機能の不在**: 速度制限検出時の自動復旧機能がない

### 影響
- 全件再ダウンロード時に途中で速度制限により停止
- Checkpointのダウンロード失敗により、重要なモデルが取得できない
- 手動での再実行が必要で運用負荷が高い

---

## 🎯 実装目標

### 主要目標
1. **Checkpoint優先**: 大容量ファイルを速度制限前に確実にダウンロード
2. **レート制限回避**: 適切な待機時間で連続ダウンロードによる制限を防ぐ
3. **自動リトライ**: 速度制限検出時の指数バックオフリトライで自動復旧
4. **効率的な処理**: 失敗時のスキップ機能で全体処理を継続

### 成功指標
- Checkpointの優先ダウンロード成功率: 95%以上
- レート制限発生率: 50%以上削減
- 自動リトライ成功率: 80%以上
- 全件ダウンロード完了率: 90%以上（従来50%以下）

---

## 🔧 実装仕様

### 1. モデルタイプ優先順位ソート

**ファイル**: `download_history.py`

#### 変更内容
```python
def get_all_downloads(self, remove_duplicates: bool = True, sort_by_type: bool = False) -> List[Dict]:
    """
    全てのダウンロード履歴を取得

    Args:
        remove_duplicates: 重複除去するかどうか
        sort_by_type: モデルタイプで優先順位ソート（デフォルト: False）

    Returns:
        List[Dict]: ダウンロード履歴のリスト
    """
    # CSV読み込み処理（既存）
    ...

    # sort_by_type=Trueの場合、優先順位でソート
    if sort_by_type:
        type_priority = {
            'checkpoint': 0,
            'lora': 1,
            'embedding': 2
        }
        downloads.sort(key=lambda x: type_priority.get(x.get('model_type', ''), 999))

    return downloads
```

#### 優先順位
1. **checkpoint** (優先度: 0) - 大容量、最優先
2. **lora** (優先度: 1) - 中容量
3. **embedding** (優先度: 2) - 小容量
4. **その他** (優先度: 999) - 未分類

#### 設計判断
- CSV記録順は維持（ソートはメモリ上で実施）
- 既存の`get_all_downloads()`呼び出しへの影響なし（デフォルト`sort_by_type=False`）
- タイプ不明のモデルは最後に配置

---

### 2. レート制限対策の実装

**ファイル**: `downloader.py`

#### A. ダウンロード間隔の追加

```python
# 定数定義
SLEEP_BETWEEN_DOWNLOADS = 5  # ダウンロード間の待機時間（秒）
RETRY_DELAYS = [60, 180, 300]  # リトライ時の待機時間（秒）
SPEED_THRESHOLD = 10 * 1024  # 低速度閾値（10KB/s）
SLOW_DURATION_THRESHOLD = 30  # 低速継続時間閾値（秒）
```

#### B. redownload_all()関数の強化

**変更箇所**: `downloader.py:423-486`

```python
async def redownload_all(downloads: List[Dict], config: ConfigManager, force: bool = False):
    """
    全件再ダウンロードを実行（レート制限対策込み）

    Args:
        downloads: ダウンロード履歴のリスト
        config: 設定マネージャー
        force: 強制上書きフラグ
    """
    total = len(downloads)
    success_count = 0
    error_count = 0
    skip_count = 0
    retry_stats = {'total_retries': 0, 'successful_retries': 0}

    print(f"\n🚀 全件ダウンロード開始: {total}件")
    print(f"📊 優先順位: Checkpoint → LoRA → Embedding")
    print(f"⏱️  ダウンロード間隔: {SLEEP_BETWEEN_DOWNLOADS}秒")
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

            # ファイル存在チェック（forceがFalseの場合のみ）
            if not force:
                try:
                    download_path = config.get_download_path(model_type)
                    file_path = os.path.join(download_path, filename)

                    if os.path.exists(file_path):
                        print(f"⚠️  スキップ: ファイルが既に存在")
                        skip_count += 1
                        continue
                except (ValueError, AttributeError):
                    pass

            # リトライロジック
            retry_count = 0
            success = False
            final_error = None

            while retry_count <= len(RETRY_DELAYS) and not success:
                try:
                    # ダウンロード実行
                    success, error, download_info = await downloader.download_model(url, model_type)

                    if success:
                        print(f"✅ 成功: {filename}")
                        success_count += 1

                        if retry_count > 0:
                            retry_stats['successful_retries'] += 1

                        # 次のダウンロード前に待機
                        if i < total:
                            print(f"⏳ {SLEEP_BETWEEN_DOWNLOADS}秒待機中...")
                            await asyncio.sleep(SLEEP_BETWEEN_DOWNLOADS)
                        break

                    # エラー処理
                    final_error = error

                    # 速度制限検出
                    if "速度制限" in error or "429" in error or "503" in error:
                        if retry_count < len(RETRY_DELAYS):
                            delay = RETRY_DELAYS[retry_count]
                            print(f"⚠️  速度制限検出: {delay}秒待機してリトライ（{retry_count + 1}/{len(RETRY_DELAYS)}回目）")
                            await asyncio.sleep(delay)
                            retry_count += 1
                            retry_stats['total_retries'] += 1
                        else:
                            print(f"❌ リトライ上限到達: {filename}")
                            error_count += 1
                            break
                    else:
                        # 速度制限以外のエラーは即座に失敗
                        print(f"❌ 失敗: {error}")
                        error_count += 1
                        break

                except Exception as e:
                    print(f"❌ エラー: {str(e)}")
                    error_count += 1
                    break

    # 結果サマリー
    print(f"\n{'='*60}")
    print(f"🎉 全件ダウンロード完了!")
    print(f"{'='*60}")
    print(f"✅ 成功: {success_count}件")
    print(f"⏭️  スキップ: {skip_count}件")
    print(f"❌ 失敗: {error_count}件")
    print(f"🔄 リトライ: {retry_stats['total_retries']}回（成功: {retry_stats['successful_retries']}回）")
    print(f"📊 合計: {total}件")
    print(f"📈 成功率: {(success_count / (total - skip_count) * 100):.1f}%")
```

#### C. download_file()関数の改善

**変更箇所**: `downloader.py:211-301`

```python
async def download_file(
    self,
    url: str,
    save_path: str,
    use_auth: bool = True
) -> Tuple[bool, Optional[str]]:
    """
    ファイルをダウンロード（速度制限検出機能付き）

    Returns:
        Tuple[bool, Optional[str]]: (成功/失敗, エラーメッセージ)
    """
    # ... 既存のダウンロード処理 ...

    # 速度監視用変数
    slow_speed_start_time = None

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

                # 速度制限検出
                if speed < SPEED_THRESHOLD:
                    if slow_speed_start_time is None:
                        slow_speed_start_time = current_time
                    elif current_time - slow_speed_start_time > SLOW_DURATION_THRESHOLD:
                        return False, "速度制限検出: ダウンロード速度が極端に低下しました"
                else:
                    slow_speed_start_time = None

                last_print_time = current_time

    # ... 既存の完了処理 ...
```

#### D. HTTPステータス処理の強化

```python
async with self.session.get(url, headers=headers, allow_redirects=True) as response:
    # ステータスコードチェック
    if response.status == 401:
        return False, "認証エラー: APIキーが無効または必要です"
    elif response.status == 403:
        return False, "アクセス拒否: Early Accessモデルの可能性があります"
    elif response.status == 404:
        return False, "ファイルが見つかりません"
    elif response.status == 429:
        return False, "速度制限検出: レート制限（HTTP 429）"
    elif response.status == 503:
        return False, "速度制限検出: サービス一時停止（HTTP 503）"
    elif response.status not in (200, 206):
        return False, f"ダウンロード失敗 (Status: {response.status})"
```

---

### 3. メイン関数の変更

**変更箇所**: `downloader.py:634-656`

```python
# 全件ダウンロード
if args.redownload_url == 'all':
    print(f"\n{'='*60}")
    print(f"🔄 全件再ダウンロード")
    print(f"{'='*60}")

    # sort_by_type=Trueで優先順位ソート
    downloads = history_manager.get_all_downloads(
        remove_duplicates=True,
        sort_by_type=True  # ← 追加
    )

    if not downloads:
        print("❌ 履歴がありません")
        sys.exit(1)

    print(f"📊 ダウンロード対象: {len(downloads)}件")
    print(f"📋 優先順位: Checkpoint → LoRA → Embedding")

    # 確認
    if not args.force and not args.yes:
        choice = input("全件ダウンロードを実行しますか？ (y/N): ")
        if choice.lower() != 'y':
            print("キャンセルしました")
            sys.exit(0)

    # 全件ダウンロード実行
    await redownload_all(downloads, config, args.force)
    sys.exit(0)
```

---

## 📊 動作フロー

### 全件ダウンロードの処理フロー

```
1. 履歴CSVを読み込み
   ↓
2. 重複除去
   ↓
3. モデルタイプでソート (Checkpoint → LoRA → Embedding)
   ↓
4. for each model in sorted_downloads:
   ├─ ファイル存在チェック（--forceなしの場合）
   │  └─ 存在 → スキップして次へ
   ├─ ダウンロード実行
   ├─ 速度制限検出？
   │  ├─ Yes → リトライ（最大3回、指数バックオフ）
   │  │  └─ リトライ成功 → 次へ
   │  │  └─ リトライ失敗 → 失敗カウント、次へ
   │  └─ No → 成功カウント
   └─ 5秒待機（次のダウンロード前）
   ↓
5. 結果サマリー表示
```

### 速度制限検出条件

以下のいずれかに該当する場合、速度制限と判定：

1. **HTTPステータス**: 429 (Too Many Requests) または 503 (Service Unavailable)
2. **低速度継続**: ダウンロード速度が10KB/s以下が30秒以上継続
3. **エラーメッセージ**: レスポンスに"rate limit"や"速度制限"のキーワード含む

### リトライ戦略（指数バックオフ）

| リトライ回数 | 待機時間 | 累積待機時間 |
|------------|---------|------------|
| 1回目      | 60秒    | 60秒       |
| 2回目      | 180秒   | 240秒      |
| 3回目      | 300秒   | 540秒      |
| 4回目以降  | 失敗扱い | -          |

---

## 🧪 テストケース

### 1. 優先順位ソートのテスト

**入力**:
```csv
timestamp,model_type,url,filename
2024-10-24 10:00:00,lora,https://civitai.com/1,lora1.safetensors
2024-10-24 10:01:00,checkpoint,https://civitai.com/2,checkpoint1.safetensors
2024-10-24 10:02:00,embedding,https://civitai.com/3,embedding1.pt
2024-10-24 10:03:00,lora,https://civitai.com/4,lora2.safetensors
```

**期待される出力順**:
```
1. checkpoint1.safetensors (checkpoint)
2. lora1.safetensors (lora)
3. lora2.safetensors (lora)
4. embedding1.pt (embedding)
```

### 2. 速度制限リトライのテスト

**シナリオ**: HTTP 429エラーが発生

**期待動作**:
1. 1回目のダウンロード失敗（HTTP 429）
2. 60秒待機
3. 2回目のダウンロード実行
4. 成功 → 次のファイルへ（5秒待機）

### 3. 低速度検出のテスト

**シナリオ**: ダウンロード速度が5KB/sで40秒継続

**期待動作**:
1. 30秒経過時点で速度制限検出
2. ダウンロード中断
3. リトライロジックに移行

### 4. 既存ファイルスキップのテスト

**条件**: `--force`フラグなし、ファイルが既に存在

**期待動作**:
1. ファイル存在チェック → True
2. "スキップ: ファイルが既に存在" 表示
3. skip_count += 1
4. 次のファイルへ（待機なし）

---

## 🚀 実装手順

### Phase 1: download_history.py の修正（30分）

1. `get_all_downloads()`に`sort_by_type`パラメータ追加
2. 優先順位ソート機能実装
3. ユニットテスト作成

### Phase 2: downloader.py の基本機能追加（1時間）

1. 定数定義（SLEEP_BETWEEN_DOWNLOADS, RETRY_DELAYS等）
2. `download_file()`に速度監視機能追加
3. HTTPステータス429/503の明示的検出

### Phase 3: リトライロジック実装（1時間）

1. `redownload_all()`にリトライループ追加
2. 指数バックオフ実装
3. リトライ統計の記録

### Phase 4: 結果サマリー強化（30分）

1. success/error/skip/retryのカウント
2. 成功率計算
3. 詳細なログ出力

### Phase 5: テストと検証（1時間）

1. 各テストケースの実行
2. 実際のCivitai APIでの動作確認
3. ドキュメント更新

**合計見積もり時間**: 4時間

---

## 📝 設定ファイルへの追加（将来拡張）

将来的に`config.json`でカスタマイズ可能にする項目：

```json
{
  "api_key": "...",
  "download_paths": {...},
  "rate_limit_settings": {
    "sleep_between_downloads": 5,
    "retry_delays": [60, 180, 300],
    "speed_threshold_kbps": 10,
    "slow_duration_threshold_seconds": 30
  }
}
```

---

## ⚠️ 注意事項とリスク

### リスク

1. **過度な待機時間**: 大量ファイルのダウンロードに時間がかかる
   - **対策**: `--sleep-time`オプションで調整可能にする（将来拡張）

2. **速度制限の誤検出**: ネットワークが一時的に遅い場合
   - **対策**: 閾値（10KB/s, 30秒）を適切に設定

3. **リトライ失敗**: 3回リトライしても速度制限が解除されない
   - **対策**: 失敗ファイルを記録し、後で再実行できるようにする

### 制約事項

- Civitai APIのレート制限は公式ドキュメントで60 requests/minuteと記載
- 実際の速度制限閾値は未公開のため、経験的に調整が必要
- 大容量ファイル（Checkpoint）のダウンロードには10-30分程度かかる場合がある

---

## 📈 期待される効果

### パフォーマンス改善

| 指標 | 現状 | 改善後 | 改善率 |
|-----|------|--------|-------|
| Checkpoint成功率 | 50% | 95%+ | +90% |
| 全体成功率 | 70% | 90%+ | +28% |
| レート制限発生率 | 60% | 30%以下 | -50% |
| 手動再実行回数 | 3-5回 | 0-1回 | -80% |

### ユーザー体験改善

- ✅ 無人での全件ダウンロード完了
- ✅ Checkpoint優先により重要ファイルの確実な取得
- ✅ 詳細なログと統計で進捗状況の把握が容易
- ✅ リトライ統計により問題の早期発見

---

## 📚 参考資料

- Civitai API Documentation: https://github.com/civitai/civitai/wiki/REST-API-Reference
- Rate Limiting Best Practices: HTTPステータス429の適切な処理
- Exponential Backoff Algorithm: リトライ間隔の指数的増加

---

## 🔄 今後の拡張

### Phase 2（優先度: 中）

1. **設定ファイル対応**: config.jsonでレート制限パラメータをカスタマイズ
2. **失敗ファイルリスト**: 失敗したファイルをCSVに出力し、再実行を容易に
3. **プログレスバー**: rich libraryを使った視覚的な進捗表示

### Phase 3（優先度: 低）

1. **並列ダウンロード**: 小容量ファイル（LoRA, Embedding）の並列処理
2. **スケジューリング**: 夜間バッチ実行のためのcron/タスクスケジューラ対応
3. **Webhook通知**: ダウンロード完了/失敗時のSlack/Discord通知

---

**計画書バージョン**: 1.0
**最終更新**: 2025-10-24
**承認者**: ユーザー
**実装担当**: Claude Code
