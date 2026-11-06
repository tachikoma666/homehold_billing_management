"""加密 zip 解压模块（微信/支付宝账单附件）。

微信与支付宝导出的账单 zip 使用 ZipCrypto 传统加密，密码由平台
（微信支付公众号 / 支付宝通知）单独发送，只作为参数传入、不落盘。

用法（由 Agent 调用，不提供命令行入口）::

    from billing.unzip import list_entries, extract

    entries = list_entries(zip_path)          # 查看内容与加密标记
    files = extract(zip_path, "123456")       # 解压到 zip 同名目录
    files = extract(zip_path, "123456", dest) # 解压到指定目录
"""

from __future__ import annotations

import zipfile
from pathlib import Path

__all__ = ["list_entries", "extract"]


def _fix_zip_name(info: zipfile.ZipInfo) -> str:
    """修正 zip 内中文文件名乱码。

    国内平台导出的 zip 在 Windows 上以系统编码（GBK）写入文件名且不带
    UTF-8 标志位，zipfile 会按 cp437 解码成乱码，这里还原成 GBK。
    """
    if info.flag_bits & 0x800:  # UTF-8 标志位，文件名本身正确
        return info.filename
    try:
        return info.filename.encode("cp437").decode("gbk")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def list_entries(zip_path: str | Path) -> list[dict]:
    """查看 zip 内容（无需密码），返回每个条目的名称、大小、是否加密。"""
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        raise FileNotFoundError(f"zip 文件不存在: {zip_path}")
    with zipfile.ZipFile(zip_path) as zf:
        return [
            {
                "name": _fix_zip_name(info),
                "size": info.file_size,
                "encrypted": bool(info.flag_bits & 0x1),
            }
            for info in zf.infolist()
            if not info.is_dir()
        ]


def extract(
    zip_path: str | Path,
    password: str,
    dest_dir: str | Path | None = None,
) -> list[Path]:
    """解压加密 zip，返回解压出的文件路径列表。

    - 密码错误时抛出 ValueError（zipfile 底层报 RuntimeError）。
    - 压缩方式为 AES（zipfile 不支持）时给出明确提示，改用 pyzipper。
    - 目录条目跳过；文件统一平铺到目标目录（账单 zip 内只有一个 CSV）。
    """
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        raise FileNotFoundError(f"zip 文件不存在: {zip_path}")
    dest = Path(dest_dir) if dest_dir else zip_path.parent / zip_path.stem
    dest.mkdir(parents=True, exist_ok=True)
    pwd = password.encode("utf-8")

    extracted: list[Path] = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            target = dest / Path(_fix_zip_name(info)).name
            try:
                with zf.open(info, pwd=pwd) as src, open(target, "wb") as dst:
                    dst.write(src.read())
            except NotImplementedError as exc:
                raise RuntimeError(
                    "该 zip 使用 AES 加密，标准库 zipfile 不支持；"
                    "请安装 pyzipper 后重试（pip install pyzipper）"
                ) from exc
            except RuntimeError as exc:
                if "password" in str(exc).lower():
                    raise ValueError(f"解压密码错误: {exc}") from exc
                raise
            extracted.append(target)
    return extracted
