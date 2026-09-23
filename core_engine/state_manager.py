import os
import json
import tempfile
import shutil
import pandas as pd
from typing import Dict, Any, Optional

class StateManager:
    """
    轻量级 JSON 原子快照持久化管理器。
    负责增量状态的安全存储、幂等防重与回退。
    """
    def __init__(self, base_dir: str = ".states"):
        self.base_dir = base_dir

    def get_state_dir(self, strategy_id: str, symbol: str, config_hash: str) -> str:
        return os.path.join(self.base_dir, strategy_id, symbol, config_hash)

    def _atomic_write_json(self, file_path: str, data: Dict[str, Any]):
        """
        原子写入 JSON，避免写入中断导致损坏
        """
        dir_name = os.path.dirname(file_path)
        os.makedirs(dir_name, exist_ok=True)
        
        fd, temp_path = tempfile.mkstemp(dir=dir_name, prefix="tmp_state_", suffix=".json")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # 原子重命名
            shutil.move(temp_path, file_path)
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e

    def save_checkpoint(self, strategy_id: str, symbol: str, config_hash: str, 
                        checkpoint_id: str, state_data: Dict[str, Any], prefix_hash: str = None):
        """
        保存检查点（一个完整交易日处理成功后调用）。
        """
        import hashlib
        if prefix_hash is None:
            # 如果没有传入前缀哈希，则使用状态内容的哈希作为 fallback
            state_str = json.dumps(state_data, sort_keys=True, ensure_ascii=False)
            prefix_hash = hashlib.sha256(state_str.encode('utf-8')).hexdigest()[:16]
            
        state_data['prefix_hash'] = prefix_hash
        state_dir = self.get_state_dir(strategy_id, symbol, config_hash)
        snapshots_dir = os.path.join(state_dir, "snapshots")
        os.makedirs(snapshots_dir, exist_ok=True)
        
        # 1. 写入快照文件
        snapshot_filename = f"{strategy_id}_{prefix_hash}.json"
        snapshot_path = os.path.join(snapshots_dir, snapshot_filename)
        self._atomic_write_json(snapshot_path, state_data)
        
        # 2. 更新 latest.json 指向最新快照
        latest_path = os.path.join(state_dir, "latest.json")
        latest_data = {
            "latest_checkpoint_id": checkpoint_id,
            "prefix_hash": prefix_hash,
            "snapshot_path": snapshot_path,
            "updated_at": pd.Timestamp.now().isoformat()
        }
        self._atomic_write_json(latest_path, latest_data)

    def load_latest_checkpoint(self, strategy_id: str, symbol: str, config_hash: str) -> Optional[Dict[str, Any]]:
        """
        加载最近有效的快照
        """
        state_dir = self.get_state_dir(strategy_id, symbol, config_hash)
        latest_path = os.path.join(state_dir, "latest.json")
        
        if not os.path.exists(latest_path):
            return None
            
        try:
            with open(latest_path, 'r', encoding='utf-8') as f:
                latest_data = json.load(f)
                
            snapshot_path = latest_data.get("snapshot_path")
            if snapshot_path and os.path.exists(snapshot_path):
                with open(snapshot_path, 'r', encoding='utf-8') as sf:
                    return json.load(sf)
        except Exception as e:
            print(f"Failed to load checkpoint: {e}")
            return None
            
        return None

    def verify_checkpoint(self, state_data: Dict[str, Any], current_config_hash: str, 
                          current_prefix_hash: str = None) -> bool:
        """
        验证检查点是否合法可以续接
        """
        # 1. 校验配置哈希兼容性
        if state_data.get('config_hash') != current_config_hash:
            print("Config hash mismatch, cannot resume.")
            return False
            
        # 2. 校验检查点处于完整提交状态
        if not state_data.get('is_complete', False):
            print("Checkpoint was not marked as complete.")
            return False
            
        # 3. 校验历史前缀未发生篡改
        if current_prefix_hash is not None:
            saved_prefix_hash = state_data.get('prefix_hash')
            if saved_prefix_hash != current_prefix_hash:
                print("Prefix hash mismatch (historical data or config changed), cannot resume.")
                return False
                
        return True
