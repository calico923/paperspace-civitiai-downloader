"""
Model Type Classifier

Civitai APIのメタデータからモデルタイプを自動判定する機能
ComfyUI-Lora-Managerの実装を参考に作成
"""

from typing import Optional, Dict, Tuple
import logging

logger = logging.getLogger(__name__)

class ModelTypeClassifier:
    """モデルタイプを自動判定するクラス"""
    
    # ComfyUI-Lora-Managerから移植した定数
    VALID_LORA_TYPES = ['lora', 'locon', 'dora']
    SUPPORTED_MODEL_TYPES = [
        *VALID_LORA_TYPES,
        'textualinversion',
        'checkpoint',
    ]
    
    def __init__(self):
        """ModelTypeClassifierを初期化"""
        pass
    
    def classify_from_metadata(self, version_info: Dict) -> Tuple[Optional[str], str]:
        """
        Civitai APIのメタデータからモデルタイプを判定
        
        Args:
            version_info: Civitai APIから取得したバージョン情報
            
        Returns:
            Tuple[Optional[str], str]: (判定されたモデルタイプ, 判定理由)
        """
        try:
            # モデルタイプを取得
            model_type_from_info = version_info.get('model', {}).get('type', '').lower()
            
            if not model_type_from_info:
                return None, "モデルタイプ情報が見つかりません"
            
            # ComfyUI-Lora-Managerの分類ロジックを適用
            if model_type_from_info == 'checkpoint':
                return 'checkpoint', f"APIから判定: {model_type_from_info}"
            elif model_type_from_info in self.VALID_LORA_TYPES:
                return 'lora', f"APIから判定: {model_type_from_info} (LoRA系)"
            elif model_type_from_info == 'textualinversion':
                return 'embedding', f"APIから判定: {model_type_from_info}"
            else:
                return None, f"サポートされていないモデルタイプ: {model_type_from_info}"
                
        except Exception as e:
            logger.error(f"モデルタイプ判定エラー: {str(e)}")
            return None, f"判定エラー: {str(e)}"
    
    def validate_model_type(self, model_type: str) -> bool:
        """
        モデルタイプが有効かチェック
        
        Args:
            model_type: チェックするモデルタイプ
            
        Returns:
            bool: 有効な場合True
        """
        return model_type in ['lora', 'checkpoint', 'embedding']
    
    def get_supported_types(self) -> list:
        """
        サポートされているモデルタイプのリストを取得
        
        Returns:
            list: サポートされているモデルタイプのリスト
        """
        return ['lora', 'checkpoint', 'embedding']
    
    def get_type_mapping(self) -> Dict[str, list]:
        """
        モデルタイプのマッピングを取得
        
        Returns:
            Dict[str, list]: モデルタイプのマッピング
        """
        return {
            'lora': self.VALID_LORA_TYPES,
            'checkpoint': ['checkpoint'],
            'embedding': ['textualinversion']
        }


def test_classifier():
    """分類器のテスト"""
    classifier = ModelTypeClassifier()
    
    # テストケース
    test_cases = [
        {
            'name': 'LoRA',
            'version_info': {'model': {'type': 'lora'}},
            'expected': 'lora'
        },
        {
            'name': 'LoCon',
            'version_info': {'model': {'type': 'locon'}},
            'expected': 'lora'
        },
        {
            'name': 'Checkpoint',
            'version_info': {'model': {'type': 'checkpoint'}},
            'expected': 'checkpoint'
        },
        {
            'name': 'TextualInversion',
            'version_info': {'model': {'type': 'textualinversion'}},
            'expected': 'embedding'
        },
        {
            'name': 'Unknown',
            'version_info': {'model': {'type': 'unknown'}},
            'expected': None
        }
    ]
    
    print("🧪 ModelTypeClassifier テスト開始")
    print("=" * 50)
    
    for test_case in test_cases:
        result, reason = classifier.classify_from_metadata(test_case['version_info'])
        expected = test_case['expected']
        
        status = "✅" if result == expected else "❌"
        print(f"{status} {test_case['name']}: {result} (期待: {expected}) - {reason}")
    
    print("=" * 50)
    print("🎉 テスト完了!")


if __name__ == "__main__":
    test_classifier()
