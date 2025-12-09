import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import polars as pl
import os

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from utils.logging_utils import build_task_log_path  # noqa: E402
from utils.performance_utils import MetaEngine  # noqa: E402


def test_build_task_log_path_creates_nested_path():
    with TemporaryDirectory() as tmp:
        path = build_task_log_path(
            base_dir=tmp,
            dag_id="dag/sample",
            run_id="run__1",
            task_id="task\\x",
            filename="custom.log",
        )
        expected = (
            Path(tmp)
            / "dag_id=dag_sample"
            / "run_id=run__1"
            / "task_id=task_x"
            / "custom.log"
        )
        assert path == expected


def test_metaengine_writes_log_file():
    with TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "my.log"

        class Dummy(metaclass=MetaEngine, log_file=str(log_path), log_level="INFO"):  # noqa: E306,E501
            def transform(self, frame: pl.DataFrame) -> pl.DataFrame:
                return frame

        dummy = Dummy()
        frame = pl.DataFrame({"a": [1]})
        dummy.transform(frame)

        assert log_path.exists()
        content = log_path.read_text()
        assert "Initiating process." in content
        assert "Done. Total time" in content


def test_metaengine_uses_instance_log_file_over_env():
    with TemporaryDirectory() as tmp:
        env_path = Path(tmp) / "env.log"
        inst_path = Path(tmp) / "inst.log"
        os.environ["METAENGINE_LOG_FILE"] = str(env_path)

        class Dummy(metaclass=MetaEngine, log_level="INFO"):  # noqa: E306
            log_file = None
            def transform(self, frame: pl.DataFrame) -> pl.DataFrame:
                return frame

        dummy = Dummy()
        dummy.log_file = str(inst_path)
        frame = pl.DataFrame({"a": [1]})
        dummy.transform(frame)

        del os.environ["METAENGINE_LOG_FILE"]
        assert inst_path.exists()
        assert not env_path.exists()


def test_metaengine_uses_env_log_file_if_no_instance_file():
    with TemporaryDirectory() as tmp:
        env_path = Path(tmp) / "env2.log"
        os.environ["METAENGINE_LOG_FILE"] = str(env_path)

        class DummyEnv(metaclass=MetaEngine, log_level="INFO"):  # noqa: E306
            def transform(self, frame: pl.DataFrame) -> pl.DataFrame:
                return frame

        dummy = DummyEnv()
        frame = pl.DataFrame({"a": [1]})
        dummy.transform(frame)

        del os.environ["METAENGINE_LOG_FILE"]
        assert env_path.exists()
