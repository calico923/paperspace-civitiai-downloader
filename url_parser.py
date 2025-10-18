"""
Civitai URL Parser Module

URLからmodel IDとmodel version IDを抽出するユーティリティ
"""

from urllib.parse import urlparse, parse_qs
from typing import Optional, Tuple
import re


class CivitaiURLParser:
    """Civitai URLを解析してモデル情報を抽出するクラス"""
    
    @staticmethod
    def parse_url(url: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Civitai URLを解析してmodel IDとmodel version IDを抽出
        
        対応フォーマット:
        1. https://civitai.com/models/649516
        2. https://civitai.com/models/649516?modelVersionId=726676
        3. https://civitai.com/models/649516/model-name?modelVersionId=726676
        
        Args:
            url: Civitai URL
            
        Returns:
            Tuple[Optional[int], Optional[int]]: (model_id, model_version_id)
        """
        try:
            parsed_url = urlparse(url)
            
            # Extract model ID from path
            path_match = re.search(r'/models/(\d+)', parsed_url.path)
            model_id = int(path_match.group(1)) if path_match else None
            
            # Extract model version ID from query parameters
            query_params = parse_qs(parsed_url.query)
            model_version_id = None
            if 'modelVersionId' in query_params:
                try:
                    model_version_id = int(query_params['modelVersionId'][0])
                except (ValueError, IndexError):
                    pass
            
            return model_id, model_version_id
            
        except Exception as e:
            raise ValueError(f"Invalid Civitai URL: {url}. Error: {str(e)}")
    
    @staticmethod
    def validate_model_type(model_type: str) -> bool:
        """
        モデルタイプが有効かチェック
        
        Args:
            model_type: モデルタイプ ('lora', 'checkpoint', 'embedding')
            
        Returns:
            bool: 有効な場合True
        """
        valid_types = ['lora', 'checkpoint', 'embedding']
        return model_type.lower() in valid_types


if __name__ == "__main__":
    # テスト
    parser = CivitaiURLParser()
    
    test_urls = [
        "https://civitai.com/models/649516",
        "https://civitai.com/models/649516?modelVersionId=726676",
        "https://civitai.com/models/649516/model-name?modelVersionId=726676",
    ]
    
    for url in test_urls:
        model_id, version_id = parser.parse_url(url)
        print(f"URL: {url}")
        print(f"  Model ID: {model_id}, Version ID: {version_id}")
        print()

