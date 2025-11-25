from __future__ import annotations

from pathlib import Path
from typing import Dict

import jinja2
import mlflow

TEMPLATE = """
<h1>{{ title }}</h1>
<ul>
{% for key, value in metrics.items() %}
<li>{{ key }}: {{ value }}</li>
{% endfor %}
</ul>
"""


def log_run(params: Dict[str, str], metrics: Dict[str, float], artifacts: Dict[str, Path]) -> None:
    with mlflow.start_run():
        for key, value in params.items():
            mlflow.log_param(key, value)
        for key, value in metrics.items():
            mlflow.log_metric(key, value)
        for key, path in artifacts.items():
            mlflow.log_artifact(path, artifact_path=key)


def render_report(metrics: Dict[str, float], target: Path) -> None:
    env = jinja2.Environment(autoescape=True)
    template = env.from_string(TEMPLATE)
    html = template.render(title="Backtest Report", metrics=metrics)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html)


__all__ = ["log_run", "render_report"]
