# ComfyUI-LoRA-Manager の settings.json 調査メモ

## 1. 調査対象
- リポジトリ: `/Users/kuniaki-k/Code/paperspace/ComfyUI-Lora-Manager`
- 調査項目:
  1. `settings.json` が初回に作成されるタイミング
  2. `settings.json` を読み込むタイミング

## 2. settings.json の生成タイミング
### 2.1 ComfyUI プラグインとして実行する場合
- `py/config.py` で `Config` クラスがインポート時に初期化される (`config = Config()`; 約行460)。
- `Config.__init__` 内で `standalone_mode` が偽なら `save_folder_paths_to_settings()` を呼び出す (`py/config.py` 行69-71)。
- `save_folder_paths_to_settings()` が `ensure_settings_file(logger)` を実行し、続いて `get_settings_manager()` を呼ぶ (`py/config.py` 行76-79)。
- `SettingsManager` 初期化時に以下が走る (`py/services/settings_manager.py` 行55-91)：
  - `ensure_settings_file` で保存パスを決定（ユーザー設定ディレクトリまたはプロジェクト直下の既存ファイル）。
  - `_load_settings()` がファイルを試読し、存在しない場合はデフォルト設定を作成。
  - `_ensure_default_settings()` が不足キーを補い `_save_settings()` を呼ぶため、初回はここでファイルが生成される。
- したがって **ComfyUI 連携モードでは、モジュールがロードされた直後に `settings.json` が作成** される。

### 2.2 スタンドアロンモード (`standalone.py`)
- 起動直後に `os.environ["LORA_MANAGER_STANDALONE"] = "1"` を設定し、`Config.__init__` 内の `save_folder_paths_to_settings()` がスキップされる。
- `validate_settings()` が `ensure_settings_file` で期待パスを取得し、ファイルが存在しない場合はエラーメッセージを出して終了 (`standalone.py` 行225-244)。
- そのため **スタンドアロンでは利用者が `settings.json.example` をコピーして手動作成するのが前提**。初回自動生成は行われない。

### 2.3 パス解決ロジック
- `ensure_settings_file` は以下を行う (`py/utils/settings_paths.py` 行51-83)：
  - プロジェクト直下の `settings.json` があればそれを優先（レガシー互換）。
  - なければ `platformdirs.user_config_dir("ComfyUI-LoRA-Manager")` 配下に `settings.json` を配置するためのディレクトリを作成し、フルパスを返す。

## 3. settings.json を読み込むタイミング
### 3.1 SettingsManager 初期化時
- `_load_settings()` が `json.load` でファイルを読み込む (`py/services/settings_manager.py` 行64-71)。
- 以降はメモリ上の `self.settings` が参照され、更新時は `_save_settings()` が書き戻し。

### 3.2 スタンドアロンモード特有の読み込み
- `MockFolderPaths.get_folder_paths()` が毎回 `settings.json` を開いてパスを取得 (`standalone.py` 行33-67)。
- `StandaloneServer.setup_routes()` もルーティング設定時に例示画像パスを読む (`standalone.py` 行161-175)。
- `validate_settings()` で存在確認とフォルダ検証のために読み込み (`standalone.py` 行225-259)。

### 3.3 更新系処理
- アップデータ (`py/routes/update_routes.py` 行126-145) は更新前後に `settings.json` をバックアップ・復元するためファイルを読み書きする。
- その他のサーバーモジュールは `get_settings_manager()` を経由してメモリ上の設定を利用し、直接ファイルを再読込するケースは上記以外に見当たらない。

## 4. 留意点
- `ensure_settings_file` はファイル自体を生成せずパス返却のみ。**実ファイル作成は SettingsManager の `_save_settings()` が担う**。
- レガシー環境から移行する場合、プロジェクト直下の `settings.json` が検出されるとそのまま使用される。
- スタンドアロンで自動生成したい場合は、`validate_settings()` の前に `SettingsManager` を強制初期化するなどの拡張が必要。

