"""
Configuration Manager Module

config.jsonファイルの読み込みと設定管理
"""

import json
import os
from typing import Dict, Optional


class ConfigManager:
    """設定ファイルを管理するクラス"""
    
    def __init__(self, config_path: str = "config.json"):
        """
        ConfigManagerを初期化
        
        Args:
            config_path: 設定ファイルのパス
        """
        # スクリプトのディレクトリを基準にパスを解決
        if not os.path.isabs(config_path):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            self.config_path = os.path.join(script_dir, config_path)
        else:
            self.config_path = config_path
        
        self.config: Dict = {}
        self._load_config()
    
    def _load_config(self):
        """設定ファイルを読み込む"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(
                f"設定ファイルが見つかりません: {self.config_path}\n"
                f"config.json.exampleを参考にconfig.jsonを作成してください。"
            )
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"設定ファイルの形式が不正です: {str(e)}")
    
    def get_api_key(self) -> str:
        """
        Civitai APIキーを取得
        
        Returns:
            str: APIキー
            
        Raises:
            ValueError: APIキーが設定されていない場合
        """
        api_key = self.config.get('civitai_api_key', '')
        
        if not api_key or api_key == 'your_civitai_api_key_here':
            raise ValueError(
                "Civitai APIキーが設定されていません。\n"
                "config.jsonのcivitai_api_keyを設定してください。\n"
                "APIキーはCivitai.comのProfile > Account Settings > API Keysから取得できます。"
            )
        
        return api_key
    
    def get_download_path(self, model_type: str) -> str:
        """
        指定されたモデルタイプのダウンロードパスを取得
        
        Args:
            model_type: モデルタイプ ('lora', 'checkpoints', 'embedding')
            
        Returns:
            str: ダウンロードパス
        """
        download_paths = self.config.get('download_paths', {})
        
        if model_type not in download_paths:
            raise ValueError(f"モデルタイプ '{model_type}' のダウンロードパスが設定されていません")
        
        path = download_paths[model_type]
        
        # 相対パスの場合はスクリプトディレクトリを基準に解決
        if not os.path.isabs(path):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(script_dir, path)
        
        # ディレクトリが存在しない場合は作成
        os.makedirs(path, exist_ok=True)
        
        return path
    
    def get_history_file(self) -> str:
        """
        ダウンロード履歴ファイルのパスを取得
        
        Returns:
            str: 履歴ファイルのパス
        """
        history_file = self.config.get('download_history_file', './download_history.txt')
        
        # 相対パスの場合はスクリプトディレクトリを基準に解決
        if not os.path.isabs(history_file):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            history_file = os.path.join(script_dir, history_file)
        
        return history_file
    
    def validate(self) -> bool:
        """
        設定ファイルの内容を検証
        
        Returns:
            bool: 有効な場合True
        """
        try:
            # APIキーのチェック
            self.get_api_key()
            
            # ダウンロードパスのチェック
            for model_type in ['lora', 'checkpoints', 'embedding']:
                self.get_download_path(model_type)
            
            # 履歴ファイルのチェック
            self.get_history_file()
            
            return True
            
        except Exception as e:
            print(f"設定の検証に失敗: {str(e)}")
            return False


if __name__ == "__main__":
    # テスト
    try:
        config = ConfigManager("config.json")
        print("設定ファイル読み込み成功！")
        print(f"APIキー: {config.get_api_key()[:10]}...")
        print(f"LoRAダウンロードパス: {config.get_download_path('lora')}")
        print(f"履歴ファイル: {config.get_history_file()}")
    except Exception as e:
        print(f"エラー: {str(e)}")

