"""生成评测的泄漏检测测试。

find_leaks 是门禁的判定核心：既要抓住业务人员看不懂的系统标识，
又不能把 WMS / POD / HRMI 这类业务术语误报成泄漏。
"""

import pytest

from scripts.eval_generation import find_leaks


class TestFindLeaks:
    """内部标识识别"""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("导入（IMPORT）", ["IMPORT"]),
            ("已下单（ALREADY_CREATE_ORDER）", ["ALREADY_CREATE_ORDER"]),
            ("审批通过（REVIEW_PASS）", ["REVIEW_PASS"]),
            ("字段 customerOrderNo 重复", ["customerOrderNo"]),
            ("每月付款码 monthlyCardUuid", ["monthlyCardUuid"]),
            ("路由 /adiBus/order", ["/adiBus/order", "adiBus"]),
        ],
    )
    def test_detects_internal_identifiers(self, text, expected):
        """枚举常量、驼峰字段、前端路由都应被抓到"""
        assert sorted(find_leaks(text)) == sorted(expected)

    @pytest.mark.parametrize(
        "text",
        [
            "跨越速运（KYSY）支持添加运单号",
            "HRMI 人才测评系统",
            "WMS / POD / O2O / SKU / API 都是业务术语",
            "同时存数量和跟踪项的 JSON",
            "顺店通的标准版约 3800 元/年",
            "取件时间必须晚于当前 2 小时",
        ],
    )
    def test_ignores_business_terms(self, text):
        """业务术语、金额、数字不应误报"""
        assert find_leaks(text) == []

    def test_empty_text(self):
        """空答案不应报错"""
        assert find_leaks("") == []

    def test_multiple_leaks_deduped(self):
        """同一标识重复出现只计一次"""
        text = "状态 IMPORT，另一个 IMPORT，还有 DISPATCH"
        assert sorted(find_leaks(text)) == ["DISPATCH", "IMPORT"]
