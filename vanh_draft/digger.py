import base64
import json
from bson.binary import Binary
from typing import Optional, Any, List

class CheckpointDigger:
    def __init__(self, db, col_name: str = "checkpoints"):
        self.col = db[col_name]

    @staticmethod
    def _b64(binary_obj) -> str:
        return base64.b64encode(bytes(binary_obj)).decode()

    def iter_raw_messages(self, thread_id: Optional[str] = None):
        result = []
        query = {}
        if thread_id is not None:
            marker = f'"{thread_id}"'.encode("utf-8")
            query["metadata.thread_id"] = Binary(marker, 0)

        for doc in self.col.find(query):
            writes = doc.get("metadata", {}).get("writes", {})
            if not isinstance(writes, dict):
                continue
            start = writes.get("__start__")
            if isinstance(start, dict) and "messages" in start:
                user_b64 = self._b64(start["messages"])
                user_txt = self.decode_user_msg(user_b64)
                if user_txt:
                    result.append(user_txt)

            agent = writes.get("agent")
            if isinstance(agent, dict) and "messages" in agent:
                agent_b64 = self._b64(agent["messages"])
                agent_txt = self.decode_agent_msg(agent_b64)
                if agent_txt:
                    result.append(agent_txt)
        return result

    @staticmethod
    def base64_to_json(encoded_str: str) -> Any:
        """Base64 ➜ bytes ➜ utf-8 ➜ json.loads."""
        decoded_bytes = base64.b64decode(encoded_str)
        return json.loads(decoded_bytes.decode("utf-8"))

    @classmethod
    def decode_user_msg(cls, encoded_str: str) -> Optional[str]:
        obj = cls.base64_to_json(encoded_str)
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            return obj[0].get("content")
        return None

    @classmethod
    def decode_agent_msg(cls, encoded_str: str) -> Optional[str]:
        obj = cls.base64_to_json(encoded_str)
        if isinstance(obj, list) and obj:
            return obj[0].get("kwargs", {}).get("content")
        return None

    def __call__(self, thread_id: Optional[str] = None) -> List[str]:
        return self.iter_raw_messages(thread_id)

# ------------------------------ DEMO ------------------------------ #
if __name__ == "__main__":
    digger = CheckpointDigger()
    history = digger(thread_id="1")
    print(history)

