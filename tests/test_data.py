from openclassrooms_projet5.config import DATA_DIR, MODELS_DIR, PROJ_ROOT


def test_project_directories_exist():
    assert PROJ_ROOT.exists()
    assert DATA_DIR.exists()
    assert MODELS_DIR.exists()
