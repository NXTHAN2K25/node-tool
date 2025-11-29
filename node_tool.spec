# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# -----------------------------------------------------------------------------
# 1. 动态收集数据文件的逻辑
# -----------------------------------------------------------------------------
def collect_pkg_data(package_root, include_extensions, exclude_dirs=None):
    """
    递归查找指定目录下的文件，并构建 datas 列表。
    :param package_root: 根目录名称 (例如 'app')
    :param include_extensions: 需要包含的扩展名列表 ['.html', '.css', '.js']
    :param exclude_dirs: 需要排除的文件夹名称列表 ['nodes']
    :return: List of tuples [(host_path, container_path)]
    """
    datas = []
    if exclude_dirs is None:
        exclude_dirs = []

    for root, dirs, files in os.walk(package_root):
        # 排除指定的目录（原地修改 dirs 列表以阻止 os.walk 进入）
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext in include_extensions:
                source_path = os.path.join(root, filename)
                # 计算在包内的相对路径，保持目录结构
                target_dir = root 
                datas.append((source_path, target_dir))
                print(f"Adding internal asset: {source_path} -> {target_dir}")
            
    return datas

# 定义需要打包进 exe 的文件类型
# 我们只打包代码逻辑和静态样式/模板
internal_extensions = ['.html', '.css', '.js', '.png', '.ico', '.svg', '.sh']

# 定义需要排除的文件夹（因为你想让它们在外部）
# 'nodes' 文件夹包含 yaml/json，我们不打包它
excluded_folders = ['nodes', '__pycache__']

# 执行收集
added_datas = collect_pkg_data('app', internal_extensions, excluded_folders)

# -----------------------------------------------------------------------------
# 2. PyInstaller Analysis
# -----------------------------------------------------------------------------
a = Analysis(
    ['run.py'],  # 入口文件
    pathex=[],
    binaries=[],
    datas=added_datas, # 这里填入上面收集到的文件列表
    hiddenimports=[
        # Flask 的一些插件可能需要手动声明
        'engineio.async_drivers.threading', 
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# -----------------------------------------------------------------------------
# 3. 生成 PYZ 包
# -----------------------------------------------------------------------------
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# -----------------------------------------------------------------------------
# 4. 生成 EXE (单文件模式 OneFile)
# -----------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='NodeTool',       # 生成的 exe 名字，build.py 会根据这个名字找文件
    debug=False,           
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,              # 默认开启 UPX，但 build.py 会自动检测并在需要时修改为 False
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,          # True: 显示黑框终端 (方便看日志), False: 只有 GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
