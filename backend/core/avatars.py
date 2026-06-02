"""
头像池工具 —— 随机分配预置头像

头像文件存储在 backend/static/avatars/ 下，由 FastAPI StaticFiles 以
/static/avatars/avatar-N.jpg 路径提供服务。

队伍：咕嘎一辈子队
"""

import random

AVATAR_POOL = [
    "/static/avatars/avatar-1.jpg",
    "/static/avatars/avatar-2.jpg",
    "/static/avatars/avatar-3.jpg",
    "/static/avatars/avatar-4.jpg",
    "/static/avatars/avatar-5.jpg",
    "/static/avatars/avatar-6.jpg",
    "/static/avatars/avatar-7.jpg",
    "/static/avatars/avatar-8.jpg",
    "/static/avatars/avatar-9.jpg",
    "/static/avatars/avatar-10.jpg",
    "/static/avatars/avatar-11.jpg",
    "/static/avatars/avatar-12.jpg",
    "/static/avatars/avatar-13.jpg",
    "/static/avatars/avatar-14.jpg",
    "/static/avatars/avatar-15.jpg",
    "/static/avatars/avatar-16.jpg",
    "/static/avatars/avatar-17.jpg",
    "/static/avatars/avatar-18.jpg",
]


def pick_random_avatar() -> str:
    """从预置头像池中随机返回一个路径。"""
    return random.choice(AVATAR_POOL)
