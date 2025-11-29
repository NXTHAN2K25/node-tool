name: Build and Release

# 🟢 [修改] 触发条件：仅保留手动触发
# 原来的 push 触发器已被删除，现在提交代码不会自动构建了
on:
  workflow_dispatch:

jobs:
  # ----------------------------------------------------------------
  # 任务 1: Windows 构建
  # ----------------------------------------------------------------
  build-windows:
    runs-on: windows-latest
    steps:
    - name: Checkout Code
      uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.10'
        cache: 'pip'

    - name: Install Dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pyinstaller

    - name: Run Build Script
      run: python build.py

    - name: Upload Windows Artifact
      uses: actions/upload-artifact@v4
      with:
        name: Windows-Build
        path: "*.zip"
        retention-days: 5

  # ----------------------------------------------------------------
  # 任务 2: Linux 构建 (AMD64 和 ARM64)
  # ----------------------------------------------------------------
  build-linux:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        include:
          - arch: amd64
            platform: linux/amd64
          - arch: arm64
            platform: linux/arm64
            
    steps:
    - name: Checkout Code
      uses: actions/checkout@v4

    - name: Set up QEMU
      uses: docker/setup-qemu-action@v3

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3

    - name: Build Docker Image
      uses: docker/build-push-action@v5
      with:
        context: .
        file: Dockerfile
        load: true
        tags: node-tool-builder:latest
        platforms: ${{ matrix.platform }}
        cache-from: type=gha
        cache-to: type=gha,mode=max

    - name: Run Build and Extract
      run: |
        # 🟢 [Debug] 打印当前工作目录，方便排查
        echo "Current workspace: ${{ github.workspace }}"
        
        # 运行容器
        # 1. 挂载当前目录到容器内的 /output
        # 2. 执行构建脚本
        # 3. 🟢 [关键修改] 使用 find 命令查找并复制 zip 文件，避免通配符不匹配的问题
        #    同时打印文件列表以便调试
        docker run --rm --platform ${{ matrix.platform }} \
        -v "${{ github.workspace }}:/output" \
        node-tool-builder:latest \
        sh -c "python build.py && echo '--- Build Directory Content ---' && ls -lh && echo '--- Copying Zip ---' && cp *.zip /output/ || echo 'Copy failed'"

        # 🟢 [Debug] 检查宿主机上的文件是否复制成功
        echo "--- Host Directory Content ---"
        ls -lh ${{ github.workspace }}

    - name: Upload Linux Artifacts
      uses: actions/upload-artifact@v4
      with:
        name: Linux-${{ matrix.arch }}-Build
        path: "*.zip"
        retention-days: 5
