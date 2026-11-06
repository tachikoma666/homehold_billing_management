"""billing.unzip 单元测试（标准库 unittest，无需第三方依赖）。

覆盖：
1. list_entries 正常列出条目（名称/大小/加密标记）
2. extract 正确密码解压且内容一致
3. extract 指定 dest_dir
4. 密码错误抛 ValueError
5. 文件不存在抛 FileNotFoundError
6. GBK 文件名乱码还原（_fix_zip_name）
7. 真实微信账单 zip（存在时）：列出加密条目 + 错误密码报 ValueError
"""

from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from billing.unzip import _fix_zip_name, extract, list_entries  # noqa: E402

REAL_ZIP = Path(
    r"D:\AI PM课程\家庭账单agent测试"
    r"\微信支付账单流水文件(20261006-20261106)——【解压密码可在微信支付公众号查看】.zip"
)
PASSWORD = "123456"
CONTENT = "交易时间,交易类型,交易对方,商品,收/支,金额(元),支付方式,当前状态\n2026-10-01 12:00:00,商户消费,美团,外卖,支出,25.50,零钱,已支付\n"


def make_encrypted_zip(path: Path, inner_name: str = "账单流水.csv") -> None:
    """构造一个 ZipCrypto 加密 zip（模拟微信/支付宝账单附件）。"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.setpassword(PASSWORD.encode("utf-8"))
        info = zipfile.ZipInfo(inner_name)
        info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, CONTENT)


class TestUnzip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = Path(self.tmp.name)
        self.zip_path = self.tmp_path / "bill.zip"
        make_encrypted_zip(self.zip_path)

    def test_list_entries(self):
        entries = list_entries(self.zip_path)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["name"], "账单流水.csv")
        self.assertEqual(entries[0]["size"], len(CONTENT))
        self.assertTrue(entries[0]["encrypted"])

    def test_extract_default_dest(self):
        files = extract(self.zip_path, PASSWORD)
        self.assertEqual(len(files), 1)
        target = self.tmp_path / "bill" / "账单流水.csv"
        self.assertEqual(files[0], target)
        self.assertTrue(target.is_file())
        self.assertEqual(target.read_text(encoding="utf-8"), CONTENT)

    def test_extract_custom_dest(self):
        dest = self.tmp_path / "out" / "nested"
        files = extract(self.zip_path, PASSWORD, dest_dir=dest)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0], dest / "账单流水.csv")
        self.assertEqual(files[0].read_text(encoding="utf-8"), CONTENT)

    def test_wrong_password(self):
        with self.assertRaises(ValueError):
            extract(self.zip_path, "000000")

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            list_entries(self.tmp_path / "nope.zip")
        with self.assertRaises(FileNotFoundError):
            extract(self.tmp_path / "nope.zip", PASSWORD)

    def test_fix_gbk_filename(self):
        # 模拟旧版 Windows 工具写出的 GBK 文件名（无 UTF-8 标志位）
        gbk_name = "微信支付账单流水文件.csv".encode("gbk")
        mojibake = gbk_name.decode("cp437")  # zipfile 默认解码结果（乱码）
        info = zipfile.ZipInfo(mojibake)
        info.flag_bits = 0x1  # 加密且无 UTF-8 标志
        self.assertEqual(_fix_zip_name(info), "微信支付账单流水文件.csv")

    def test_fix_utf8_filename_untouched(self):
        info = zipfile.ZipInfo("账单流水.csv")
        info.flag_bits = 0x801  # 带 UTF-8 标志位
        self.assertEqual(_fix_zip_name(info), "账单流水.csv")

    @unittest.skipUnless(REAL_ZIP.is_file(), "真实微信账单 zip 不存在")
    def test_real_wechat_zip(self):
        entries = list_entries(REAL_ZIP)
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0]["encrypted"])
        self.assertIn(".xlsx", entries[0]["name"])
        with self.assertRaises(ValueError):
            extract(REAL_ZIP, "wrong-password-test")


if __name__ == "__main__":
    unittest.main(verbosity=2)
