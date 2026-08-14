import os
import shutil
import sys
import tempfile
import time

from numpy.compat import Path

# 适配导包路径，和之前test_decorators逻辑一致
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from utils.file_handler import check_file_suffix, get_file_fingerprint, read_text_file, scan_dir_files
from utils.decorators import FileOperationError

# ---------------- 测试1：后缀校验函数 check_file_suffix ----------------
def test_01_check_suffix():
    print("自测1：文件后缀校验")
    # 正向用例：合法后缀
    assert check_file_suffix("demo.txt") is True
    assert check_file_suffix("test.MD") is True
    print("合法后缀校验通过")

    # 反向用例
    try:
        check_file_suffix("data.xlsx")
    except FileOperationError:
        print("非法后缀正常抛出异常，校验通过")

# test_01_check_suffix()

# ---------------- 测试2：单文件读取 read_text_file ----------------
def test_02_read_single_file():
    print("\n===== 自测2：单文件读取 =====")
    # 先创建临时测试txt文件
    test_file = "temp_test.txt"
    with open(test_file, 'w', encoding="utf-8") as f:
        f.write("RAG测试文本内容")

    # 正向用例：正常读取，检验返回文本
    content = read_text_file(test_file)
    assert content == "RAG测试文本内容"
    print("正常文件读取成功，计时、日志装饰器生效")

    # 反向1：不存在的文件
    try:
        read_text_file("not_exist.txt")
    except FileOperationError:
        print("不存在文件正常抛出异常")
    # 反向2：不支持的后缀
    try:
        read_text_file("data.exe")
    except FileOperationError:
        print("非法格式文件正常拦截")

    # 清理临时文件
    os.remove(test_file)

# test_02_read_single_file()

# ---------------- 测试3：文件夹批量扫描 scan_dir_files ----------------
def test_03_scan_directory():
    print("\n===== 自测3：文件夹递归扫描 =====")
    # 创建临时测试目录
    temp_dir = "tempt_scan_dir"
    os.makedirs(temp_dir, exist_ok=True)
    # 创建合法、非法文件
    with open(os.path.join(temp_dir, "a.txt"), "w") as f:
        f.write("123")
    with open(os.path.join(temp_dir, "b.md"), "w") as f:
        f.write("456")
    with open(os.path.join(temp_dir, "c.xls"), "w") as f:
        f.write("789")

    #正向
    path_list = scan_dir_files(temp_dir)
    assert len(path_list) == 2
    print("文件夹扫描自动过滤非法文件，执行正常")

    #反向
    try:
        scan_dir_files("no_dir")
    except FileOperationError:
        print("非法目录路径正常抛出异常")

    # 清理临时目录
    for f in os.listdir(temp_dir):
        os.remove(os.path.join(temp_dir, f))
    os.rmdir(temp_dir)

# test_03_scan_directory()
def setup_test_env():
    """创建临时测试环境"""
    temp_dir = tempfile.mkdtemp(prefix="file_handler_test_")
    doc_dir = Path(temp_dir) / "docs"
    cache_dir = Path(temp_dir) / "cache"
    fingerprint_path = cache_dir / ".fingerprint"
    doc_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return doc_dir, cache_dir, fingerprint_path


def teardown_test_env(base_dir: Path):
    """清理测试环境"""
    if base_dir.exists():
        shutil.rmtree(base_dir, ignore_errors=True)


def test_01_fingerprint_generation():
    """测试1：生成指纹 - 相同目录生成相同指纹，变化后指纹不同"""
    doc_dir, cache_dir, fp_path = setup_test_env()
    try:
        # 创建文件
        (doc_dir / "a.txt").write_text("hello")
        (doc_dir / "b.md").write_text("world")
        time.sleep(0.01)

        fp1 = get_file_fingerprint(doc_dir)
        fp2 = get_file_fingerprint(doc_dir)
        assert fp1 == fp2, "相同目录指纹应一致"

        # 修改文件
        time.sleep(0.01)
        (doc_dir / "a.txt").write_text("hello world")
        fp3 = get_file_fingerprint(doc_dir)
        assert fp1 != fp3, "文件变化后指纹应不同"

        print("✅ test_01_fingerprint_generation 通过")
    finally:
        teardown_test_env(doc_dir.parent)

test_01_fingerprint_generation()

