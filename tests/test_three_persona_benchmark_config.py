from pathlib import Path
import hashlib

import pytest
import yaml

from multi_agent_personalities.evaluation.config import load_three_persona_benchmark_config


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/benchmark_three_personas_v1.yaml"


def test_fixed_benchmark_configuration():
    config = load_three_persona_benchmark_config(CONFIG)
    assert config.characters == ("sherlock", "poirot", "layton")
    assert config.chance_baseline == 1 / 3
    assert len(config.scenarios) == 6
    assert [scenario.speaker_order[0] for scenario in config.scenarios] == [
        "sherlock", "poirot", "layton", "sherlock", "poirot", "layton"
    ]
    for persona in config.personas.values():
        assert hashlib.sha256((ROOT / persona.path).read_bytes()).hexdigest() == persona.sha256


@pytest.mark.parametrize("mutation", ["baseline", "order", "duplicate", "persona"])
def test_invalid_benchmark_configuration_rejected(tmp_path, mutation):
    data = yaml.safe_load(CONFIG.read_text())
    benchmark = data["benchmark"]
    if mutation == "baseline":
        benchmark["chance_baseline"] = 0.5
    elif mutation == "order":
        benchmark["scenarios"][0]["speaker_order"] = ["poirot", "sherlock", "layton"]
    elif mutation == "duplicate":
        benchmark["scenarios"][1]["topic"] = benchmark["scenarios"][0]["topic"]
    else:
        del benchmark["personas"]["layton"]
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError):
        load_three_persona_benchmark_config(path)


@pytest.mark.parametrize('value', [None, '', '   '])
def test_model_configuration_required(tmp_path, value):
    data = yaml.safe_load(CONFIG.read_text())
    if value is None:
        del data['benchmark']['model']
    else:
        data['benchmark']['model'] = value
    path = tmp_path / 'config.yaml'
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError):
        load_three_persona_benchmark_config(path)


def test_model_is_frozen():
    assert load_three_persona_benchmark_config(CONFIG).model == 'gpt-5.6-luna'
