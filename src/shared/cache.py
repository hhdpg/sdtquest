"""LRU 缓存模块。

提供基于内存的 LRU（Least Recently Used）缓存实现，
用于相似问题缓存、检索结果缓存等场景。

主要类:
- LRUCache: 线程安全的 LRU 缓存

典型用法:
    >>> from src.shared.cache import LRUCache
    >>> cache = LRUCache[str, str](max_size=100, ttl_seconds=300)
    >>> cache.put("key", "value")
    >>> cache.get("key")
    'value'
"""

import threading
import time
from collections import OrderedDict
from typing import Generic, TypeVar

from loguru import logger


K = TypeVar("K")
V = TypeVar("V")


class LRUCache(Generic[K, V]):
    """
    线程安全的 LRU 缓存。

    特性:
    - 基于 OrderedDict 实现 O(1) 的存取和淘汰
    - 支持 TTL 过期机制
    - 线程安全（使用 threading.Lock）
    - 可选的命中统计

    Attributes:
        max_size: 缓存最大容量
        ttl_seconds: 条目过期时间（秒），0 表示不过期
        hits: 缓存命中次数
        misses: 缓存未命中次数

    Example:
        >>> cache = LRUCache[str, str](max_size=100, ttl_seconds=300)
        >>> cache.put("question_1", "answer_1")
        >>> cache.get("question_1")
        'answer_1'
        >>> cache.stats()
        {'size': 1, 'max_size': 100, 'hits': 1, 'misses': 0, 'hit_rate': 1.0}
    """

    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: int = 0,
        name: str = "default",
    ):
        """
        初始化 LRU 缓存。

        Args:
            max_size: 缓存最大容量
            ttl_seconds: 条目过期时间（秒），0 表示不过期
            name: 缓存名称（用于日志区分）
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.name = name

        self._data: OrderedDict[K, tuple[V, float]] = OrderedDict()
        self._lock = threading.Lock()

        # 统计
        self.hits = 0
        self.misses = 0

        logger.debug(
            "LRUCache 初始化 | name={} | max_size={} | ttl={}s",
            name, max_size, ttl_seconds,
        )

    def get(self, key: K) -> V | None:
        """
        获取缓存条目

        如果条目存在且未过期，将其移到最近使用位置。

        Args:
            key: 缓存键

        Returns:
            缓存值，未命中或已过期返回 None
        """
        with self._lock:
            if key not in self._data:
                self.misses += 1
                return None

            value, timestamp = self._data[key]

            # 检查过期
            if self.ttl_seconds > 0:
                age = time.time() - timestamp
                if age > self.ttl_seconds:
                    del self._data[key]
                    self.misses += 1
                    logger.debug("缓存过期 | name={} | key={}", self.name, key)
                    return None

            # 移到最近使用位置
            self._data.move_to_end(key)
            self.hits += 1
            return value

    def put(self, key: K, value: V) -> None:
        """
        添加或更新缓存条目

        如果缓存已满，淘汰最久未使用的条目。

        Args:
            key: 缓存键
            value: 缓存值
        """
        with self._lock:
            if key in self._data:
                # 更新现有条目
                self._data.move_to_end(key)
                self._data[key] = (value, time.time())
            else:
                # 添加新条目
                if len(self._data) >= self.max_size:
                    # 淘汰最久未使用的
                    evicted_key, _ = self._data.popitem(last=False)
                    logger.debug(
                        "缓存淘汰 | name={} | key={}",
                        self.name, evicted_key,
                    )
                self._data[key] = (value, time.time())

    def delete(self, key: K) -> bool:
        """
        删除缓存条目

        Args:
            key: 缓存键

        Returns:
            True 表示删除成功，False 表示键不存在
        """
        with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False

    def clear(self) -> int:
        """
        清空缓存

        Returns:
            被清理的条目数量
        """
        with self._lock:
            count = len(self._data)
            self._data.clear()
            self.hits = 0
            self.misses = 0
            logger.debug("缓存已清空 | name={} | count={}", self.name, count)
            return count

    def cleanup_expired(self) -> int:
        """
        清理所有过期条目

        Returns:
            被清理的过期条目数量
        """
        if self.ttl_seconds <= 0:
            return 0

        with self._lock:
            now = time.time()
            expired_keys = [
                key for key, (_, ts) in self._data.items()
                if now - ts > self.ttl_seconds
            ]
            for key in expired_keys:
                del self._data[key]

            if expired_keys:
                logger.debug(
                    "过期条目已清理 | name={} | count={}",
                    self.name, len(expired_keys),
                )
            return len(expired_keys)

    @property
    def size(self) -> int:
        """当前缓存大小"""
        with self._lock:
            return len(self._data)

    def stats(self) -> dict:
        """
        获取缓存统计信息

        Returns:
            包含容量、命中次数、命中率等的字典
        """
        with self._lock:
            total = self.hits + self.misses
            hit_rate = self.hits / total if total > 0 else 0.0
            return {
                "name": self.name,
                "size": len(self._data),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl_seconds,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(hit_rate, 3),
            }

    def __contains__(self, key: K) -> bool:
        """检查键是否在缓存中（不考虑过期）"""
        with self._lock:
            return key in self._data

    def __len__(self) -> int:
        """返回缓存大小"""
        return self.size
