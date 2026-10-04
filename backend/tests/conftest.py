import os
import tempfile

# 必须在任何 app 模块导入之前指向 sqlite，否则 engine 会按默认配置连 Postgres
_fd, _db_path = tempfile.mkstemp(prefix="hallspan_test_", suffix=".db")
os.close(_fd)
os.environ["DATABASE_URL"] = "sqlite:///" + _db_path
os.environ["SEED_ON_EMPTY"] = "true"
