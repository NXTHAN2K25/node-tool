import os
import json
import sys  # 用于检测打包环境

class Config:
    # 基础配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    
    # 获取项目根目录 (basedir)
    # 逻辑：如果是打包环境，使用 exe 所在目录；否则使用当前文件所在目录
    if getattr(sys, 'frozen', False):
        # 打包后：使用可执行文件 (.exe) 所在的真实目录
        basedir = os.path.dirname(sys.executable)
    else:
        # 开发环境：使用 config.py 所在的目录
        basedir = os.path.abspath(os.path.dirname(__file__))
    
    # ---------------------------------------------------------
    # 数据库配置逻辑 (优先级: 环境变量 > db_config.json > 默认SQLite)
    # ---------------------------------------------------------
    
    # 1. 尝试读取 db_config.json
    _db_config = {}
    _config_path = os.path.join(basedir, 'db_config.json')
    try:
        if os.path.exists(_config_path):
            with open(_config_path, 'r', encoding='utf-8') as f:
                _db_config = json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load db_config.json: {e}")

    # 2. 确定数据库模式 (环境变量优先)
    # 环境变量: KOMARI_DB_MODE (sqlite, psql)
    _db_mode = os.environ.get('KOMARI_DB_MODE') or _db_config.get('db_mode', 'sqlite')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    if _db_mode == 'psql':
        # PostgreSQL 配置
        # 优先读取环境变量，否则读取 json 配置，最后默认值
        _pg_host = os.environ.get('PG_HOST') or _db_config.get('psql_config', {}).get('host', 'localhost')
        _pg_port = os.environ.get('PG_PORT') or _db_config.get('psql_config', {}).get('port', '5432')
        _pg_user = os.environ.get('PG_USER') or _db_config.get('psql_config', {}).get('user', 'komari_user')
        _pg_pass = os.environ.get('PG_PASSWORD') or _db_config.get('psql_config', {}).get('password', 'komari_password')
        _pg_db   = os.environ.get('PG_DB') or _db_config.get('psql_config', {}).get('database', 'komari_db')
        
        SQLALCHEMY_DATABASE_URI = f"postgresql://{_pg_user}:{_pg_pass}@{_pg_host}:{_pg_port}/{_pg_db}"
        print(f">>> Database Mode: PostgreSQL ({_pg_host}:{_pg_port}/{_pg_db})")
        
    else:
        # SQLite 配置 (默认)
        _sqlite_path = os.environ.get('SQLITE_PATH') or _db_config.get('sqlite_path', 'app.db')
        # 确保是绝对路径
        if not os.path.isabs(_sqlite_path):
            
            _sqlite_path = os.path.join(basedir, _sqlite_path)
            
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + _sqlite_path
        print(f">>> Database Mode: SQLite ({_sqlite_path})")