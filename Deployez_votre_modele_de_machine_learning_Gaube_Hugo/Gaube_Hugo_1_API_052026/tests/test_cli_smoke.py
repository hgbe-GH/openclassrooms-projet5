from pathlib import Path

from openclassrooms_projet5 import dataset, features, plots
from openclassrooms_projet5.modeling import train


def test_dataset_command_runs_without_error(tmp_path: Path):
    dataset.main(
        input_path=tmp_path / "dataset.csv",
        output_path=tmp_path / "dataset_processed.csv",
    )


def test_features_command_runs_without_error(tmp_path: Path):
    features.main(
        input_path=tmp_path / "dataset.csv",
        output_path=tmp_path / "features.csv",
    )


def test_plots_command_runs_without_error(tmp_path: Path):
    plots.main(
        input_path=tmp_path / "dataset.csv",
        output_path=tmp_path / "plot.png",
    )


def test_train_command_runs_without_error(tmp_path: Path):
    train.main(
        features_path=tmp_path / "features.csv",
        labels_path=tmp_path / "labels.csv",
        model_path=tmp_path / "model.pkl",
    )
