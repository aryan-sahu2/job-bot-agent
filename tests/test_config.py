from src.config.loader import Config, ConfigLoader


class TestConfigLoader:
    def test_default_config_when_file_missing(self):
        loader = ConfigLoader()
        config = loader.load("nonexistent.yaml")
        assert isinstance(config, Config)
        assert config.app.name == "job-bot"
        assert config.browser.headless is True
        assert config.browser.timeout == 30000
        assert config.llm.provider == "ollama"
        assert config.llm.model == "gemma3"

    def test_load_default_yaml(self):
        loader = ConfigLoader()
        config = loader.load()
        assert isinstance(config, Config)
        assert config.app.name == "job-bot"
