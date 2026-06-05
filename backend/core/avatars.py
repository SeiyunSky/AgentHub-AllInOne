"""
头像池工具 —— 随机分配预置头像

头像文件存储在 backend/static/avatars/ 下，由 FastAPI StaticFiles 以
/static/avatars/avatar-N.jpg 路径提供服务。

队伍：咕嘎一辈子队
"""

import random

from backend.static.common import AVATAR_POOL


def pick_random_avatar() -> str:
    """从预置头像池中随机返回一个路径。"""
    return random.choice(AVATAR_POOL)
